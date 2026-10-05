import json
import subprocess
import sys
from pathlib import Path
from scripts.generate_control_registers import render, ROOT
from models.python import control_registers as R

def test_generated_map_current():
    subprocess.run([sys.executable,str(ROOT/'scripts/generate_control_registers.py'),'--check'],check=True)
    spec=json.loads((ROOT/'spec/control_registers.json').read_text())
    assert [r['offset'] for r in spec['registers']]==list(range(0,0x48,4))
    assert R.IP_ID_VALUE==0x4f524649 and R.ABI_VERSION_VALUE==0x10000
    for r in spec['registers']:assert getattr(R,'ADDR_'+r['name'])==r['offset']

def test_generator_detects_stale(tmp_path):
    # Run isolated generator against a stale output, without modifying live sources.
    import shutil
    for name in ('scripts/generate_control_registers.py','spec/control_registers.json',*render()):
        dest=tmp_path/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    (tmp_path/'models/python/control_registers.py').write_text('# stale\n')
    r=subprocess.run([sys.executable,str(tmp_path/'scripts/generate_control_registers.py'),'--check'],capture_output=True,text=True)
    assert r.returncode!=0 and 'Stale generated file' in r.stderr
