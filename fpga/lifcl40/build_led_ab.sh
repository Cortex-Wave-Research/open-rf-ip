#!/usr/bin/env bash
# Run from repository root; file-only build, no programmer invocation.
set -euo pipefail
set -x
for variant in A B; do
  swap=0
  if [[ "$variant" == B ]]; then swap=1; fi
  out="build/lifcl40/led_ab/$variant"
  mkdir -p "$out"
  verilator --lint-only --Wall --top-module led_ab_top "-GSWAP=1'b$swap" \
    fpga/lifcl40/led_ab_top.sv > "$out/lint.log" 2>&1
  yosys -l "$out/yosys.log" -p "read_verilog -sv fpga/lifcl40/led_ab_top.sv; chparam -set SWAP $swap led_ab_top; synth_nexus -family lifcl -top led_ab_top -json $out/synth.json; check -assert; stat"
  nextpnr-nexus --device LIFCL-40-9BG400C --json "$out/synth.json" \
    --pdc fpga/lifcl40/static_led.pdc --seed 1 --verbose \
    --write "$out/routed.json" --fasm "$out/routed.fasm" \
    --report "$out/timing.json" --log "$out/nextpnr.log"
  prjoxide pack "$out/routed.fasm" "build/lifcl40/led_ab_$variant.bit"
  prjoxide unpack "build/lifcl40/led_ab_$variant.bit" "$out/unpacked.fasm"
  prjoxide pack "$out/unpacked.fasm" "$out/repacked.bit"
  cmp "build/lifcl40/led_ab_$variant.bit" "$out/repacked.bit"
done
sha256sum build/lifcl40/led_ab_A.bit build/lifcl40/led_ab_B.bit > build/lifcl40/led_ab/bitstreams.sha256
.venv/bin/python fpga/lifcl40/audit_led_ab.py > build/lifcl40/led_ab/audit.log
