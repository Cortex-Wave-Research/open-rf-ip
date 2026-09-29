#!/usr/bin/env bash
# Run from repository root. No bitstream packing or programming.
set -euo pipefail
mkdir -p reports/lifcl40 reports/logs
yosys -l reports/logs/lifcl40-yosys.log scripts/synth_lifcl40_nco.ys
for mhz in 12 50 100 150 200; do
    # Timing failure is recorded via exit status; never use --timing-allow-fail.
    status=0
    nextpnr-nexus --device LIFCL-40-9BG400C \
        --json reports/lifcl40/nco-synth.json --pdc fpga/lifcl40/nco.pdc \
        --freq "$mhz" --seed 1 \
        --write "reports/lifcl40/routed-${mhz}.json" \
        --fasm "reports/lifcl40/routed-${mhz}.fasm" \
        --report "reports/lifcl40/timing-${mhz}.json" --detailed-timing-report \
        --log "reports/logs/lifcl40-nextpnr-${mhz}.log" || status=$?
    echo "$status" > "reports/lifcl40/exit-${mhz}.txt"
done
