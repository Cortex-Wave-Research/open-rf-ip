#!/usr/bin/env bash
# Run from repository root. File-only build; never invokes a programmer.
set -euo pipefail
out=build/lifcl40/led_sanity
mkdir -p "$out"
verilator --lint-only --Wall --top-module led_sanity_top \
  fpga/lifcl40/led_sanity_top.sv > "$out/lint.log" 2>&1
verilator --cc --exe --build --Wall --top-module led_sanity_top \
  --Mdir "$out/sim" fpga/lifcl40/led_sanity_top.sv \
  "$PWD/fpga/lifcl40/led_sanity_check.cpp" > "$out/simulation-build.log" 2>&1
"$out/sim/Vled_sanity_top" > "$out/simulation.log"
yosys -l "$out/yosys.log" -p "read_verilog -sv fpga/lifcl40/led_sanity_top.sv; synth_nexus -family lifcl -top led_sanity_top -json $out/synth.json; check -assert; stat"
nextpnr-nexus --device LIFCL-40-9BG400C --json "$out/synth.json" \
  --pdc fpga/lifcl40/led_sanity.pdc --freq 12 --seed 1 \
  --write "$out/routed.json" --fasm "$out/routed.fasm" \
  --report "$out/timing.json" --detailed-timing-report --log "$out/nextpnr.log"
prjoxide pack "$out/routed.fasm" build/lifcl40/led_sanity.bit
prjoxide unpack build/lifcl40/led_sanity.bit "$out/unpacked.fasm"
prjoxide pack "$out/unpacked.fasm" "$out/repacked.bit"
cmp build/lifcl40/led_sanity.bit "$out/repacked.bit"
sha256sum build/lifcl40/led_sanity.bit > "$out/bitstream.sha256"
