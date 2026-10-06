"""Reset only through the public clock/reset; retain the independent edge scoreboard."""
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from models.python import control_registers as R
from verification.cocotb.control_bus import Bus


@cocotb.test()
async def reset_at_transaction_boundaries(d):
    hp, kind = int(os.environ['HP']), int(os.environ['KIND'])
    waveform = bool(int(os.environ['WAVEFORM']))
    b = Bus(d, hp, kind, waveform)
    await Timer(1, unit='ns')
    # Evidence that separate processes really randomize initial state. Never used
    # as a reference value, and never require any architectural value pre-reset.
    probe = int((d.i_out if waveform else d.active_nco_o).value)
    scenarios = []

    async def check_reset(label):
        b.busy = b.completion = False
        await b.reset()
        for address in R.REGISTERS:
            await b.access(address)
        assert not any((b.model.valid, b.model.dirty, b.model.sequence,
                        b.model.errors, b.model.done, b.model.run, b.model.start))
        assert not any(b.model.active.values())
        assert b.model.shadow == {a: kind if a == R.ADDR_MODE else 0
                                  for a in b.model.shadow}
        if waveform:
            assert b.engine.phase == 0 and not b.samples
        scenarios.append(label)

    async def execute(address, value):
        # Stop immediately after B, without the normal response retirement C.
        for name, v in [('wb_cyc_i', 1), ('wb_stb_i', 1), ('wb_we_i', 1),
                        ('wb_adr_i', address), ('wb_dat_i', value), ('wb_sel_i', 15)]:
            getattr(d, name).value = v
        await b.tick()
        await b.tick((address, True, value, 15))

    async def configure(length=64):
        await b.pair(R.ADDR_NCO_PHASE_INC_LO, 0x12345678)
        await b.pair(R.ADDR_CHIRP_START_LO, 0x23456789)
        await b.pair(R.ADDR_CHIRP_STEP_LO, (1 << 64)-7, True)
        await b.write(R.ADDR_CHIRP_LENGTH, length)
        await b.command(R.CMD_COMMIT)
        assert b.model.valid

    await check_reset('idle')
    await b.write(R.ADDR_CHIRP_LENGTH, 64)
    await check_reset('dirty shadow')
    for address, label in [(R.ADDR_NCO_PHASE_INC_LO, 'LOW'),
                           (R.ADDR_NCO_PHASE_INC_HI, 'HIGH')]:
        await execute(address, 0xabcdef01)
        await check_reset('immediately after ' + label)
    await configure()
    await b.write(R.ADDR_CHIRP_START_LO, 55)
    # Captured command is canceled by reset on its would-be execution edge.
    for name, v in [('wb_cyc_i', 1), ('wb_stb_i', 1), ('wb_we_i', 1),
                    ('wb_adr_i', R.ADDR_COMMAND), ('wb_dat_i', R.CMD_COMMIT), ('wb_sel_i', 15)]:
        getattr(d, name).value = v
    await b.tick()
    await check_reset('immediately before COMMIT execution')
    await b.write(R.ADDR_CHIRP_LENGTH, 64)
    await execute(R.ADDR_COMMAND, R.CMD_COMMIT)
    await check_reset('immediately after COMMIT execution')
    for pause in (False, True):
        await configure()
        await b.write(R.ADDR_RUN_CONTROL, 1)
        if waveform:
            if kind:
                await b.command(R.CMD_START)
            for _ in range(8):
                await b.tick()
            assert b.samples
        else:
            b.busy = True
        if pause:
            await b.write(R.ADDR_RUN_CONTROL, 0)
            for _ in range(5):
                await b.tick()
        await check_reset('paused busy engine' if pause else 'busy engine')
    await configure()
    await check_reset('RUN_ENABLE low with valid config')
    await b.command(R.CMD_START)
    await b.command(3)
    if not waveform:
        b.completion = True
        await b.tick()
        b.completion = False
    elif kind:
        await configure(2)
        await b.write(R.ADDR_RUN_CONTROL, 1)
        await b.command(R.CMD_START)
        for _ in range(10):
            await b.tick()
        assert b.model.done
    await check_reset('sticky error/completion')
    for n in range(4):
        await b.write(R.ADDR_SCRATCH, 0x11223344 + n)
        await check_reset(f'repeated reset {n}')
    Path(os.environ['RESET_RESULT']).write_text(json.dumps({
        'seed': int(os.environ['SIGNOFF_SEED']), 'pre_reset_probe': probe,
        'scenarios': scenarios, 'cycles': b.cycles, 'result': 'PASS'}, indent=2)+'\n')
