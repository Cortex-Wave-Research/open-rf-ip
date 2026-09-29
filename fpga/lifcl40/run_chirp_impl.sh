#!/usr/bin/env bash
# Reuse validated native clock/LED pins. No hardware programming or bitstream pack.
set -euo pipefail
mkdir -p reports/chirp reports/logs
yosys -l reports/logs/m3-lifcl40-yosys.log scripts/synth_lifcl40_chirp.ys
for mhz in 12 50 100 150 200; do
    status=0
    nextpnr-nexus --device LIFCL-40-9BG400C \
        --json reports/chirp/lifcl40-synth.json --pdc fpga/lifcl40/nco.pdc \
        --freq "$mhz" --seed 1 \
        --write "reports/chirp/routed-${mhz}.json" \
        --fasm "reports/chirp/routed-${mhz}.fasm" \
        --report "reports/chirp/timing-${mhz}.json" --detailed-timing-report \
        --log "reports/logs/m3-nextpnr-${mhz}.log" || status=$?
    echo "$status" > "reports/chirp/exit-${mhz}.txt"
done
