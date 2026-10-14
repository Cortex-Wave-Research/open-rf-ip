"""Passive observers only: every control transaction originates in the real CPU."""
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from models.python.control_plane import ControlPlane
from models.python import control_registers as R
from models.python.high_purity import HighPurityNCO, HighPurityChirp, HighPurityConfig
from models.python.nco_lut import LutNCO
from models.python.chirp import ChirpModel, ChirpConfig
from verification.cpu.wishbone_observer import completion as check_completion, csr_state
from verification.cpu.pause_observer import PauseObserver
from verification.cpu.dbus_observer import DBusObserver, request_payload
from verification.cpu.startup_observer import StartupObserver
from verification.cpu.completion_observer import CompletionObserver


def scope(handle, path):
    """Resolve each hierarchy component separately through the VPI API."""
    for component in path.split('.'):
        handle = handle[component]
    return handle


async def execute_firmware(d, focus_pause=False, focus_x=False, focus_completion=False,
                           reset_cycles=8, interrupt_when=None):
    hp, kind = int(os.environ['HP']), int(os.environ['KIND'])
    m = ControlPlane(hp, kind)
    engine = (HighPurityChirp() if hp else ChirpModel()) if kind else (HighPurityNCO() if hp else LutNCO())
    controlled = scope(d, ('chirp' if kind else 'tone') + '.controlled')
    control = controlled.control
    pause = PauseObserver(controlled, hp, kind)
    run_events, cycle_outputs = [], []
    transcript, samples, queue = [], [], []
    previous = None
    transaction = False
    stages = []
    first_pc = None
    csr_count = 0
    pending_wb = None
    rejected_tone_start = 0
    old_mailbox = 0
    active_changes = 0
    negative_commits = 0
    mmio_reads = set()
    dbus = DBusObserver()
    startup = StartupObserver()
    lifecycle = CompletionObserver() if kind else None
    d.clk.value = 0
    d.rst.value = 1
    for cycle in range(300000):
        reset = cycle < reset_cycles
        d.clk.value = 0
        d.rst.value = int(reset)
        await Timer(5, unit='ns')
        def value(h, n): return int(getattr(h, n).value)
        startup.check(d.cpu, cycle, reset)
        if not reset and value(d, 'i_valid') and value(d, 'i_ready'):
            if first_pc is None: first_pc = value(d, 'i_pc')
        if not reset:
            try:
                dbus.check(d, cycle)
            except AssertionError:
                raw = {n: str(getattr(d,n).value) for n in (
                    'rst','i_pc','d_valid','d_ready','d_wr','d_address','d_data','d_mask',
                    'd_rsp_ready','d_error','d_rdata','wb_cyc','wb_stb','wb_we',
                    'wb_addr','wb_wdata','wb_sel','wb_ack','wb_err','wb_rdata')}
                raw.update({'cpu.'+n: str(getattr(d.cpu,n).value) for n in (
                    'execute_PC','execute_INSTRUCTION','execute_RS2','memory_PC')})
                Path(os.environ['CPU_RESULT']+'.failure.json').write_text(json.dumps(
                    dict(cycle=cycle,time_ns=cycle*10+5,signals=raw),indent=2)+'\n')
                raise
            assert not value(d, 'i_error'), ('instruction fault', cycle)
            if value(d, 'd_valid') and value(d, 'd_ready'):
                a = value(d, 'd_address')
                if a >> 16 == 0x4000:
                    request = request_payload(d, 'd_address', 'd_wr', 'd_data', 'd_mask')
                    request = (a & 0xffff, *request[1:])
                    queue.append(request)
                    transcript.append([cycle, 'cpu', a, *request[1:]])
            bus_request = None
            if value(d, 'wb_cyc') or value(d, 'wb_stb'):
                bus_request = request_payload(d, 'wb_addr','wb_we','wb_wdata','wb_sel')
                owned = pending_wb[0] if pending_wb is not None else (queue[0] if queue else None)
                assert owned is not None and bus_request == owned, ('unowned/changed WB request', cycle)
                assert value(d, 'wb_cyc') and value(d, 'wb_stb')
            if value(d, 'wb_ack') or value(d, 'wb_err'):
                assert pending_wb is not None, ('duplicate WB completion', cycle)
                owned, result = pending_wb
                data, error = result
                response = value(d,'wb_rdata') if not owned[1] or error else None
                dbus.wishbone(owned, result)
                check_completion(owned, bus_request, value(d,'wb_cyc'), value(d,'wb_stb'),
                                 value(d,'wb_ack'), value(d,'wb_err'), response, result)
                transcript.append([cycle, 'wb', value(d, 'wb_addr'), value(d, 'wb_we'),
                                   response, value(d, 'wb_sel'), int(error)])
                pending_wb = None
        request = None
        if not reset and value(control, 'req'):
            request = request_payload(control, 'addr','we','wdata','sel')
            assert queue and queue.pop(0) == request, ('non-CPU or duplicate CSR request', cycle)
            csr_count += 1
            if not request[1]: mmio_reads.add(request[0])
        enable = m.run and m.valid
        completion = bool(previous and previous['valid'] and previous['chirp_end'])
        busy = transaction if kind else enable
        if kind:
            step = m.pair(R.ADDR_CHIRP_STEP_LO, True)
            if step & (1 << 63): step -= 1 << 64
            cfg = (HighPurityConfig if hp else ChirpConfig)(m.pair(R.ADDR_CHIRP_START_LO, True),
                  step, m.active[R.ADDR_CHIRP_LENGTH], bool(m.active[R.ADDR_CHIRP_CONFIG] & 1))
            expected = engine.tick(cfg, start=m.start, enable=enable, rst=reset)
            if reset: transaction = False
            else:
                if completion and not cfg.repeat: transaction = False
                if m.start: transaction = True
        else:
            i, q, valid = engine.tick(m.pair(R.ADDR_NCO_PHASE_INC_LO, True), enable=enable, rst=reset)
            expected = dict(i=i, q=q, valid=valid, chirp_start=False, chirp_end=False)
        before, sequence = m.active.copy(), m.sequence
        data, error = m.tick(request, busy=busy, completion=completion, reset=reset)
        if request:
            assert pending_wb is None
            pending_wb = (request, (data, error))
            if request[1] and request[0] == R.ADDR_RUN_CONTROL:
                run_events.append([cycle, request[2], request[3], int(error), int(m.run)])
            transcript.append([cycle, 'csr', *request, data, int(error), m.sequence, m.errors,
                               m.pair(R.ADDR_NCO_PHASE_INC_LO, True), m.pair(R.ADDR_CHIRP_START_LO, True),
                               m.pair(R.ADDR_CHIRP_STEP_LO, True)])
            if request[1] and request[0] == R.ADDR_COMMAND:
                if request[2] == R.CMD_COMMIT and m.sequence == sequence:
                    negative_commits += 1
                    assert m.active == before
                if not kind and request[2] == R.CMD_START:
                    assert m.errors & R.ERR_BAD_COMMAND and not m.start and m.active == before
                    rejected_tone_start += 1
        if m.active != before: active_changes += 1
        previous = expected
        d.clk.value = 1
        await Timer(5, unit='ns')
        csr_state(control.csr, m)
        observed = {}
        for field, port in [('i', 'i_out'), ('q', 'q_out'), ('valid', 'sample_valid'),
                            ('chirp_start', 'chirp_start'), ('chirp_end', 'chirp_end')]:
            actual = getattr(d, port).value.to_signed() if field in ('i', 'q') else value(d, port)
            observed[field] = actual
            assert actual == expected[field], (cycle, field, actual, expected[field])
        pause.check(cycle, reset, enable, engine, observed)
        if focus_pause:
            cycle_outputs.append([cycle, int(m.run), *observed.values(), engine.phase])
        for port, expected_active in [('active_nco_o', m.pair(R.ADDR_NCO_PHASE_INC_LO, True)),
                                     ('active_start_o', m.pair(R.ADDR_CHIRP_START_LO, True)),
                                     ('active_step_o', m.pair(R.ADDR_CHIRP_STEP_LO, True)),
                                     ('active_length_o', m.active[R.ADDR_CHIRP_LENGTH]),
                                     ('start_o', m.start)]:
            assert value(control.csr, port) == expected_active, (cycle, port)
        if expected['valid']: samples.append([expected[k] for k in ('i', 'q', 'valid', 'chirp_start', 'chirp_end')])
        mb = value(d, 'mailbox_o')
        if mb != old_mailbox:
            transcript.append([cycle, 'mailbox', mb]); stages.append(mb); old_mailbox = mb
        assert mb >> 16 != 0xdead, ('firmware FAIL signature', hex(mb), cycle)
        if lifecycle:
            lifecycle.check(cycle, request, m, observed, transaction, len(samples), dbus.events)
        if interrupt_when and interrupt_when(cycle, len(samples), pause.paused_cycles):
            return dict(cycles=cycle+1, samples=samples, transcript=transcript,
                        dbus=dbus.events, startup=startup.entry, phase=engine.phase)
        if focus_completion and 'clear' in lifecycle.events and cycle == lifecycle.events['clear'] + 1:
            lifecycle.validate(cycle, m, transaction, transcript)
            assert len(samples) == 10000 and startup.entry is not None
            assert sum(x[3] for x in samples) == 1 and sum(x[4] for x in samples) == 1
            Path(os.environ['CPU_RESULT']).write_text(json.dumps(dict(
                result='PASS',cycles=cycle+1,lifecycle=lifecycle.events,
                samples=samples,transcript=transcript,dbus=dbus.events),indent=2)+'\n')
            return
        if focus_x and mb == 0x20:
            assert startup.entry is not None
            assert dbus.reads[0x40000004] == 0x00010000
            assert dbus.reads[0x4000000c] == 0x81234567
            assert not queue and pending_wb is None and dbus.pending is None
            Path(os.environ['CPU_RESULT']).write_text(json.dumps(dict(
                result='PASS', cycles=cycle+1, transcript=transcript,
                dbus=dbus.events, startup=startup.entry,
                ignored_read_payloads=dbus.ignored_read_payloads),indent=2)+'\n')
            return
        if focus_pause and pause.resumed_samples >= 32 and mb == 0x50:
            assert first_pc == 0x80000000 and stages == [0x10,0x20,0x30,0x40,0x50]
            assert [x[1] for x in run_events] == [1,0,1]
            assert pause.paused_cycles > 23 and not queue and pending_wb is None
            Path(os.environ['CPU_RESULT']).write_text(json.dumps(dict(
                result='PASS',scope='focused real CPU pause/resume',cycles=cycle+1,
                pause_cycles=pause.paused_cycles,resume_cycle=pause.resume_cycle,
                resumed_samples=pause.resumed_samples,run_events=run_events,
                transcript=transcript,dbus=dbus.events,cycle_outputs=cycle_outputs),indent=2)+'\n')
            return
        if mb == 0x600d600d: break
    else:
        raise AssertionError('Firmware timeout: no PASS signature')
    assert first_pc == 0x80000000
    assert stages == [0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x600d600d], stages
    assert len(samples) >= 10000 and pause.paused_cycles > 23
    assert [x[1] for x in run_events] == [1,0,1,0] and pause.resumed_samples >= 32
    assert not queue and pending_wb is None and csr_count > 40
    assert negative_commits >= (2 if hp else 4)
    assert active_changes == 1 and m.sequence == 2
    assert {R.ADDR_IP_ID,R.ADDR_ABI_VERSION,R.ADDR_CAPABILITIES,R.ADDR_SCRATCH,
            R.ADDR_STATUS,R.ADDR_ERROR_STATUS} <= mmio_reads
    if kind:
        assert len(samples) == 10000 and not transaction
        lifecycle.validate(cycle, m, transaction, transcript, final_pass=True)
        assert sum(x[3] for x in samples) == 1 and sum(x[4] for x in samples) == 1
    else:
        assert rejected_tone_start >= 2 and not m.done
    out = Path(os.environ['CPU_RESULT'])
    out.write_text(json.dumps(dict(result='PASS', cycles=cycle+1, profile=hp, kind=kind,
        samples=len(samples), main_samples=10000, first_pc=first_pc, stages=stages,
        csr_transactions=csr_count, rejected_commits=negative_commits,
        tone_start_rejections=rejected_tone_start, pause_cycles=pause.paused_cycles,
        run_events=run_events,completion_lifecycle=lifecycle.events if lifecycle else None,
        I_mismatches=0,Q_mismatches=0,valid_mismatches=0,start_mismatches=0,end_mismatches=0,
        alignment_correction=False,dbus=dbus.events,transcript=transcript,main_waveform=samples[:10000]),indent=2)+'\n')


@cocotb.test()
async def firmware_execution(d):
    await execute_firmware(d)
