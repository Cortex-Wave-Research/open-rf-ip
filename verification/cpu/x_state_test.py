"""Real firmware prefix: reset, self-test, ABI_VERSION and SCRATCH readback."""
import cocotb
from verification.cpu import system_test


@cocotb.test()
async def cpu_required_read_data(d):
    await system_test.execute_firmware(d, focus_x=True)
