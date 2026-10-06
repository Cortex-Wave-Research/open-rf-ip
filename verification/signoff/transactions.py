"""Version 1 public-port transactions, shared unchanged by both simulators."""
import random
from models.python import control_registers as R


def vectors(seed=None):
    ops = [{'reset': True}]
    def access(a, v=None, sel=15, **kw):
        ops.append(dict(address=a, write=v is not None, value=v or 0, select=sel, **kw))
    def command(v, **kw):
        access(R.ADDR_COMMAND, v, **kw)
    for a in R.REGISTERS:
        access(a)
    command(R.CMD_START)
    access(R.ADDR_SCRATCH, 0x12345678)
    for sel in range(16):
        access(R.ADDR_SCRATCH, 0xaabbccdd, sel)
        access(R.ADDR_SCRATCH)
    access(R.ADDR_CHIRP_LENGTH, 16)
    for reverse in (False, True):
        for lo in (R.ADDR_NCO_PHASE_INC_LO, R.ADDR_CHIRP_START_LO, R.ADDR_CHIRP_STEP_LO):
            halves = [(lo, 0xbbbbbbbb), (lo+4, 0xcccccccc)]
            for a, v in reversed(halves) if reverse else halves:
                access(a, v)
            command(R.CMD_COMMIT)  # invalid compact, valid full-width HP
            access(lo+4, 0xffffffff if lo == R.ADDR_CHIRP_STEP_LO else 0)
    command(R.CMD_COMMIT)
    access(R.ADDR_RUN_CONTROL, 1)
    command(R.CMD_START)
    command(R.CMD_COMMIT, busy=True)
    command(R.CMD_START, busy=True)
    access(R.ADDR_CHIRP_START_LO, 123)
    command(R.CMD_START)
    access(R.ADDR_MODE, 7)
    command(R.CMD_COMMIT)
    command(3)
    access(0x80)
    access(0x29, 33)
    access(R.ADDR_IP_ID, 1)
    access(R.ADDR_COMMAND, R.CMD_COMMIT, 1)
    command(R.CMD_CLEAR_STATUS, done=True)
    command(R.CMD_CLEAR_STATUS)
    if seed is not None:
        rng = random.Random(seed)
        addresses = list(R.REGISTERS) + [1, 0x11, 0x45, 0x48, 0xfffc]
        for _ in range(500):
            a = rng.choice(addresses)
            value = rng.choice([0, 1, 2, 3, 4, rng.getrandbits(32)])
            ops.append(dict(address=a, write=bool(rng.getrandbits(1)), value=value,
                            select=rng.randrange(16), busy=rng.random() < .15,
                            done=rng.random() < .05, reset=rng.random() < .02))
    return {'version': 1, 'seed': seed, 'transactions': ops}
