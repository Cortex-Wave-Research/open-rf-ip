"""Read-only retirement observation of deterministic software C-entry state."""
import re
from pathlib import Path
from verification.cpu.dbus_observer import resolved


class StartupObserver:
    def __init__(self):
        dis = Path('build/vexriscv/firmware/firmware.dis').read_text()
        self.main = int(re.search(r'^([0-9a-f]+) <main>:', dis, re.M)[1], 16)
        call = re.search(r'^([0-9a-f]+):.*jalr\s+ra,.*<main>', dis, re.M)
        self.return_pc = int(call[1], 16) + 4
        self.registers = {}
        self.entry = None

    def check(self, cpu, cycle, reset):
        if reset:
            self.registers.clear()
            self.entry = None
            return
        if self.entry is not None:
            return
        # Immediately before main's first instruction retires: preceding startup
        # writes have committed, but main's SP decrement has not committed yet.
        if resolved(cpu.writeBack_arbitration_isFiring) and resolved(cpu.writeBack_PC) == self.main:
            expected = {i: 0 for i in range(3, 32)}
            expected.update({1: self.return_pc, 2: 0x80010400})
            assert self.registers == expected, ('C-entry register state', cycle, self.registers, expected)
            self.entry = dict(cycle=cycle, pc=self.main, registers=self.registers.copy())
            return
        if resolved(cpu.lastStageRegFileWrite_valid):
            index = resolved(cpu.lastStageRegFileWrite_payload_address)
            if index:
                self.registers[index] = resolved(cpu.lastStageRegFileWrite_payload_data)
