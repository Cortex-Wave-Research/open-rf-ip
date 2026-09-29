# Fixed-frequency NCO: Milestone 2

Verification commands and scope: [Verification](verification.md).

`rtl/nco/rf_nco.sv` is a vendor-independent, one-sample-per-enabled-clock NCO.
The separate chirp controller composes this core. By default it uses a 32-bit unsigned accumulator
and signed 14-bit I/Q outputs. The clock frequency equals the complex sample rate when
enable is continuously high. The core has no physical-frequency parameter.

## Parameters, interface and timing

| Parameter | Default | Supported range |
| --- | --- | --- |
| `PHASE_WIDTH` (P) | 32 | LUT_ADDR_WIDTH through 64 |
| `OUTPUT_WIDTH` (B) | 14 | 2 through 16 |
| `LUT_ADDR_WIDTH` (A) | 10 | 2 through 12 |

The bounds keep the committed master grid and constant arithmetic finite and
explicit. The standard 32-bit phase arithmetic agrees with the unchanged ideal
Python model; alternative widths generalize the same modulo arithmetic.

| Port | Meaning |
| --- | --- |
| `clk` | Rising-edge sample clock |
| `rst` | Active-high synchronous reset; takes priority over enable |
| `enable` | Advance and produce a sample on this edge |
| `phase_increment[P-1:0]` | Unsigned tuning word, sampled on each enabled edge |
| `i_out`, `q_out` | Registered signed B-bit two's-complement samples |
| `sample_valid` | High after an enabled, non-reset edge; otherwise low |

On reset, phase, I, Q, and valid become zero. No state is assumed before a reset
edge. On each enabled edge, output the lookup for the **old** phase and advance
phase by the input increment modulo 2^P. Therefore the first enabled edge after
reset produces `(2^(B-1)-1, 0)`, or `(8191, 0)` by default, with valid high. There is one registered lookup stage,
no additional startup bubbles, and one pair per clock under continuous enable.
An increment change at an edge affects the next enabled sample's phase, not the
sample registered at that edge.

When disabled, phase and I/Q hold; valid goes low. Resumption uses the frozen
phase. This pauses the discrete sample sequence rather than tracking elapsed
wall-clock phase. Irregular enable patterns are not a uniformly sampled tone
at the clock rate. Reset is the only operation that restarts phase.

## Phase and amplitude quantization

For address width A, with `2 <= A <= 12` (default A=10):

```
N = 2^A
peak = 2^(B-1) - 1
q_address = floor(phase / 2^(P-A))
i_address = (q_address + N/4) mod N
sine[k] = round_away(peak * sin(2*pi*k/N))
I = sine[i_address]
Q = sine[q_address]
phase_next = (phase + phase_increment) mod 2^P
```

`round_away` means nearest integer, with exact half ties away from zero. There is
no interpolation or address rounding. Discarding low bits applies only to the
LUT address; all P accumulator bits remain live. Both modular additions in RTL
use explicit width casts. Positive frequency rotates from +I toward +Q.

The table spans `-peak` through `+peak`, or -8191 through +8191 by default.
The two's-complement word is `sample mod 2^B`, held in a signed B-bit ROM/output.
Default-width encoding examples:
zero = `0000`, +8191 = `1fff`, -8191 = `2001`; code `2000` (-8192) is unused.
I and Q read the same sine array at different addresses. There are two read
ports; a target tool may implement them with memory or logic, or duplicate ROM
storage. The generic source makes no block-RAM or technology mapping promise.

Frequency resolution remains fs/2^P regardless of A. Increasing A improves
phase-to-amplitude resolution at a ROM cost of `B * 2^A` bits. The default
table contains 14,336 bits; A=12 and B=14 contain 57,344 bits. Phase quantization is less
than one address bin (2*pi/2^A radians). It introduces waveform error and spurs;
these tests establish functional correctness, not a measured SFDR specification.

## LUT generation and model independence

From the repository root:

```sh
.venv/bin/python scripts/generate_nco_lut.py
.venv/bin/python scripts/generate_nco_lut.py --check
```

The generator computes a 4096-point grid using 70-digit Decimal arithmetic,
a sine Taylor series in the first quadrant, and exact integer symmetry. It
writes `rtl/nco/sine_lut_12b.svh`, which is committed source, not a runtime
data file. Each entry is signed Q2.46: `round_away(2^46 * sin(angle))`, encoded
in 48 bits. The SV initialization loop selects every `2^(12-A)`th master entry
at elaboration, multiplies it by `peak` in explicitly signed 64-bit arithmetic,
then rounds the magnitude by adding `2^45` and shifting right 46 places before
restoring the sign. An explicit B-bit cast stores the result.

