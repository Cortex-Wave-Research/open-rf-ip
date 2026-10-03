#!/usr/bin/env bash
# Run from repository root. Builds only; never accesses USB or programs hardware.
set -euo pipefail
out=build/lifcl40/high_purity_capture
mkdir -p "$out"
sha256sum rtl/nco/rf_nco.sv rtl/chirp/chirp_controller.sv rtl/chirp/rf_chirp_nco.sv > "$out/production-before.sha256"
sources='rtl/nco/rf_nco.sv rtl/nco/rf_nco_high_purity.sv rtl/nco/rf_nco_mode.sv rtl/chirp/chirp_controller.sv rtl/chirp/rf_chirp_nco.sv rtl/chirp/rf_chirp_nco_mode.sv fpga/lifcl40/high_purity_capture/hp_capture_store.sv fpga/lifcl40/capture/capture_i2c.sv fpga/lifcl40/high_purity_capture/high_purity_capture_top.sv'
verilator --lint-only --Wall -Irtl/nco --top-module high_purity_capture_top $sources > "$out/lint.log" 2>&1
yosys -l "$out/yosys.log" -p "read_verilog -defer -sv -Irtl/nco $sources; hierarchy -check -top high_purity_capture_top; proc; flatten; opt; memory_collect; synth_nexus -family lifcl -top high_purity_capture_top -json $out/synth.json; check -assert; stat" > "$out/synthesis-console.log" 2>&1
nextpnr-nexus --device LIFCL-40-9BG400C --json "$out/synth.json" --pdc fpga/lifcl40/capture/capture.pdc --freq 12 --seed 1 --verbose --write "$out/routed.json" --fasm "$out/routed.fasm" --report "$out/timing.json" --detailed-timing-report --log "$out/nextpnr.log" > "$out/route-console.log" 2>&1
# nextpnr does not implement ldc_set_sysconfig. Explicit Oxide database settings:
cp "$out/routed.fasm" "$out/packed.fasm"
cat >> "$out/packed.fasm" <<'FASM'
CIB_R0C77__EFB_1_OSC.SYSCONFIG.SLAVE_I2C_PORT.DISABLE
CIB_R0C75__EFB_0.SYSCONFIG.SLAVE_I3C_PORT.DISABLE
CIB_R0C77__EFB_1_OSC.SYSCONFIG.SLAVE_SPI_PORT.DISABLE
CIB_R0C77__EFB_1_OSC.CONFIG_IP_CORE.MCPERSISTUI2C.DIS
FASM
prjoxide pack "$out/packed.fasm" build/lifcl40/high_purity_capture.bit
prjoxide unpack build/lifcl40/high_purity_capture.bit "$out/unpacked.fasm"
sha256sum build/lifcl40/high_purity_capture.bit > "$out/bitstream.sha256"
sha256sum -c "$out/production-before.sha256" > "$out/production-unchanged.log"
prjoxide pack "$out/unpacked.fasm" "$out/repacked.bit"
cmp build/lifcl40/high_purity_capture.bit "$out/repacked.bit"
.venv/bin/python fpga/lifcl40/high_purity_capture/audit.py > "$out/audit.log"
