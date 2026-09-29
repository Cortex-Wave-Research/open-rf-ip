"""Build portable RTL and run cocotb through pytest; missing tools fail visibly."""

from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("phase_bits,output_bits,address_bits", [
    (32, 14, 2), (32, 14, 10), (32, 14, 12),
    (16, 8, 8), (64, 16, 8), (12, 2, 12),
])
def test_rf_nco(phase_bits, output_bits, address_bits):
    build_dir = ROOT / "build" / f"nco_p{phase_bits}_o{output_bits}_a{address_bits}"
    runner = get_runner("verilator")
    runner.build(
        sources=[ROOT / "rtl/nco/rf_nco.sv"],
        includes=[ROOT / "rtl/nco"],
        hdl_toplevel="rf_nco",
        parameters={"LUT_ADDR_WIDTH": address_bits, "PHASE_WIDTH": phase_bits, "OUTPUT_WIDTH": output_bits},
        build_args=["--Wall"],
        build_dir=build_dir,
        timescale=("1ns", "1ps"),
        log_file=build_dir / "build.log",
    )
    runner.test(
        hdl_toplevel="rf_nco",
        test_module="verification.cocotb.nco_cocotb",
        extra_env={
            "NCO_LUT_ADDR_WIDTH": str(address_bits),
            "NCO_PHASE_WIDTH": str(phase_bits),
            "NCO_OUTPUT_WIDTH": str(output_bits),
        },
        seed=20260921,
        log_file=build_dir / "simulation.log",
    )
