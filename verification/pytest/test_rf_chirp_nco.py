"""Controller alone, composition regression, and short trace runs."""
from pathlib import Path
import pytest
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('top,trace', [('chirp_controller', False),
                                      ('rf_chirp_nco', False), ('rf_chirp_nco', True)])
def test_chirp_rtl(top, trace):
    build = ROOT / 'build' / (top + ('_inspect' if trace else '_regression'))
    sources = [ROOT / 'rtl/chirp/chirp_controller.sv']
    if top == 'rf_chirp_nco':
        sources += [ROOT / 'rtl/nco/rf_nco.sv', ROOT / 'rtl/chirp/rf_chirp_nco.sv']
    runner = get_runner('verilator')
    runner.build(sources=sources, includes=[ROOT / 'rtl/nco'], hdl_toplevel=top,
                 build_args=['--Wall'] + (['--trace-fst'] if trace else []),
                 build_dir=build, timescale=('1ns', '1ps'), waves=trace,
                 log_file=build / 'build.log')
    waveform = ROOT / 'waveforms/rf_chirp_nco.fst'
    waveform.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'reports/chirp').mkdir(parents=True, exist_ok=True)
    runner.test(hdl_toplevel=top,
                test_module='verification.cocotb.chirp_inspect' if trace else 'verification.cocotb.chirp_cocotb',
                extra_env={'CHIRP_SAMPLE_CSV': str(ROOT / 'reports/chirp/demo_rtl_samples.csv')},
                seed=20260923, waves=trace,
                test_args=['--trace-file', str(waveform)] if trace else [],
                log_file=build / 'simulation.log')
    if trace:
        assert 0 < waveform.stat().st_size < 1_000_000
