"""Short, bit-checked capture for human inspection; no long-regression tracing."""

import cocotb

from verification.cocotb.nco_cocotb import Bench


@cocotb.test()
async def inspection_10mhz(dut):
    bench = Bench(dut)
    increment = 0x1999999A  # 10 MHz, rounded tuning word at fs = 100 MHz.
    # 200 clocks at 10 ns each = 2 us. Each edge is checked against Python.
    for count, enable, rst in [
        (2, False, True),
        (3, False, False),
        (120, True, False),
        (5, False, False),
        (60, True, False),
        (2, True, True),
        (8, True, False),
    ]:
        for _ in range(count):
            await bench.cycle(increment, enable=enable, rst=rst)
    dut._log.info("Inspection capture: 200 clocks, 2 us, 0 mismatches")
