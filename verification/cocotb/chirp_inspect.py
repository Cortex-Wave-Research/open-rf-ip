import cocotb
from models.python.chirp import ChirpConfig
from verification.cocotb.chirp_cocotb import Bench


@cocotb.test()
async def inspect_short_chirp(dut):
    b = Bench(dut)
    await b.reset()
    for _ in range(3):
        await b.cycle(enable=False)
    await b.cycle(ChirpConfig(0x051eb852, 0x00800000, 16, True), start=True)
    for k in range(80):
        await b.cycle(enable=not 20 <= k < 24)
    await b.reset()
    await b.cycle(ChirpConfig(0x33333333, -0x01000000, 16), start=True)
    for _ in range(20):
        await b.cycle()
