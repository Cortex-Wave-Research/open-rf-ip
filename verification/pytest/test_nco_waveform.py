"""Generate the small FST inspection artifact using the production RTL."""

from pathlib import Path

from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[2]


def test_inspection_waveform():
    build_dir = ROOT / "build/nco_inspect"
    waveform = ROOT / "waveforms/rf_nco.fst"
    waveform.parent.mkdir(parents=True, exist_ok=True)
    runner = get_runner("verilator")
    runner.build(
        sources=[ROOT / "rtl/nco/rf_nco.sv"],
        includes=[ROOT / "rtl/nco"],
        hdl_toplevel="rf_nco",
        build_args=["--Wall", "--trace-fst"],
        build_dir=build_dir,
        timescale=("1ns", "1ps"),
        waves=True,
        log_file=build_dir / "build.log",
    )
    runner.test(
        hdl_toplevel="rf_nco",
        test_module="verification.cocotb.nco_inspect",
        extra_env={"NCO_PHASE_WIDTH": "32", "NCO_OUTPUT_WIDTH": "14", "NCO_LUT_ADDR_WIDTH": "10"},
        seed=20260921,
        waves=True,
        test_args=["--trace-file", str(waveform)],
        log_file=build_dir / "simulation.log",
    )
    assert 0 < waveform.stat().st_size < 1_000_000, "Expected a small, nonempty FST capture"
