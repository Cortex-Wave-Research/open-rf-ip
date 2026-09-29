"""Independent numerical NCO reference; no RTL or lookup-table dependencies.

Phase words are unsigned 32-bit turns. I = cos(phase), Q = sin(phase).
Integer phase evolution is exact; trigonometry uses Python binary64 libm.
"""

import math
from fractions import Fraction

PHASE_BITS = 32
PHASE_MODULUS = 1 << PHASE_BITS
PHASE_MASK = PHASE_MODULUS - 1


def _round_away(value: Fraction) -> int:
    """Round an exact rational to nearest integer, ties away from zero."""
    magnitude = abs(value)
    rounded = (2 * magnitude.numerator + magnitude.denominator) // (
        2 * magnitude.denominator
    )
    return -rounded if value < 0 else rounded


def frequency_to_phase_increment(frequency_hz, sample_rate_hz) -> int:
    """Return round(f/fs * 2**32) modulo 2**32.

    Accept integers, finite floats, or Fraction values. Floats retain their
    exact binary value; use Fraction for exact decimal/rational inputs.
    Require fs > 0 and -fs/2 <= f <= fs/2 (both Nyquist signs map to 2**31).
    Negative frequencies yield the unsigned encoding of a negative increment.
    """
    frequency = Fraction(frequency_hz)
    sample_rate = Fraction(sample_rate_hz)
    if sample_rate <= 0:
        raise ValueError("sample rate must be positive")
    if abs(frequency) > sample_rate / 2:
        raise ValueError("frequency must be within the Nyquist interval")
    return _round_away(frequency * PHASE_MODULUS / sample_rate) & PHASE_MASK


def _word(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("phase words must be Python integers")
    if not 0 <= value < PHASE_MODULUS:
        raise ValueError("phase word must be unsigned 32-bit")
    return value


def quantize_signed(value: float, bits: int = 14) -> int:
    """Quantize [-1, 1] with symmetric full scale 2**(bits-1)-1.

    Round nearest, ties away from zero. The most-negative two's-complement
    code is unused. Widths 2..32 are supported. Reject out-of-range inputs.
    Rounding applies to the computed binary64 scaled value.
    """
    if not isinstance(bits, int) or isinstance(bits, bool) or not 2 <= bits <= 32:
        raise ValueError("sample width must be an integer from 2 to 32")
    if not math.isfinite(value) or not -1.0 <= value <= 1.0:
        raise ValueError("normalized amplitude must be finite and in [-1, 1]")
    scaled = value * ((1 << (bits - 1)) - 1)
    return _round_away(Fraction(scaled))


def phase_to_iq(phase: int, bits: int = 14) -> tuple[int, int]:
    """Map a phase word to signed integer (I, Q), using ideal sin/cos."""
    angle = math.tau * _word(phase) / PHASE_MODULUS
    return quantize_signed(math.cos(angle), bits), quantize_signed(math.sin(angle), bits)


class NCO:
    """32-bit accumulator; step returns current phase, then advances it.

    Changing phase_increment preserves phase. Reset defaults to zero phase
    and retains the programmed increment. All input words are range-checked.
    """

    def __init__(self, phase_increment: int, initial_phase: int = 0):
        self.phase_increment = phase_increment
        self.reset(initial_phase)

    @property
    def phase(self) -> int:
        return self._phase

    @property
    def phase_increment(self) -> int:
        return self._phase_increment

    @phase_increment.setter
    def phase_increment(self, value: int) -> None:
        self._phase_increment = _word(value)

    def reset(self, phase: int = 0) -> None:
        self._phase = _word(phase)

    def step(self) -> int:
        phase = self._phase
        self._phase = (phase + self.phase_increment) & PHASE_MASK
        return phase

    def sample(self, bits: int = 14) -> tuple[int, int]:
        iq = phase_to_iq(self.phase, bits)
        self.step()
        return iq
