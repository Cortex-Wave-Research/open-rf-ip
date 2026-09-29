# NCO reference conventions

The accumulator has exactly 32 bits. One turn is 2^32 phase units:

`phase[n] = (initial_phase + n * increment) mod 2^32`.

`NCO.step()` returns phase[n] before advancing. `NCO.sample()` returns the I/Q
pair for that same phase before advancing once. Reset sets phase to zero (or
an explicit unsigned word) and preserves the increment. Updating the increment
does not reset phase, so frequency changes preserve phase continuity.

Frequency conversion is `round(f / fs * 2^32) mod 2^32`, using nearest rounding
with ties away from zero. Rational arithmetic prevents intermediate floating
point rounding in this conversion. Floats are interpreted as their exact binary
values; use `Fraction` for exact rational inputs. The sample rate must be positive
and frequency must be in [-fs/2, fs/2]. Both Nyquist endpoints encode 0x80000000.
Negative frequency uses modular subtraction through an unsigned increment word.
Frequency resolution is fs/2^32; nearest rounding gives at most half that error
(interpreted modulo fs at the Nyquist boundary).

I is cosine and Q is sine; positive frequency rotates from +I toward +Q.
The default output width is 14 bits. Supported widths are 2 through 32 bits.
Multiply each normalized component by `2^(bits-1)-1`, then round nearest with
ties away from zero. Thus 14-bit output spans -8191 through +8191; -8192 is unused.
This symmetric convention avoids unequal positive and negative peak magnitudes.
Outputs are signed Python integers, not packed two's-complement bit vectors.

Integer accumulation and frequency rounding are exact. Sine/cosine and amplitude
scaling use binary64 math, so this is an ideal numerical waveform reference,
not a bit-accurate model of an RTL lookup table or CORDIC. The separate
`models/python/nco_lut.py` implements the exact address truncation, amplitude
quantization, and clock behavior of the Milestone 2 RTL. See
[the RTL contract](nco-rtl.md) for details and verification commands.

The ideal model remains useful for assessing LUT approximation error. No chirp
control, parallel lanes, or FPGA primitives are included in either model.
