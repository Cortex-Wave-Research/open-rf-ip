"""Independent cycle specification for the fixed 32/14/10-bit chirp composition.

Frequency words use a closed-form progression rather than an RTL-style recurrence.
Only the existing independent numerical LUT function is shared with the NCO model.
"""
from dataclasses import dataclass
from fractions import Fraction

from models.python.nco_lut import lut_phase_to_iq

MODULUS = 1 << 32


def nearest(value):
    value = Fraction(value)
    a = abs(value)
    result = (2 * a.numerator + a.denominator) // (2 * a.denominator)
    return -result if value < 0 else result


@dataclass(frozen=True)
class ChirpConfig:
    start_word: int
    step: int
    length: int
    repeat: bool = False

    def __post_init__(self):
        for name, low, high in [('start_word', 0, MODULUS-1),
                                ('step', -(1 << 31), (1 << 31)-1),
                                ('length', 0, MODULUS-1)]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} outside supported integer range')

    def word(self, index):
        return (self.start_word + index * self.step) % MODULUS


def linear_config(start_hz, stop_hz, sample_rate_hz, length, *, repeat=False):
    """Round start word and ideal per-sample frequency slope separately.

    Endpoints refer to the first and last of N emitted frequency words (N-1
    intervals). N=1 has only a start frequency; unequal endpoints are rejected.
    No optimization of start/step to compensate endpoint error is performed.
    """
    start, stop, fs = map(Fraction, (start_hz, stop_hz, sample_rate_hz))
    if fs <= 0 or abs(start) > fs/2 or abs(stop) > fs/2:
        raise ValueError('frequencies must be within Nyquist and fs positive')
    if type(length) is not int or not 1 <= length < MODULUS:
        raise ValueError('length must be in 1..2^32-1')
    if length == 1 and start != stop:
        raise ValueError('one sample cannot have distinct frequency endpoints')
    word = nearest(start * MODULUS / fs) % MODULUS
    step = 0 if length == 1 else nearest((stop-start)*MODULUS/(fs*(length-1)))
    return ChirpConfig(word, step, length, repeat)


def word_frequency(word, sample_rate_hz):
    """Principal signed frequency [-fs/2, fs/2); Nyquist is represented negative."""
    signed = word if word < (1 << 31) else word - MODULUS
    return Fraction(signed) * Fraction(sample_rate_hz) / MODULUS


class ChirpModel:
    def __init__(self):
        self.reset()

    def reset(self):
        self.config = ChirpConfig(0, 0, 0)
        self.busy = False
        self.index = 0
        self.phase = 0
        self.iq = (0, 0)

    @property
    def current_word(self):
        return self.config.word(self.index)

    def tick(self, config=None, *, start=False, enable=True, rst=False):
        """Return post-edge outputs and the pre-edge phase/word used if valid.

        busy/index/current_word after this method describe the NEXT sample.
        A completed one-shot holds its final index/word until another start.
        """
        if rst:
            self.reset()
            return dict(i=0, q=0, valid=False, chirp_start=False, chirp_end=False,
                        word=None, phase=None, q_address=None, i_address=None, index=None)
        result = dict(i=self.iq[0], q=self.iq[1], valid=False, chirp_start=False,
                      chirp_end=False, word=None, phase=None, q_address=None,
                      i_address=None, index=None)
        if self.busy and enable:
            k, phase, word = self.index, self.phase, self.current_word
            q_address = phase >> 22
            self.iq = lut_phase_to_iq(phase)
            result.update(i=self.iq[0], q=self.iq[1], valid=True,
                          chirp_start=k == 0, chirp_end=k == self.config.length-1,
                          word=word, phase=phase, q_address=q_address,
                          i_address=(q_address+256) % 1024, index=k)
            self.phase = (phase + word) % MODULUS
            if k == self.config.length-1:
                if self.config.repeat:
                    self.index = 0
                else:
                    self.busy = False
            else:
                self.index += 1
        elif not self.busy and enable and start and config is not None and config.length:
            self.config = config
            self.index = 0
            self.busy = True
        return result
