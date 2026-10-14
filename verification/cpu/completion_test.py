"""Bounded real-firmware START/completion/read/CLEAR_STATUS regression."""
import cocotb
from verification.cpu import system_test


@cocotb.test()
async def cpu_completion_clear(d):
    await system_test.execute_firmware(d, focus_completion=True)
