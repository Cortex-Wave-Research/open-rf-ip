from pathlib import Path
import pytest
from cocotb_tools.runner import get_runner
from scripts.control_plane_sources import CONTROL, WAVE
ROOT=Path(__file__).resolve().parents[2]

def run(top,hp,kind,test,extra):
    out=ROOT/'build/control_plane'/f'{top}-{hp}-{kind}'
    runner=get_runner('verilator')
    params={'HIGH_PURITY':hp}
    if top=='openrf_control':params['ENGINE_KIND']=kind
    runner.build(sources=[ROOT/p for p in CONTROL+extra],includes=[ROOT/'rtl/nco'],hdl_toplevel=top,parameters=params,build_dir=out,build_args=['--Wall'],timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel=top,test_module=test,extra_env={'HP':str(hp),'KIND':str(kind),'PROJECT_ROOT':str(ROOT)},seed=6101,log_file=out/'simulation.log')

@pytest.mark.parametrize('hp',[0,1])
@pytest.mark.parametrize('kind',[0,1])
def test_csr_bus(hp,kind):run('openrf_control',hp,kind,'verification.cocotb.control_plane',[])

@pytest.mark.parametrize('hp',[0,1])
@pytest.mark.parametrize('kind',[0,1])
def test_controlled_waveform(hp,kind):
    name='openrf_controlled_'+('chirp' if kind else 'nco')
    run(name,hp,kind,'verification.cocotb.control_waveform',WAVE+['rtl/control/'+name+'.sv'])
