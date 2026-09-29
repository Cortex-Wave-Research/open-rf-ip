"""Verify the target harness against the independent programmable chirp model."""
import cocotb
from cocotb.triggers import Timer
from models.python.chirp import ChirpModel, linear_config


@cocotb.test()
async def startup_and_two_chirps(dut):
    model = ChirpModel()
    c = linear_config(2_000_000, 20_000_000, 100_000_000, 10000, repeat=True)
    previous = dict(i=0, q=0, valid=False, chirp_start=False, chirp_end=False)
    emitted = 0
    for cycle in range(20005):
        reset = cycle < 4
        parity = ((previous['i'] & 0x3fff).bit_count()
                  + (previous['q'] & 0x3fff).bit_count()
                  + previous['valid'] + previous['chirp_start']
                  + previous['chirp_end'] + model.busy) & 1
        expected = model.tick(c, start=True, rst=reset)
        dut.clk.value = 0
        await Timer(5, unit='ns')
        dut.clk.value = 1
        await Timer(5, unit='ns')
        assert int(dut.activity.value) == (0 if reset else parity)
        assert dut.i_sample.value.to_signed() == expected['i']
        assert dut.q_sample.value.to_signed() == expected['q']
        assert bool(dut.sample_valid.value) == expected['valid']
        assert bool(dut.chirp_start.value) == expected['chirp_start']
        assert bool(dut.chirp_end.value) == expected['chirp_end']
        assert bool(dut.busy.value) == model.busy
        assert int(dut.chirp.nco.phase.value) == model.phase
        emitted += expected['valid']
        previous = expected
    assert emitted == 20000
