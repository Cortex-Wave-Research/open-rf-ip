#!/usr/bin/env bash
# Run from repository root. Build files only; NEVER invokes a programmer.
set -euo pipefail
mkdir -p build/lifcl40 reports/lifcl40_preflight
# Regression/lint must pass before packing. Existing tests are run separately
# and recorded in reports/lifcl40_preflight/regression.log.
yosys -l build/lifcl40/yosys.log fpga/lifcl40/synth_physical.ys
nextpnr-nexus --device LIFCL-40-9BG400C --json build/lifcl40/physical-synth.json \
  --pdc fpga/lifcl40/physical.pdc --freq 12 --seed 1 \
  --write build/lifcl40/physical-routed.json --fasm build/lifcl40/physical.fasm \
  --report build/lifcl40/timing.json --detailed-timing-report \
  --log build/lifcl40/nextpnr.log
.venv/bin/python -m fpga.lifcl40.audit_physical
prjoxide pack build/lifcl40/physical.fasm build/lifcl40/chirp_liveness.bit
prjoxide unpack build/lifcl40/chirp_liveness.bit build/lifcl40/unpacked.fasm
prjoxide pack build/lifcl40/unpacked.fasm build/lifcl40/repacked.bit
cmp build/lifcl40/chirp_liveness.bit build/lifcl40/repacked.bit
sha256sum build/lifcl40/chirp_liveness.bit > build/lifcl40/bitstream.sha256
