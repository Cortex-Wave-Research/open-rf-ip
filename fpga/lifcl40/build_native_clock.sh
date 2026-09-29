#!/usr/bin/env bash
# Repository root; build/simulation only, no programming.
set -euo pipefail
set -x
out=build/lifcl40/native_clock_test
mkdir -p "$out"
verilator --lint-only --Wall --top-module native_clock_test_top fpga/lifcl40/native_clock_test_top.sv > "$out/lint.log" 2>&1
verilator --cc --exe --build --Wall --top-module native_clock_test_top \
  --Mdir "$out/sim" fpga/lifcl40/native_clock_test_top.sv \
  "$PWD/fpga/lifcl40/native_clock_check.cpp" > "$out/simulation-build.log" 2>&1
"$out/sim/Vnative_clock_test_top" > "$out/simulation.log"
yosys -l "$out/yosys.log" -p "read_verilog -sv fpga/lifcl40/native_clock_test_top.sv; synth_nexus -family lifcl -top native_clock_test_top -json $out/synth.json; check -assert; stat"
nextpnr-nexus --device LIFCL-40-9BG400C --json "$out/synth.json" \
  --pdc fpga/lifcl40/native_clock_test.pdc --freq 12 --seed 1 --verbose \
  --write "$out/routed.json" --fasm "$out/routed.fasm" \
  --report "$out/timing.json" --detailed-timing-report --log "$out/nextpnr.log"
prjoxide pack "$out/routed.fasm" build/lifcl40/native_clock_test.bit
prjoxide unpack build/lifcl40/native_clock_test.bit "$out/unpacked.fasm"
prjoxide pack "$out/unpacked.fasm" "$out/repacked.bit"
cmp build/lifcl40/native_clock_test.bit "$out/repacked.bit"
sha256sum build/lifcl40/native_clock_test.bit > "$out/bitstream.sha256"
.venv/bin/python fpga/lifcl40/audit_native_clock.py > "$out/audit.log"
