from pathlib import Path
from cocotb_tools.runner import get_runner
from verification.pytest.test_production_modes import SOURCES
ROOT=Path(__file__).resolve().parents[3]

def test_transport():
    out=ROOT/'build/lifcl40/hp-capture-transport'
    runner=get_runner('verilator')
    runner.build(sources=[ROOT/p for p in ['fpga/lifcl40/capture/capture_i2c.sv',
        'fpga/lifcl40/high_purity_capture/hp_capture_store.sv','fpga/lifcl40/high_purity_capture/hp_capture_sim.sv']],
        hdl_toplevel='hp_capture_sim',build_dir=out,build_args=['--Wall'],timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel='hp_capture_sim',test_module='fpga.lifcl40.high_purity_capture.transport_cocotb',log_file=out/'simulation.log')


def test_integration():
    out=ROOT/'build/lifcl40/hp-capture-integration'
    runner=get_runner('verilator')
    sources=SOURCES+['fpga/lifcl40/capture/capture_i2c.sv','fpga/lifcl40/high_purity_capture/hp_capture_store.sv','fpga/lifcl40/high_purity_capture/high_purity_capture_top.sv']
    runner.build(sources=[ROOT/p for p in sources],includes=[ROOT/'rtl/nco'],hdl_toplevel='high_purity_capture_top',
        build_dir=out,build_args=['--Wall'],timescale=('1ns','1ps'),log_file=out/'build.log')
    runner.test(hdl_toplevel='high_purity_capture_top',test_module='fpga.lifcl40.high_purity_capture.integration_cocotb',log_file=out/'simulation.log')
