# Production compact and high-purity NCO modes

Milestone 5 adds Candidate C as an elaboration-time selectable production mode.
It retains the physically validated compact datapath and its numerical contract.
Milestone 5A also physically validates the high-purity mode; see the
[physical evidence and reproduction](high_purity_physical_validation.md).

## Interfaces and selection

The existing `rf_nco` and `rf_chirp_nco` modules and compact LUT are unchanged.
Existing designs retain their source lists and interfaces. New designs can use
`rf_nco_mode` or `rf_chirp_nco_mode`, both with integer `HIGH_PURITY=0` by default.
Set `HIGH_PURITY=1` at elaboration for Candidate C. Only the selected branch is
synthesized; generic netlist audits require exactly one shared dual-read ROM.
There is no runtime mode switch, runtime output mux, or simultaneously instantiated
compact/high-purity datapath. Original parameterized `rf_nco` remains available
for its previously supported width combinations; the new mode wrappers deliberately
support only the two product configurations below.

| Property | COMPACT (`HIGH_PURITY=0`) | HIGH_PURITY (`HIGH_PURITY=1`) |
|---|---|---|
| `PHASE_WIDTH` | 32 | 64 |
| `OUTPUT_WIDTH` | 14 | 18 |
| Effective phase address | 10 bits | 16 bits |
| Output range | −8191…8191 | −131071…131071 |
| Logical ROM | 1024 × 14 full sine | 16384 × 17 quarter magnitudes |
| NCO pipeline stages | 1 | 2 |
| Dither | Off | Off |

`PHASE_WIDTH` and `OUTPUT_WIDTH` default from the mode. Invalid combinations
are rejected during elaboration; no implicit narrowing of high-purity words is
allowed. NCO ports remain clk, rst, enable, phase_increment, i_out, q_out,
sample_valid; mode-specific widths are explicit. Chirp wrappers retain the existing
control/data port names, with 64-bit start_phase_inc, signed chirp_step, and
phase_increment in high-purity mode. Length/count remain unsigned 32 bits.

Compile production sources (include path `rtl/nco`):

```
rtl/nco/rf_nco.sv
rtl/nco/rf_nco_high_purity.sv
rtl/nco/rf_nco_mode.sv
rtl/chirp/chirp_controller.sv
rtl/chirp/rf_chirp_nco.sv
rtl/chirp/rf_chirp_nco_mode.sv
```

Example: `rf_chirp_nco_mode #(.HIGH_PURITY(1)) chirp (...)` with explicitly
64-bit unsigned start and 64-bit signed step signals. Old compact-only builds
still need only their original three source modules.

## Numerical mapping and reproducible ROM

High-purity phase is unsigned modulo 2^64. Each admitted sample uses the phase
before increment; all low 48 bits remain in the accumulator but are discarded for
amplitude lookup. I is cosine, Q sine. I address is Q address plus 16384 modulo
65536, exactly one quarter turn on the amplitude grid.

ROM magnitudes are `round_nearest_ties_away(131071 * sin(pi*k/32768))` for
`k=0…16383`. A second/fourth quadrant reflects the 14-bit offset, and the upper
phase bit supplies the sign. The exact quarter-turn endpoint bypasses address zero
and uses 131071. Positive magnitudes are zero-extended to signed 18 bits before
negation. The asymmetric signed minimum −131072 is unused. Arithmetic truncation
is documented explicitly in RTL; neither saturation nor hidden scaling is used.

Run `.venv/bin/python scripts/generate_high_purity_lut.py` to regenerate
`rtl/nco/high_purity_quarter.svh`, or add `--check` to verify it without modification.
The generator uses 70-digit Decimal Taylor sine and positive ties-away rounding.
It shares mathematical helper code with the old offline generator, never the
verification model. No real arithmetic, external readmem path, vendor primitive,
interpolator, or runtime multiplier is present in the reusable implementation.
The checked-in generated header is required by synthesis, following the compact LUT precedent.
Its SHA256 is `a3e1227bf9eb206344441ea1b520c47fbab3e8d825f0d1f94c412f7f198aff7c`.

`models/python/high_purity.py` independently computes the quarter table using
binary64 math. Tests also compare every one of 65536 phase addresses against
direct full-wave sine/cosine, including all cardinal boundaries and wraparound.
The model reads no RTL constants. Original compact reference files are unchanged.

## Latency and pause contract

