from pathlib import Path
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[2]


def test_chirp_top():
    build = ROOT / 'build/lifcl40-chirp-wrapper'
    runner = get_runner('verilator')
    runner.build(sources=[ROOT / p for p in ['rtl/nco/rf_nco.sv',
                 'rtl/chirp/chirp_controller.sv', 'rtl/chirp/rf_chirp_nco.sv',
                 'fpga/lifcl40/chirp_top.sv']], includes=[ROOT / 'rtl/nco'],
                 hdl_toplevel='chirp_top', build_args=['--Wall'], build_dir=build,
                 timescale=('1ns','1ps'), log_file=build / 'build.log')
    runner.test(hdl_toplevel='chirp_top', test_module='fpga.lifcl40.chirp_top_cocotb',
                seed=20260923, log_file=build / 'simulation.log')
