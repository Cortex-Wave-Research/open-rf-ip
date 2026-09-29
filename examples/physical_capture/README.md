# Physical compact chirp capture

These files are unchanged copies of one physical LIFCL-40-EVN capture reported by the operator on 2026-09-29. They are not simulation output. Board configuration: LIFCL-40-9BG400C, native 12 MHz clock, JP2 shorted, JP1 open; compact NCO with 32-bit phase, 10-bit LUT address and signed 14-bit I/Q.

The one-shot chirp uses start word 178956971, signed step +53692, length 10000, and reset phase zero. RAM stores 1024 consecutive valid samples beginning with the first chirp_start. FT2232H channel-B I²C retrieves the frozen RFC1 image. The host reader reported “Saved 1024 samples …; no numerical correctness claim.” The separate independent Python comparison then established **BIT-EXACT PASS**: zero I/Q/control mismatches, zero alignment shift, and zero maximum/RMS I/Q error. Raw binary decoding exactly matches the CSV.

| File | Bytes | SHA256 |
| --- | --- | --- |
| `capture_1024.csv` | 22307 | `838cea308f4670e01a06aa13fcae285304edb8e953b948e3c67764cd3843ff76` |
| `capture_1024.bin` | 4112 | `01588b97134f0fd15e7bb73dc4164e59adc20ae0d983de08ec3899d860910d8c` |

CSV: 1025 lines including header; 1024 records with columns `index,I,Q,valid,chirp_start,chirp_end`. Do not edit these evidence files. Original working copies remain preserved separately.

From the repository root, after installing `requirements-dev.txt`:

```sh
sha256sum examples/physical_capture/capture_1024.csv examples/physical_capture/capture_1024.bin
.venv/bin/python analysis/plot_hardware_verification.py
```

The command validates structure, regenerates the independent reference, compares all five fields, cross-checks raw decoding, and writes derived CSV/JSON/figures to `reports/hardware_verification/`. It never accesses hardware. The [physical validation document](../../docs/physical_validation.md) defines RFC1 packing and the limits of this result. This is a digital prefix validation, not analog/RF measurement or proof of the uncaptured remainder.
