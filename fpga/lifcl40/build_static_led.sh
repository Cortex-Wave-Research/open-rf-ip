#!/usr/bin/env bash
# Run from repository root. Build files only; never invokes a programmer.
set -euo pipefail
set -x
out=build/lifcl40/static_led
mkdir -p "$out"
verilator --lint-only --Wall --top-module static_led_top \
  fpga/lifcl40/static_led_top.sv > "$out/lint.log" 2>&1
yosys -l "$out/yosys.log" -p "read_verilog -sv fpga/lifcl40/static_led_top.sv; synth_nexus -family lifcl -top static_led_top -json $out/synth.json; check -assert; stat"
# No --freq or clock constraint: this design has no clock or sequential paths.
nextpnr-nexus --device LIFCL-40-9BG400C --json "$out/synth.json" \
  --pdc fpga/lifcl40/static_led.pdc --seed 1 --verbose \
  --write "$out/routed.json" --fasm "$out/routed.fasm" \
  --report "$out/timing.json" --log "$out/nextpnr.log"
prjoxide pack "$out/routed.fasm" build/lifcl40/static_led.bit
prjoxide unpack build/lifcl40/static_led.bit "$out/unpacked.fasm"
prjoxide pack "$out/unpacked.fasm" "$out/repacked.bit"
cmp build/lifcl40/static_led.bit "$out/repacked.bit"
sha256sum build/lifcl40/static_led.bit > "$out/bitstream.sha256"
.venv/bin/python fpga/lifcl40/audit_static_led.py > "$out/audit.log"
