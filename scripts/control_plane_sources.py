"""Shared, dependency-free source manifests for control simulation and synthesis.

Paths are relative to the repository root. The package must precede its users;
the existing waveform modules are reused without modifying their implementations.
"""

CONTROL = [
    "rtl/control/openrf_control_pkg.sv",
    "rtl/control/openrf_wb_slave.sv",
    "rtl/control/openrf_csr_core.sv",
    "rtl/control/openrf_control.sv",
]

WAVE = [
    "rtl/nco/rf_nco.sv",
    "rtl/nco/rf_nco_high_purity.sv",
    "rtl/nco/rf_nco_mode.sv",
    "rtl/chirp/chirp_controller.sv",
    "rtl/chirp/rf_chirp_nco.sv",
    "rtl/chirp/rf_chirp_nco_mode.sv",
]

WRAPPERS = [
    "rtl/control/openrf_controlled_nco.sv",
    "rtl/control/openrf_controlled_chirp.sv",
]
