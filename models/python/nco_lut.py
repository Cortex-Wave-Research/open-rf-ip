"""Independent bit-exact LUT NCO model, alongside the ideal model in nco.py.

No RTL table or generator is imported/read. Table entries are independently
computed with binary64 sin, then the documented signed amplitude quantizer.
The RTL generator instead uses high-precision Decimal arithmetic and symmetry.
"""

import math
from functools import lru_cache

from models.python.nco import quantize_signed


def _address_width(bits: int) -> int:
    if not isinstance(bits, int) or isinstance(bits, bool) or not 2 <= bits <= 12:
        raise ValueError("LUT address width must be an integer from 2 to 12")
    return bits


def _width(bits: int, minimum: int, maximum: int) -> int:
    if not isinstance(bits, int) or isinstance(bits, bool) or not minimum <= bits <= maximum:
        raise ValueError(f"width must be an integer from {minimum} to {maximum}")
    return bits


def _phase_word(value: int, phase_bits: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("phase words must be Python integers")
    if not 0 <= value < (1 << phase_bits):
        raise ValueError("phase word does not fit the unsigned accumulator")
    return value


def encode_signed(value: int, output_bits: int = 14) -> int:
    """Return the unsigned two's-complement bit pattern of a signed sample."""
    bits = _width(output_bits, 2, 16)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("sample must be a Python integer")
    if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError("sample does not fit the signed output")
    return value % (1 << bits)


@lru_cache(maxsize=165)
def sine_table(address_bits: int = 10, output_bits: int = 14) -> tuple[int, ...]:
    size = 1 << _address_width(address_bits)
    bits = _width(output_bits, 2, 16)
    return tuple(quantize_signed(math.sin(math.tau * k / size), bits) for k in range(size))


def lut_phase_to_iq(
    phase: int, address_bits: int = 10, *, phase_bits: int = 32, output_bits: int = 14
) -> tuple[int, int]:
    """Truncate phase to its top address_bits bits; cosine is offset sine."""
    bits = _address_width(address_bits)
    width = _width(phase_bits, bits, 64)
    address = _phase_word(phase, width) >> (width - bits)
    table = sine_table(bits, _width(output_bits, 2, 16))
    quarter = len(table) // 4
    return table[(address + quarter) % len(table)], table[address]


class LutNCO:
    """Clock model of rf_nco; constructor state equals a completed reset edge.

    tick() returns registered (I, Q, sample_valid) after the rising edge.
    Reset wins over enable. Disabled edges hold phase and I/Q, and clear valid.
    Enabled edges output the pre-increment phase, then advance modulo 2**phase_bits.
    """

    def __init__(self, address_bits: int = 10, *, phase_bits: int = 32, output_bits: int = 14):
        self.address_bits = _address_width(address_bits)
        self.phase_bits = _width(phase_bits, self.address_bits, 64)
        self.output_bits = _width(output_bits, 2, 16)
        self.phase = 0
        self.iq = (0, 0)
        self.sample_valid = False

    def tick(self, phase_increment: int = 0, *, enable: bool = True, rst: bool = False):
        increment = _phase_word(phase_increment, self.phase_bits)
        if rst:
            self.phase = 0
            self.iq = (0, 0)
            self.sample_valid = False
        else:
            self.sample_valid = bool(enable)
            if enable:
                self.iq = lut_phase_to_iq(
                    self.phase, self.address_bits, phase_bits=self.phase_bits, output_bits=self.output_bits
                )
                self.phase = (self.phase + increment) % (1 << self.phase_bits)
        return (*self.iq, self.sample_valid)

    @property
    def output_words(self) -> tuple[int, int]:
        return tuple(encode_signed(value, self.output_bits) for value in self.iq)
