"""Run the focused ABI observer regression; no CPU or production source edits."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from cocotb_tools.runner import get_runner
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.control_plane_sources import CONTROL


def run(sim):
    out = ROOT/'build/vexriscv/write-response'/sim
    runner = get_runner(sim)
    runner.build(sources=[ROOT/p for p in CONTROL], hdl_toplevel='openrf_control',
                 parameters={'HIGH_PURITY':0,'ENGINE_KIND':0}, build_dir=out,
                 build_args=['--Wall'] if sim=='verilator' else ['-g2012','-Wall'],
                 timescale=('1ns','1ps'), log_file=out/'build.log')
    runner.test(hdl_toplevel='openrf_control',test_module='verification.cpu.write_response_test',
                test_dir=ROOT, results_xml=str(out/'results.xml'),seed=6201,
                extra_env={'PYTHONPATH':str(ROOT),'OBSERVER_RESULT':str(out/'observations.json')},
                log_file=out/'simulation.log')
    cases=ET.parse(out/'results.xml').findall('.//testcase')
    assert len(cases)==1 and not any(c.tag in ('failure','error','skipped') for c in cases[0]), out
    return json.loads((out/'observations.json').read_text())

if __name__=='__main__':
    sim=sys.argv[1]
    run(sim)
    print(sim, 'write-response regression PASS')
