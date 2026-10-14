"""Real CPU restart after randomized boot, active-waveform and paused aborts."""
import json
import os
import random
from pathlib import Path
import cocotb
from verification.cpu import system_test


@cocotb.test()
async def cpu_reset_recovery(d):
    rng = random.Random(int(os.environ['CPU_SEED']))
    boot, active, paused = rng.randrange(100, 2000), rng.randrange(17, 101), rng.randrange(5, 50)
    prefixes = []
    for condition in (lambda c,s,p: c == boot, lambda c,s,p: s == active,
                      lambda c,s,p: p == paused):
        prefixes.append(await system_test.execute_firmware(
            d, reset_cycles=rng.randrange(4, 13), interrupt_when=condition))
    # Each entry resets CPU, adapter, CSR and waveform together. Final execution
    # must complete all normal firmware/numerical checks after the paused abort.
    await system_test.execute_firmware(d, reset_cycles=rng.randrange(4, 13))
    path = Path(os.environ['CPU_RESULT'])
    result = json.loads(path.read_text())
    result['reset_prefixes'] = prefixes
    result['reset_targets'] = [boot, active, paused]
    path.write_text(json.dumps(result, indent=2)+'\n')
