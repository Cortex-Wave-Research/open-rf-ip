from pathlib import Path
from cocotb_tools.runner import get_runner
ROOT = Path(__file__).resolve().parents[3]
def test_capture():
    out = ROOT / 'build/lifcl40/capture-simulation'
    runner = get_runner('verilator')
    runner.build(sources=[ROOT/'fpga/lifcl40/capture'/name for name in
        ['capture_store.sv','capture_i2c.sv','sim_top.sv']], hdl_toplevel='sim_top',
        build_dir=out, build_args=['--Wall'], timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel='sim_top', test_module='fpga.lifcl40.capture.capture_cocotb',
        log_file=out/'simulation.log')

def test_integrated_capture():
    out = ROOT / 'build/lifcl40/capture-integration'
    runner = get_runner('verilator')
    sources=['rtl/nco/rf_nco.sv','rtl/chirp/chirp_controller.sv','rtl/chirp/rf_chirp_nco.sv']
    sources += ['fpga/lifcl40/capture/'+n for n in ['capture_store.sv','capture_i2c.sv','capture_readback_top.sv']]
    runner.build(sources=[ROOT/p for p in sources],includes=[ROOT/'rtl/nco'],
        hdl_toplevel='capture_readback_top', build_dir=out, build_args=['--Wall'],
        timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel='capture_readback_top',test_module='fpga.lifcl40.capture.integration_cocotb',log_file=out/'simulation.log')
