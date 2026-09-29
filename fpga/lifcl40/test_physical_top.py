from pathlib import Path
import pytest
from cocotb_tools.runner import get_runner
ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('hb,done',[(6000000,300),(11,2)])
def test_physical_top(hb,done):
    build=ROOT/'build'/f'lifcl40-physical-test-{hb}'
    r=get_runner('verilator')
    r.build(sources=[ROOT/p for p in ['rtl/nco/rf_nco.sv','rtl/chirp/chirp_controller.sv','rtl/chirp/rf_chirp_nco.sv','fpga/lifcl40/physical_top.sv']],includes=[ROOT/'rtl/nco'],hdl_toplevel='physical_top',parameters={'HEARTBEAT_HALF_CYCLES':hb,'CHIRPS_PER_TOGGLE':done},build_args=['--Wall'],build_dir=build,timescale=('1ns','1ps'),log_file=build/'build.log')
    r.test(hdl_toplevel='physical_top',test_module='fpga.lifcl40.physical_top_cocotb',extra_env={'HB_LIMIT':str(hb),'DONE_LIMIT':str(done)},seed=20260927,log_file=build/'simulation.log')