This produces a ROM of exactly `2^A` B-bit words, not a runtime multiplier or
a 48-bit output table. The largest intermediate for B<=16 is less than 2^61,
so signed 64-bit scaling/rounding cannot overflow. The generator exhaustively
checks every master entry at every supported B against direct 70-digit sine
quantization, rejecting any double-rounding discrepancy. The `--check` test
also detects stale generated constants. No thousands of hand-maintained values
or separate tables per output width are required. The generated function and
quantizer are used only with constant arguments during initialization.
There is no `$readmemh` runtime path dependency, vendor primitive, or synthesizable
real-number arithmetic. Include `rtl/nco` in the HDL tool's include path.

`models/python/nco_lut.py` computes its own table directly using binary64 sine
and the documented amplitude rounding. It does not load the generated header
or import the generator. The full 4096-entry RTL sweep at A=12 compares every
generated entry against this independent computation. Smaller supported widths
are subsets of this master grid. The original ideal model in `nco.py` remains
unchanged and evaluates the full phase without LUT address truncation.

## Reproduce verification

Required installed tools: Python, pytest, cocotb, Verilator, make, C++ compiler,
and Yosys. No proprietary tool is needed.

```sh
# All Python tests and RTL regressions (LUT address widths 2, 10, 12):
.venv/bin/python -m pytest -q

# Strict lint; warnings are fatal:
verilator --lint-only --Wall --top-module rf_nco -Irtl/nco rtl/nco/rf_nco.sv

# Generic synthesis, including pre-mapping ROM inspection:
mkdir -p build
yosys -l build/yosys-nco.log scripts/synth_nco.ys
```

The pytest runner builds Verilator and runs nine cocotb cases per configuration:
`(P,B,A) = (32,14,2), (32,14,10), (32,14,12), (16,8,8), (64,16,8), (12,2,12)`.
These include the default, both address-width bounds, the widest accumulator
and output, minimal output width, and a configuration with no discarded phase
bits. Python also cross-checks 32-bit phase evolution directly against the
unchanged ideal model, and checks all supported output widths and LUT widths.
Every driven rising edge compares I, Q, and valid against the Python clock model
with exact integer equality, including unsigned two's-complement wire encoding.
Tests cover synchronous reset and its priority,
enable stalls/resumption, zero increment, 1 MHz and 10 MHz at a nominal 100 MHz
sample rate, a tuning word one LSB below Nyquist, modulo wrap, quadrature,
every table entry, and phase continuity across arbitrary increment changes.
The two frequency tests each compare 10,000 uninterrupted samples per width;
near-Nyquist and wrap stress tests also run 10,000 samples each.

Build logs, simulation logs, and cocotb XML results are under `build/nco_p*_o*_a*`.
Yosys saves pre-mapping memory and post-mapping generic gate statistics and JSON
netlists under `build/`. These generated build artifacts are ignored by Git.
Generic gate counts do not predict LIFCL-40 utilization or achievable clock rate.
See [physical validation](physical_validation.md) for the later board-level result.

## Initial validation (2026-09-21, before width extension)

With Python 3.14.4, pytest 9.1.1, cocotb 2.1.0, Verilator 5.032, and Yosys 0.52:

- Full `python -m pytest -q`: **65 passed in 13.64s**. This comprises 62 Python
  unit tests and three RTL test runners, each running nine passing cocotb cases
  (27 RTL cases total, zero failures/skips).
- Each tested width (2, 10, 12) matched 10,000 consecutive samples exactly at
  both 1 MHz (`0x028f5c29`) and 10 MHz (`0x1999999a`), using fs=100 MHz.
- Strict Verilator lint passed at widths 2, 10, and 12 without warnings.
- Default-width generic Yosys synthesis passed with no warnings and zero
  `check -assert` problems. Before mapping, `sine_lut` was one 1024-by-14-bit
  `$mem_v2` ROM with two asynchronous read ports and zero write ports.
- After generic mapping: 1,775 cells, including 1,113 mux cells and 61 register
  bits (32 phase, 28 output, one valid). No memory cells remained after generic
  ROM-to-logic mapping; these are not FPGA LUT/block-RAM utilization numbers.

No tool installation was required. Detailed generated reports are in `build/`;
the public summary is in [Verification](verification.md).
