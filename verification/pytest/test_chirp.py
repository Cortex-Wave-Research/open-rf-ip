"""Independent mathematical checks of chirp sequencing before RTL comparison."""
from fractions import Fraction
import pytest
from models.python.chirp import ChirpConfig, ChirpModel, MODULUS, linear_config, nearest, word_frequency
from models.python.nco_lut import lut_phase_to_iq


@pytest.mark.parametrize('word,step,n', [
    (100, 7, 10), (100, -7, 10), (123, 0, 20), (9, 3, 1), (9, -3, 2),
    (0xfffffffe, 7, 20), (3, -8, 20), (0x70000000, -(1 << 31), 20),
    (0, (1 << 31)-1, 20), (0x051eb852, 77317, 10000),
])
def test_closed_form_phase(word, step, n):
    config = ChirpConfig(word, step, n)
    model = ChirpModel()
    assert not model.tick(config, start=True)['valid']
    for k in range(n):
        r = model.tick()
        phase = (k*word + step*k*(k-1)//2) % MODULUS
        assert r['phase'] == phase
        assert r['word'] == (word+k*step) % MODULUS
        assert (r['i'], r['q']) == lut_phase_to_iq(phase)
        assert r['q_address'] == phase >> 22
        assert r['i_address'] == ((phase >> 22)+256) % 1024
        assert r['valid'] and r['chirp_start'] == (k == 0)
        assert r['chirp_end'] == (k == n-1)
    assert not model.busy
    assert not model.tick()['valid']


@pytest.mark.parametrize('length', [1, 2, 17])
def test_repeat_continuity(length):
    c = ChirpConfig(0x12345678, -7654321, length, True)
    m = ChirpModel()
    m.tick(c, start=True)
    phase = 0
    for k in range(length*5):
        r = m.tick()
        assert r['phase'] == phase
        assert r['word'] == c.word(k % length)
        assert r['chirp_start'] == (k % length == 0)
        assert r['chirp_end'] == (k % length == length-1)
        phase = (phase+c.word(k % length)) % MODULUS


def test_controls_and_latching():
    m = ChirpModel()
    c = ChirpConfig(17, -5, 3)
    other = ChirpConfig(777, 88, 20, True)
    assert not m.tick(c, start=True, enable=False)['valid']
    assert not m.busy
    m.tick(ChirpConfig(3, 2, 0), start=True)
    assert not m.busy
    m.tick(c, start=True)
    for k in range(3):
        phase = m.phase
        assert not m.tick(other, start=True, enable=False)['valid']
        assert m.phase == phase
        r = m.tick(other, start=True)
        assert r['word'] == c.word(k)
    saved = m.phase
    m.tick(other, start=True)
    assert m.tick()['phase'] == saved  # restarting does not reset phase
    assert m.tick(rst=True)['i'] == 0
    assert not m.busy and m.phase == 0


def test_demo_quantization():
    c = linear_config(2_000_000, 20_000_000, 100_000_000, 10000)
    assert c.start_word == 85899346
    assert c.step == nearest(Fraction(18_000_000 * MODULUS, 100_000_000 * 9999))
    assert abs(word_frequency(c.start_word, 100_000_000)-2_000_000) <= Fraction(100_000_000, 2*MODULUS)
    assert abs(word_frequency(c.word(9999), 100_000_000)-20_000_000) <= Fraction(10000*100_000_000, 2*MODULUS)


@pytest.mark.parametrize('value,result', [(Fraction(1,2),1),(Fraction(-1,2),-1),
                                          (Fraction(3,2),2),(Fraction(-3,2),-2)])
def test_rounding(value, result):
    assert nearest(value) == result


@pytest.mark.parametrize('args', [(-1,0,1),(MODULUS,0,1),(0,1 << 31,1),
                                   (0,-(1 << 31)-1,1),(0,0,-1),(0,0,MODULUS)])
def test_invalid_config(args):
    with pytest.raises(ValueError):
        ChirpConfig(*args)


@pytest.mark.parametrize('args', [(0,1,100,1),(0,1,0,5),(0,60,100,5),(0,1,100,0)])
def test_invalid_frequency_config(args):
    with pytest.raises(ValueError):
        linear_config(*args)


def test_downward_and_single_frequency_config():
    assert linear_config(20_000_000, 2_000_000, 100_000_000, 10000).step < 0
    assert linear_config(2, 2, 100, 1).step == 0
    assert word_frequency(MODULUS-1, MODULUS) == -1
