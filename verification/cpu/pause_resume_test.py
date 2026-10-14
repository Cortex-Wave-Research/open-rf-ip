"""Focused real-CPU prefix through 32 resumed samples, unchanged firmware."""
import cocotb
from verification.cpu import system_test

@cocotb.test()
async def cpu_pause_resume(d):
    await system_test.execute_firmware(d, focus_pause=True)
