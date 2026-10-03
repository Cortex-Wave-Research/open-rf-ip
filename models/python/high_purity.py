"""Independent production high-purity model; never reads RTL ROM constants.

Quarter magnitudes use binary64 math, independently of the Decimal RTL generator.
Chirp scheduling uses closed-form words. Pipeline is a one-entry sample queue
advanced by global enable, including invalid bubbles that drain one-shots.
"""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import math
from models.python.chirp import nearest

MOD = 1 << 64
MASK = MOD-1


@lru_cache(None)
def quarter_table():
    return tuple(math.floor(131071*math.sin(math.pi*k/32768)+0.5) for k in range(16384))


def phase_to_iq(phase):
    if type(phase) is not int or not 0 <= phase < MOD:
        raise ValueError('phase must be an unsigned 64-bit integer')
    address = phase >> 48
    def component(a):
        quadrant, offset = divmod(a, 16384)
        index = offset if quadrant % 2 == 0 else 16384-offset
        magnitude = 131071 if index == 16384 else quarter_table()[index]
        return -magnitude if quadrant >= 2 else magnitude
    return component((address+16384) % 65536), component(address)


@dataclass(frozen=True)
class HighPurityConfig:
    start_word: int
    step: int
    length: int
    repeat: bool = False

    def __post_init__(self):
        for name, low, high in [('start_word',0,MASK), ('step',-(1<<63),(1<<63)-1), ('length',0,(1<<32)-1)]:
            value = getattr(self,name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} outside supported integer range')

    def word(self, index):
        return (self.start_word + index*self.step) % MOD


def linear_config(start_hz, stop_hz, fs, length, repeat=False):
    start, stop, rate = map(Fraction, (start_hz,stop_hz,fs))
    if rate <= 0 or max(abs(start),abs(stop)) > rate/2:
        raise ValueError('frequencies must be within Nyquist; fs positive')
    if type(length) is not int or not 1 <= length < (1<<32):
        raise ValueError('invalid length')
    if length == 1 and start != stop:
        raise ValueError('one sample cannot have two frequencies')
    word = nearest(start*MOD/rate) % MOD
    step = 0 if length == 1 else nearest((stop-start)*MOD/(rate*(length-1)))
    return HighPurityConfig(word,step,length,repeat)


class HighPurityNCO:
    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = 0
        self.pending = None
        self.iq = (0,0)

    def tick(self, word=0, *, enable=True, sample_enable=True, rst=False):
        if rst:
            self.reset()
            return (*self.iq,False)
        valid = False
        if enable:
            if self.pending is not None:
                self.iq = self.pending
                valid = True
            if sample_enable:
                self.pending = phase_to_iq(self.phase)
                self.phase = (self.phase+word) % MOD
            else:
                self.pending = None
        return (*self.iq,valid)


class HighPurityChirp:
    def __init__(self):
        self.reset()

    def reset(self):
        self.config = HighPurityConfig(0,0,0)
        self.index = 0
        self.busy = False
        self.phase = 0
        self.pending = None
        self.iq = (0,0)

    @property
    def current_word(self):
        return self.config.word(self.index)

    def tick(self, config=None, *, start=False, enable=True, rst=False):
        if rst:
            self.reset()
        result = dict(i=self.iq[0],q=self.iq[1],valid=False,chirp_start=False,
                      chirp_end=False,index=None,phase=None,word=None)
        if rst or not enable:
            return result
        if self.pending is not None:
            result = self.pending
            self.iq = (result['i'],result['q'])
        self.pending = None
        if self.busy:
            k, phase, word = self.index,self.phase,self.current_word
            i,q = phase_to_iq(phase)
            self.pending = dict(i=i,q=q,valid=True,chirp_start=k==0,
                                chirp_end=k==self.config.length-1,index=k,phase=phase,word=word)
            self.phase = (phase+word) % MOD
            if k == self.config.length-1:
                if self.config.repeat:
                    self.index = 0
                else:
                    self.busy = False
            else:
                self.index += 1
        elif start and config is not None and config.length:
            self.config = config
            self.index = 0
            self.busy = True
        return result
