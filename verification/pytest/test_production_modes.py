from pathlib import Path
import pytest
from cocotb_tools.runner import get_runner
ROOT=Path(__file__).resolve().parents[2]
SOURCES=['rtl/nco/rf_nco.sv','rtl/nco/rf_nco_high_purity.sv','rtl/nco/rf_nco_mode.sv',
         'rtl/chirp/chirp_controller.sv','rtl/chirp/rf_chirp_nco.sv','rtl/chirp/rf_chirp_nco_mode.sv']
@pytest.mark.parametrize('mode',[0,1])
@pytest.mark.parametrize('top',['rf_nco_mode','rf_chirp_nco_mode'])
def test_modes(mode,top):
    out=ROOT/'build'/f'm5_{top}_{mode}'
    runner=get_runner('verilator')
    runner.build(sources=[ROOT/p for p in SOURCES],includes=[ROOT/'rtl/nco'],
                 hdl_toplevel=top,parameters={'HIGH_PURITY':mode},build_args=['--Wall'],
                 build_dir=out,timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel=top,test_module='verification.cocotb.production_modes',
                extra_env={'MODE':str(mode),'MODE_TOP':top,'PROJECT_ROOT':str(ROOT)},
                seed=5001,log_file=out/'simulation.log')
