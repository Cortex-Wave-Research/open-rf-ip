"""Exact physical chirp and LED divider checks; no hardware access."""
import os
import cocotb
from cocotb.triggers import Timer
from models.python.chirp import ChirpModel, linear_config

@cocotb.test()
async def physical_chirp_and_leds(dut):
    hb_limit=int(os.environ['HB_LIMIT']);done_limit=int(os.environ['DONE_LIMIT'])
    model=ChirpModel();config=linear_config(500000,2000000,12000000,10000,repeat=True)
    hb=done=hc=dc=0;previous=None;emitted=0
    # Defaults check boundary by state injection after exact sample regression;
    # accelerated counters exercise many real LED transitions without injection.
    for cycle in range(40007):
        reset=cycle<4
        signature=0 if reset or previous is None else ((previous['i']&0x3fff).bit_count()+(previous['q']&0x3fff).bit_count()+previous['valid'])&1
        if reset:hb=done=hc=dc=0
        else:
            hc+=1
            if hc==hb_limit:hc=0;hb^=1
            if previous and previous['chirp_end'] and previous['valid'] and model.busy:
                dc+=1
                if dc==done_limit:dc=0;done^=1
        expected=model.tick(config,start=True,rst=reset)
        dut.clk.value=0;await Timer(41.667,unit='ns')
        dut.clk.value=1;await Timer(41.667,unit='ns')
        assert int(dut.heartbeat_n.value)==1-hb
        assert int(dut.chirp_led_n.value)==1-done
        assert int(dut.heartbeat_count.value)==hc
        assert int(dut.completion_count.value)==dc
        assert int(dut.unused_datapath_signature.value)==signature
        assert dut.i_sample.value.to_signed()==expected['i']
        assert dut.q_sample.value.to_signed()==expected['q']
        assert bool(dut.sample_valid.value)==expected['valid']
        assert bool(dut.chirp_end.value)==expected['chirp_end']
        assert int(dut.chirp.nco.phase.value)==model.phase
        emitted+=expected['valid'];previous=expected
    assert emitted==40002
    if hb_limit==6000000:
        # Explicit white-box boundary checks of production-width counters.
        # This is not a simulation of 0.5 s of elapsed board time.
        dut.clk.value=0
        dut.heartbeat_count.value=hb_limit-1
        dut.completion_count.value=done_limit-1
        await Timer(41.667,unit='ns');dut.clk.value=1;await Timer(41.667,unit='ns')
        assert int(dut.heartbeat_count.value)==0
        assert int(dut.heartbeat_n.value)==hb
        assert int(dut.completion_count.value)==done_limit-1
        # Next real completion arrives after remaining samples of chirp five.
        for _ in range(10000):
            old_end=bool(dut.chirp_end.value)
            dut.clk.value=0;await Timer(41.667,unit='ns')
            dut.clk.value=1;await Timer(41.667,unit='ns')
            if old_end:
                assert int(dut.completion_count.value)==0
                assert int(dut.chirp_led_n.value)==done
                break
        else:assert False,'No completion in a full chirp'
