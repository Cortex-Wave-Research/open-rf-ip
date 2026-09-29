import math
from fractions import Fraction

import pytest

from models.python.nco import (
    NCO, PHASE_MODULUS, frequency_to_phase_increment, phase_to_iq, quantize_signed,
)


@pytest.mark.parametrize("frequency, expected", [
    (0, 0), (25, 0x40000000), (-25, 0xC0000000),
    (50, 0x80000000), (-50, 0x80000000), (10, 429496730),
])
def test_frequency_conversion(frequency, expected):
    assert frequency_to_phase_increment(frequency, 100) == expected


@pytest.mark.parametrize("sign", [-1, 1])
def test_frequency_half_lsb_rounding(sign):
    assert frequency_to_phase_increment(Fraction(sign, 2), PHASE_MODULUS) == sign % PHASE_MODULUS


@pytest.mark.parametrize("frequency, rate", [(1, 0), (1, -1), (51, 100), (-51, 100)])
def test_invalid_frequency(frequency, rate):
    with pytest.raises(ValueError):
        frequency_to_phase_increment(frequency, rate)


def test_frequency_error_bound():
    for frequency in [Fraction(1, 3), Fraction(-77, 11), Fraction(499, 10)]:
        word = frequency_to_phase_increment(frequency, 100)
        signed = word if word < 2**31 else word - PHASE_MODULUS
        assert abs(Fraction(signed * 100, PHASE_MODULUS) - frequency) <= Fraction(50, PHASE_MODULUS)


def test_phase_wrapping():
    nco = NCO(3, 0xFFFFFFFE)
    assert [nco.step() for _ in range(4)] == [0xFFFFFFFE, 1, 4, 7]
    reverse = NCO(0xFFFFFFFF, 1)
    assert [reverse.step() for _ in range(4)] == [1, 0, 0xFFFFFFFF, 0xFFFFFFFE]


@pytest.mark.parametrize("increment", [0, 1, 0x40000000, 0x80000000, 429496730, 0xFFFFFFFF])
def test_fixed_frequency_evolution(increment):
    initial = 123456789
    nco = NCO(increment, initial)
    assert [nco.step() for _ in range(10000)] == [
        (initial + k * increment) % 2**32 for k in range(10000)
    ]
    assert nco.phase == (initial + 10000 * increment) % 2**32


def test_continuity_and_reset():
    nco = NCO(3, 10)
    assert nco.step() == 10
    nco.phase_increment = 7
    assert nco.step() == 13
    assert nco.phase == 20
    nco.reset()
    assert nco.step() == 0
    assert nco.phase == 7


@pytest.mark.parametrize("bits", [2, 8, 14, 16, 32])
def test_signed_iq_cardinal_phases(bits):
    peak = 2**(bits - 1) - 1
    nco = NCO(0x40000000)
    assert [nco.sample(bits) for _ in range(5)] == [
        (peak, 0), (0, peak), (-peak, 0), (0, -peak), (peak, 0)
    ]


def test_iq_diagonal():
    assert phase_to_iq(0x20000000) == (5792, 5792)
    assert phase_to_iq(0xA0000000) == (-5792, -5792)


@pytest.mark.parametrize("value, expected", [(0, 0), (0.5, 4), (-0.5, -4), (1, 7), (-1, -7)])
def test_signed_rounding(value, expected):
    assert quantize_signed(value, 4) == expected


def test_quantization_error_and_range():
    for k in range(1024):
        phase = k * 2**22
        i, q = phase_to_iq(phase)
        for code, ideal in [(i, math.cos(math.tau * k / 1024)), (q, math.sin(math.tau * k / 1024))]:
            assert -8191 <= code <= 8191
            assert abs(code - ideal * 8191) <= 0.5


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.01, 1.01])
def test_invalid_amplitude(value):
    with pytest.raises(ValueError):
        quantize_signed(value)


@pytest.mark.parametrize("bits", [1, 33, 14.5, True])
def test_invalid_width(bits):
    with pytest.raises(ValueError):
        quantize_signed(0, bits)


@pytest.mark.parametrize("word, error", [(-1, ValueError), (2**32, ValueError), (1.5, TypeError), (True, TypeError)])
def test_invalid_phase_words(word, error):
    with pytest.raises(error):
        NCO(word)
    with pytest.raises(error):
        NCO(0, word)
    with pytest.raises(error):
        phase_to_iq(word)