The documented mode constant is `NCO_LATENCY = HIGH_PURITY ? 2 : 1`, measured
as active rising edges including the edge admitting the phase sample. This is
not an extra delay of two clocks after admission: high-purity output appears at
the next enabled edge after its ROM-read edge.

| Event, continuous enable | Compact | High-purity |
|---|---|---|
| Start accepted at edge E0 | No sample | No sample |
| Phase P0 admitted | E1 | E1 (ROM read) |
| I/Q sample 0 valid, chirp_start | E1 | E2 (sign/peak reconstruction) |
| Subsequent samples | One per enabled edge | One per enabled edge |
| Final sample/end marker | Final admission edge | Next enabled edge after final admission |
| Disabled edge | Hold I/Q and phase, clear valid/markers | Hold I/Q, phase and pending sample/markers; clear valid/markers |
| Reset edge | Clear state and I/Q | Clear both stages, scheduler, I/Q and markers |

Latencies are deliberately **not normalized**: adding a compact output stage
would alter already physically validated behavior. Applications must respect the
mode latency. Phase and increment are admitted together; valid and both markers
refer to the same output I/Q pair on every clock.

The low-level `rf_nco_high_purity` has separate `enable` (advance pipeline) and
`sample_enable` (admit phase/word) inputs. A disabled global enable freezes both
stages and does not discard pending samples. With global enable high but no input
sample, the pending sample drains once; I/Q then holds with valid low. The tone
wrapper fixes sample_enable=1. The chirp composition uses the controller's
nco_enable, allowing finite chirps to drain without emitting invented tail samples.

`chirp_controller` now has `PHASE_WIDTH=32` and `MARKER_DELAY=0` defaults.
High-purity composition selects 64 and 1. Pending start/end markers hold during
pause and drain with the data stage. Scheduler busy/count/increment are deliberately
not delayed: they still describe scheduling state, not output-sample metadata.
High-purity busy can drop one enabled edge before the final valid/end pair appears.
A new start can be accepted while that prior pair drains, without a phase reset.

## Chirp arithmetic

Start and step are genuinely 64-bit in high-purity mode. Word progression is
`W[k]=(start_word + k*signed_step) mod 2^PHASE_WIDTH`, with explicit unsigned
reinterpretation of the signed two's-complement step at modular addition.
No zero-extension of 32-bit chirp arithmetic is used. Counters/length remain
32 bits; zero length is rejected, length one emits start and end together.
Reset, ignored busy starts/config changes, nonqueued disabled starts, held-start
rearming, repeat, phase continuity, and enable pause retain their prior meaning.
Configuration is latched at acceptance.

Python uses rational nearest/ties-away rounding for both start and per-sample
step, with N−1 intervals between requested endpoints. No endpoint correction is
introduced. The 2→20 MHz, 100 MHz, 10000-sample demonstration is recomputed in
the generated `reports/high_purity_integration/spectral.json` by
`analysis/high_purity_integration.py`, including exact rational errors. The
high-purity endpoint error is +2.09131757e-8 Hz; compact is −33.299438655 Hz.

## Verification and measured limits

The implementation is tested with full address-grid traversal, ten tuning words
including awkward coherent bins and full-width values, 10000-sample tones/chirps,
30000 consecutive repeat samples, signed-step extremes, accumulator/word wrap,
random resets/pauses, length 0/1/2, long chirps, and max-length prefixes. A complete
2^32−1-sample chirp is not simulated. Exact assertions cover I/Q, valid, markers,
internal phase, scheduled word/count, and busy. Compact RTL is additionally
compared against the saved physical 1024-record CSV.

Numerical digital SFDR is measured over the same 72 coherent complex tones as Milestone
3.5: 2^20 samples per tone, rectangular FFT, all noncarrier bins including DC and
negative frequencies searched. Production-model amplitude mapping is separately
exhaustively checked against RTL. Worst measured high-purity SFDR is about
92.407 dBc, median 96.274 dBc. This is a finite tested set, not a universal tuning-
word guarantee, analog phase noise, or RF performance claim. Dither stays off.
A spur-unresolved Fs/4 tone is reported as unresolved, not infinite performance.

Equivalent constant-tone harnesses use 1/16 EBRs and zero DSPs for compact/high-
purity respectively. Production results on LIFCL-40-9BG400C, seed 1:

