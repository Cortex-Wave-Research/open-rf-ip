# Verification and reproduction

Run commands from the repository root. Python dependencies are in `requirements-dev.txt`; RTL tests also need Verilator, make, and a C++ compiler. Synthesis needs Yosys; board builds need nextpnr-nexus and Project Oxide. The validated environment used Verilator 5.032, Yosys 0.52, nextpnr 0.11.1-31, Project Oxide 0.1, and cocotb 2.1.0. Dependencies are minimum versions, not an exact environment lockfile.

## Offline numerical and physical-evidence regression

```sh
.venv/bin/python -m pytest -q verification/pytest/test_nco.py verification/pytest/test_nco_lut.py verification/pytest/test_chirp.py fpga/lifcl40/capture/test_format.py analysis/test_hardware_verification.py
.venv/bin/python analysis/plot_hardware_verification.py
.venv/bin/python analysis/plot_captured_chirp_frequency.py
```

The comparison defaults to `examples/physical_capture/`; `--input-dir` selects another capture directory. `--output-dir` selects derived outputs. Inputs are never overwritten. A persistent output manifest rejects later input changes. CSV structure is checked before numerical comparison; raw RFC1 decoding is checked independently against the CSV. Expected samples come from `ChirpModel`, whose amplitude table is mathematically generated without reading RTL constants.

Acceptance requires exactly 1024 records and zero mismatches independently for I, Q, valid, chirp_start, and chirp_end. No sample shifting or tolerance is used. Tests inject malformed CSVs, mismatches, shifted samples, evidence changes, and raw/CSV disagreements. See [capture provenance and SHA256](../examples/physical_capture/README.md).

## RTL regression

```sh
.venv/bin/python -m pytest -q verification/pytest/test_rf_nco.py verification/pytest/test_rf_chirp_nco.py verification/pytest/test_nco_waveform.py
.venv/bin/python -m pytest -q fpga/lifcl40/test_nco_top.py fpga/lifcl40/test_chirp_top.py fpga/lifcl40/test_physical_top.py fpga/lifcl40/capture/test_capture.py
```

Exact comparisons cover fixed tones, all LUT entries, phase wrapping, quadrature, reset, pauses, up/down/zero-step chirps, lengths 0/1/2/long, one-shot, repeat, ignored busy commands, and marker alignment. The simulated 10000-sample chirp matches I/Q and controls exactly. Simulated streams remain distinct from physical evidence.

## LUT, lint, and synthesis

```sh
.venv/bin/python scripts/generate_nco_lut.py --check
verilator --lint-only --Wall --top-module rf_chirp_nco -Irtl/nco rtl/nco/rf_nco.sv rtl/chirp/chirp_controller.sv rtl/chirp/rf_chirp_nco.sv
mkdir -p build reports/chirp reports/logs
yosys -l build/yosys-nco.log scripts/synth_nco.ys
yosys -l build/yosys-chirp.log scripts/synth_chirp.ys
```

Generic synthesis checks portability and structure; generic cells are not FPGA resource estimates. The historical compact regression, strict lint, generic synthesis, LIFCL-40 synthesis, placement, routing, and packing passed before physical validation.

## Offline board build

```sh
bash fpga/lifcl40/build_led_ab.sh
bash fpga/lifcl40/build_native_clock.sh
bash fpga/lifcl40/build_physical.sh
bash fpga/lifcl40/capture/build.sh
```

These scripts build and audit images without programming hardware. The capture build produces `build/lifcl40/capture_readback.bit`. Generated logs, netlists, bitstreams, waveforms, and internal reports stay on disk but are excluded from Git. [Manual programming](lifcl40_manual_programming.md) is a separate operator step.

## Milestone 4 release audit

The public-layout offline regression passed **147 tests**. A further **16 RTL/board test runners passed** using the original compact controller, whose SHA256 matches the pre-integration baseline. This includes the capture/transport simulation and exact chirp comparisons. The published CSV and binary reproduced all 1024 samples with zero I/Q/control mismatches. Both offline plotting commands completed successfully. This release audit did not rebuild FPGA bitstreams or access hardware.
