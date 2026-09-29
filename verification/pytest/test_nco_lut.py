import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from models.python.nco import NCO
from models.python.nco_lut import LutNCO, encode_signed, lut_phase_to_iq, sine_table

ROOT = Path(__file__).resolve().parents[2]


def test_committed_lut_is_reproducible():
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_nco_lut.py"), "--check"], check=True)


@pytest.mark.parametrize("bits", range(2, 13))
def test_lut_numerical_contract(bits):
    table = sine_table(bits)
    size = 1 << bits
    assert len(table) == size
    assert table[::size // 4] == (0, 8191, 0, -8191)
    for address, value in enumerate(table):
        assert -8191 <= value <= 8191
        assert abs(value - 8191 * math.sin(math.tau * address / size)) <= 0.5
        assert value == -table[(address + size // 2) % size]
        phase = address << (32 - bits)
        expected = (table[(address + size // 4) % size], value)
        assert lut_phase_to_iq(phase, bits) == expected
        # Both ends of each bin must use the same value, without phase rounding.
        assert lut_phase_to_iq(phase + (1 << (32 - bits)) - 1, bits) == expected


def test_clock_model_reset_hold_and_continuity():
    model = LutNCO()
    assert model.tick(0x40000000, rst=True) == (0, 0, False)
    assert model.tick(0x40000000) == (8191, 0, True)
    assert model.tick(0xFFFFFFFF, enable=False) == (8191, 0, False)
    assert model.phase == 0x40000000
    assert model.tick(0) == (0, 8191, True)
    assert model.tick(0xC0000000) == (0, 8191, True)
    assert model.phase == 0
    assert model.tick(123, enable=False, rst=True) == (0, 0, False)


@pytest.mark.parametrize("bits", [1, 13, 10.5, True])
def test_reject_invalid_lut_width(bits):
    with pytest.raises(ValueError):
        LutNCO(bits)
    with pytest.raises(ValueError):
        lut_phase_to_iq(0, bits)


@pytest.mark.parametrize("output_bits", range(2, 17))
def test_output_width_and_signed_encoding(output_bits):
    peak = (1 << (output_bits - 1)) - 1
    table = sine_table(12, output_bits)
    assert table[::1024] == (0, peak, 0, -peak)
    for index, value in enumerate(table):
        assert abs(value - peak * math.sin(math.tau * index / 4096)) <= 0.5
        assert -peak <= value <= peak
        encoded = encode_signed(value, output_bits)
        decoded = encoded if encoded < (1 << (output_bits - 1)) else encoded - (1 << output_bits)
        assert decoded == value
        assert encoded != (1 << (output_bits - 1))  # Unused most-negative code.


def test_lut_phase_matches_original_32bit_source_of_truth():
    ideal = NCO(0)
    model = LutNCO()
    rng = random.Random(777)
    for _ in range(10000):
        increment = rng.getrandbits(32)
        ideal.phase_increment = increment
        ideal.step()
        model.tick(increment)
        assert model.phase == ideal.phase


@pytest.mark.parametrize("phase_bits,address_bits", [(2, 2), (12, 12), (16, 8), (64, 12)])
def test_parameterized_phase_wrap(phase_bits, address_bits):
    model = LutNCO(address_bits, phase_bits=phase_bits, output_bits=16)
    increments = [(1 << phase_bits) - 1, 2, (1 << phase_bits) - 3, 0]
    total = 0
    for increment in increments * 10:
        model.tick(increment)
        total += increment
        assert model.phase == total % (1 << phase_bits)


@pytest.mark.parametrize("phase_bits,output_bits", [(9, 14), (65, 14), (32, 1), (32, 17)])
def test_reject_invalid_parameter_widths(phase_bits, output_bits):
    with pytest.raises(ValueError):
        LutNCO(10, phase_bits=phase_bits, output_bits=output_bits)
