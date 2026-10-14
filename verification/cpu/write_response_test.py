"""Deterministic regression of CPU observer semantics on the frozen control RTL."""
import json
import os
from pathlib import Path
import cocotb
from models.python import control_registers as R
from verification.cocotb.control_bus import Bus
from verification.cpu.wishbone_observer import completion, csr_state


@cocotb.test()
async def write_then_read(d):
    rows = []
    class ObservedBus(Bus):
        async def tick(self, request=None, reset=False):
            executed = int(d.req.value) if not reset else 0
            if request:
                assert executed == 1
                actual = tuple(int(getattr(d,n).value) for n in ('addr','we','wdata','sel'))
                assert actual == request
            else:
                assert not executed
            result = await super().tick(request, reset)
            csr_state(d.csr, self.model)
            if request:
                actual = tuple(int(getattr(d,n).value) for n in
                               ('wb_adr_i','wb_we_i','wb_dat_i','wb_sel_i'))
                pins = [int(getattr(d,n).value) for n in
                        ('wb_cyc_i','wb_stb_i','wb_ack_o','wb_err_o','wb_dat_o')]
                completion(request, actual, *pins, result)
                rows.append(dict(request=request, response=pins, model=result))
            return result
    b = ObservedBus(d, 0, 0)
    await b.reset()
    await b.write(R.ADDR_NCO_PHASE_INC_LO, 0x11)
    await b.write(R.ADDR_NCO_PHASE_INC_LO, 0x19999999)
    assert rows[-1]['response'][-1] == 0x11  # reproduce implementation evidence
    assert rows[-1]['model'][0] == 0        # model write placeholder, not ABI data
    await b.access(R.ADDR_NCO_PHASE_INC_LO)
    await b.write(R.ADDR_NCO_PHASE_INC_LO, 0xaabbccdd, 5)
    await b.access(R.ADDR_NCO_PHASE_INC_LO)
    await b.command(R.CMD_COMMIT)
    await b.access(R.ADDR_CONFIG_SEQUENCE)
    assert b.model.sequence == 1 and b.model.pair(R.ADDR_NCO_PHASE_INC_LO, True) == 0x19bb99dd
    await b.write(R.ADDR_IP_ID, 0x11)  # ERR and unchanged RO state
    await b.access(R.ADDR_IP_ID)
    # Deliberately corrupt each meaningful completion field: checker must reject.
    req = (R.ADDR_SCRATCH, True, 0x55, 15)
    for index in range(4):
        altered = list(req); altered[index] ^= 1
        try: completion(req, tuple(altered), 1, 1, 1, 0, 0x11, (0, False))
        except AssertionError: pass
        else: raise AssertionError(('accepted corrupt request', index))
    for ack, err in ((0,0),(0,1),(1,1)):
        try: completion(req, req, 1, 1, ack, err, 0x11, (0,False))
        except AssertionError: pass
        else: raise AssertionError('accepted corrupt termination')
    read = (R.ADDR_SCRATCH, False, 0, 15)
    try: completion(read, read, 1, 1, 1, 0, 0x10, (0x11,False))
    except AssertionError: pass
    else: raise AssertionError('accepted corrupt read data')
    Path(os.environ['OBSERVER_RESULT']).write_text(json.dumps(rows,indent=2)+'\n')
