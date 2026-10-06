"""Public-port-only replay: identical JSON stimulus and transcript on each simulator."""
import json
import os
from pathlib import Path
import cocotb
from verification.cocotb.control_bus import Bus
from models.python import control_registers as R


@cocotb.test()
async def common_transactions(d):
    rows = []
    class TranscriptBus(Bus):
        async def tick(self, request=None, reset=False):
            result = await super().tick(request, reset)
            names = ('wb_rst_i', 'wb_cyc_i', 'wb_stb_i', 'wb_we_i', 'wb_adr_i',
                     'wb_dat_i', 'wb_sel_i', 'wb_ack_o', 'wb_err_o', 'wb_dat_o',
                     'engine_busy_i', 'engine_done_i', 'active_nco_o',
                     'active_start_o', 'active_step_o', 'active_length_o',
                     'active_repeat_o', 'start_o', 'run_enable_o', 'config_valid_o')
            rows.append({'cycle': self.cycles, **{n: int(getattr(d, n).value) for n in names}})
            return result
    b = TranscriptBus(d, int(os.environ['HP']), 1)
    source = json.loads(Path(os.environ['VECTOR_FILE']).read_text())
    assert source['version'] == 1
    for op in source['transactions']:
        b.busy, b.completion = op.get('busy', False), op.get('done', False)
        if op.get('reset'):
            b.busy = b.completion = False
            await b.reset()
        else:
            await b.access(op['address'], op['write'], op['value'], op['select'])
        b.completion = False
        # Architectural state is observed through real bus reads, not hierarchy.
        for address in (R.ADDR_STATUS, R.ADDR_ERROR_STATUS, R.ADDR_CONFIG_SEQUENCE):
            await b.access(address)
    Path(os.environ['TRANSCRIPT_FILE']).write_text(json.dumps(rows, separators=(',', ':'))+'\n')
