"""Check startup and full sample retention against the independent LUT model."""
import cocotb
from cocotb.triggers import Timer

from models.python.nco_lut import LutNCO


@cocotb.test()
async def startup_and_fixed_tone(dut):
    model = LutNCO()
    for cycle in range(10004):
        reset = cycle < 4
        previous_i, previous_q = model.output_words
        signature = (previous_i.bit_count() + previous_q.bit_count()
                     + int(model.sample_valid)) & 1
        expected = model.tick(0x15555555, rst=reset)
        dut.clk.value = 0
        await Timer(5, unit="ns")
        dut.clk.value = 1
        await Timer(5, unit="ns")
        assert int(dut.activity.value) == (0 if reset else signature)
        assert dut.i_sample.value.to_signed() == expected[0]
        assert dut.q_sample.value.to_signed() == expected[1]
        assert int(dut.sample_valid.value) == expected[2]
    dut._log.info("Four reset edges and 10,000 exact I/Q/signature comparisons passed")
