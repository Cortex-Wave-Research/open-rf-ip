# Linear FMCW chirp contract

Milestone 3 adds `chirp_controller` and `rf_chirp_nco` around the unchanged
`rf_nco`. Reusable RTL is vendor-independent. Initial widths are fixed:
32-bit phase/frequency word, signed 32-bit step, unsigned 32-bit length/index,
14-bit signed I/Q and 1024-entry LUT. No dwell, phase offset, bus or parallel lanes.

## Numerical sequence

For length N and emitted sample index k=0..N−1:

- W[k] = (Wstart + k × signed_step) mod 2^32.
- I[k], Q[k] are the existing NCO's LUT conversion of P[k].
- P[k+1] = (P[k] + W[k]) mod 2^32.
- Q address = P[k][31:22]; I address = (Q address + 256) mod 1024.

Thus P[k] = P[0] + k Wstart + step k(k−1)/2 modulo 2^32 within a chirp.
The first output after reset is I=8191, Q=0. W[k] advances phase AFTER producing
sample k, exactly as in the verified NCO. The frequency at the final word is
not recoverable from N isolated I/Q samples alone: N samples give N−1 phase
differences. That word governs the interval to the next emitted sample.

Frequency in Hz is signed(W) × fs/2^32 in the principal interval [−fs/2,fs/2).
RTL imposes no frequency clamp or endpoint comparator. Word wrap is intentional,
including wrapping through Nyquist; software must select physically useful
endpoints. Step range is −2^31..2^31−1. Negative steps are added using an
explicit unsigned reinterpretation of their two's-complement bits, then explicit
32-bit truncation. This is modular arithmetic, not signed saturation.

## Clock and control

All state changes occur at rising edges. Reset is synchronous, active high,
has priority over enable/start, aborts the chirp, clears phase/IQ, busy, index,
frequency state and indication outputs. No other event resets the NCO phase.

An acceptance edge requires `!busy && enable && start && chirp_length != 0`.
It latches start word, signed step, length and repeat. It sets busy but emits
no sample. The first following enabled edge emits sample 0. This one-edge setup
latency is explicit; no arbitrary alignment or array shifting is used in tests.
Configuration must meet ordinary synchronous setup/hold requirements.

- `enable=0` pauses an active chirp: phase, I/Q, word and index hold; valid,
  chirp_start and chirp_end are zero. A start while disabled is not queued.
  Phase continuity is defined across emitted samples. Pauses extend wall-clock
  duration; the oscillator does not free-run during disabled clocks.
- While busy, start and all live configuration changes are ignored, including
  on the last sample edge. There is no abort except reset.
- `start` is a synchronous level command, normally pulsed for one cycle. If
  held high in one-shot mode it will be accepted again on the first enabled
  idle edge after completion; that acceptance edge creates a one-clock gap.
- N=0 is rejected (idle remains idle, no samples/markers). N=1 emits one sample
  with BOTH start/end asserted. Maximum length is 2^32−1, not 2^32.
- One-shot: sample N−1 asserts end/valid, then busy falls. Final word/index and
  I/Q hold until a new accepted start; phase already includes the last word.
- Repeat: after sample N−1, index and word return to zero/start for the next
  enabled edge. There is no inter-chirp invalid gap, configuration stays latched,
  and accumulated phase remains continuous. N=1 repeat marks every sample both
  start and end. Changing live repeat does not stop a latched repeat stream.

`chirp_start`, `chirp_end`, and `sample_valid` are post-edge signals aligned to
registered I/Q. They assert only for valid samples. `busy` is post-edge state
and can be zero on a valid final one-shot sample. `phase_increment` and
`chirp_count` expose the controller's CURRENT scheduling state: sampled BEFORE
an enabled edge they describe that edge's output; AFTER the edge they describe
the next sample (or held final word/index when idle). They are not delayed
metadata for the registered I/Q. The verification bench checks both sides of
the edge explicitly. `nco_enable` is combinational busy AND enable AND NOT reset.

## Demonstration and quantization

Simulation fs=100 MHz, requested start=2 MHz, stop=20 MHz, length=10,000,
nominal active duration N/fs=100 µs. Sample timestamps span 0..99.99 µs;
there are N−1=9,999 frequency-step intervals between first/last words.
This convention reaches the requested final word at the last sample, rather
than defining stop frequency at the boundary after N intervals.

The Python `linear_config` helper uses exact rational arithmetic and nearest
rounding with ties away from zero:

- Wstart = round(2 MHz × 2^32 / 100 MHz).
- step = round((20 MHz − 2 MHz) × 2^32 / (100 MHz × 9,999)).
- Wfinal = (Wstart + 9,999 step) mod 2^32.

The helper does not compensate the start word to reduce final error. Start
error is at most half a tuning-word LSB; slope rounding accumulates up to
(N−1)/2 LSB at the endpoint. Numerical values are generated in
`reports/chirp/demo_config.json` when `scripts/analyze_chirp.py` is run after the RTL regression.
The 10-bit LUT phase truncation and 14-bit amplitude quantization add diagnostic
phase-difference ripple; they do not alter the exact accumulator progression.

## Verification and implementation scope

The independent Python chirp model uses the closed-form word equation and the
existing independent numerical LUT function; it never reads RTL constants.
Python tests check closed-form accumulated phase. Cocotb compares every edge,
including I/Q, scheduling word/index, markers, valid, phase and both addresses.
The controller is also tested alone. Plots use unwrapped complex I/Q phase and
are diagnostic only. The FPGA harness reuses the native 12 MHz L13 clock and
E17 activity pin; higher timing constraints do not create physical clocks.