| Harness | COMB | FF | EBR | DSP | Routed Fmax | Slack at 100 MHz |
|---|---:|---:|---:|---:|---:|---:|
| Compact NCO | 50 | 38 | 1 | 0 | 195.351 MHz | +4.881 ns |
| High-purity NCO | 482 | 117 | 16 | 0 | 124.208 MHz | +1.949 ns |
| Compact chirp | 218 | 106 | 1 | 0 | 199.243 MHz | +4.981 ns |
| High-purity chirp | 632 | 219 | 16 | 0 | 127.049 MHz | +2.129 ns |

These constant-control harnesses retain the production datapaths but allow
specialization; they do not measure a fully programmable FPGA interface or a
physical maximum clock. High-purity NCO passes 12/50/100 MHz constraints and fails
125/150 MHz timing without relaxed constraints. The complete RFC2 capture wrapper
is separate: 1045 COMB / 269 FF / 19 EBR / 0 DSP, 91.266 MHz routed Fmax and
+72.376 ns slack at its actual 12 MHz clock. It is not a 100 MHz capture-wrapper claim.
Strict Verilator lint, Yosys checks, P&R and pack/unpack/repack passed in Milestone 5.
These historical synthesis results were not rebuilt for the publication commit.
Generic synthesis keeps ROMs as portable memories for a fair four-design comparison;
its word-level cell counts are not LUT or flattened gate counts.

## Physically validated RFC2 capture

`fpga/lifcl40/high_purity_capture/high_purity_capture_top.sv` taps the first 1024
consecutive valid samples starting at chirp_start, freezes permanently, and signals
a sticky error if valid drops mid-capture. The board configuration is 500 kHz→2 MHz
at the native 12 MHz clock, 10000 samples, repeat off, held start. Wide words are
768614336404564651 and +230607361657535, calculated from the Python helper.
The operator manually loaded the image and read 1024 records. Offline comparison
proves exact I/Q/control agreement; see the [physical record](high_purity_physical_validation.md).

RFC1 capture RTL/decoder and physical evidence remain unchanged. A new pure
`capture_format.py` decoder supports RFC1 by delegation and RFC2 directly;
`read_capture_v2.py` supports either version, explicitly selected hardware access
via `--url` or offline decoding via `--input`. Output paths must be new.

RFC2 image is 5136 bytes: 16-byte header plus 1024 five-byte records.

| Header offset | Meaning |
|---|---|
| 0…3 | ASCII RFC2 |
| 4 | Version 2 |
| 5 | Bit0 done, bit1 gap error; remaining bits zero |
| 6…7 | Count 1024, little endian |
| 8 | Five bytes per record |
| 9 | Signed component width 18 |
| 10…15 | Reserved zero |

Record k begins at byte 16+5k. The little-endian 40-bit word contains I[17:0],
Q[35:18], valid[36], chirp_start[37], chirp_end[38], reserved[39]=0. I/Q are signed
18-bit two's complement; there is no narrowing. RAM stores 39 meaningful bits per
sample: 39936 bits total, mapping to three EBRs. The wire representation uses
40960 payload bits. NCO ROM adds 16 EBRs, total wrapper 19. This is the minimum
EBR count by capacity for 39-bit capture records.

Transport is the unchanged 25 kHz FT2232H-B I²C target, address 0x2A, two-byte
big-endian byte pointer, 13-bit address space. Packed five-byte addressing uses
an exactly proven 13-bit divide-by-five reciprocal built from shifts/adds, avoiding
a large generic divider or DSP. The proof is in the store RTL. Synchronous RAM
read latency still fits the existing transport's pointer/read sequencing.
The reader decodes the header, reads the size in 64-byte chunks twice, rejects
disagreement, and saves raw binary plus CSV. Equal reads alone do not prove
numerical correctness. Existing saved RFC1 binary and CSV decode identically.

Known board pins/polarity remain L13 clock, F20 SCL, E20 SDA, E17/D3 done and
F13/D4 error. LEDs are active-low: expected D3 ON, D4 OFF after capture.
JP2 shorted, JP1 open. SRAM loading rearms; board power loss clears configuration
and RAM. The operator used temporary SRAM loading; no persistent flash write
is required. Hardware access and programming remain separate manual actions.

## Reproduce offline

See [verification commands](verification.md#milestone-5--5a-offline-reproduction)
for the 87-test regression, pure evidence comparison, spectral study, and optional
synthesis/build audits. Generated bitstreams and bulk reports remain local.
No parallel lanes, CPU, 400 MHz architecture or analog/RF hardware is introduced.
