"""Run explicitly: .venv/bin/python -m pytest -q fpga/lifcl40/test_nco_top.py."""
from pathlib import Path
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[2]


def test_nco_top():
    build = ROOT / "build/lifcl40-wrapper"
    runner = get_runner("verilator")
    runner.build(
        sources=[ROOT / "rtl/nco/rf_nco.sv", ROOT / "fpga/lifcl40/nco_top.sv"],
        includes=[ROOT / "rtl/nco"], hdl_toplevel="nco_top",
        build_args=["--Wall"], build_dir=build, timescale=("1ns", "1ps"),
        log_file=build / "build.log",
    )
    runner.test(
        hdl_toplevel="nco_top", test_module="fpga.lifcl40.nco_top_cocotb",
        seed=20260923, log_file=build / "simulation.log",
    )
