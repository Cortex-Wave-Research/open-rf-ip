import math
from fractions import Fraction
import subprocess
from pathlib import Path
import pytest
from models.python.high_purity import HighPurityConfig, HighPurityNCO, HighPurityChirp, linear_config, phase_to_iq
from models.python.chirp import linear_config as compact_config


def test_entire_grid_against_direct_trig():
    def rnd(x): return int(math.copysign(math.floor(abs(x)+.5),x))
    for a in range(65536):
        angle=math.tau*a/65536
        assert phase_to_iq(a<<48)==(rnd(131071*math.cos(angle)),rnd(131071*math.sin(angle)))
    assert [phase_to_iq(k<<62) for k in range(4)] == [(131071,0),(0,131071),(-131071,0),(0,-131071)]
    assert phase_to_iq((1<<64)-1)==phase_to_iq(65535<<48)


def test_rom_reproducible():
    subprocess.run([str(Path('.venv/bin/python').resolve()),'scripts/generate_high_purity_lut.py','--check'],check=True)


def test_endpoint_accuracy():
    c=linear_config(2_000_000,20_000_000,100_000_000,10000)
    error=Fraction(c.word(9999)*100_000_000,1<<64)-20_000_000
    assert abs(error)<Fraction(1,10_000_000)
    old=compact_config(2_000_000,20_000_000,100_000_000,10000)
    assert abs(Fraction(old.word(9999)*100_000_000,1<<32)-20_000_000)>30
    assert c.step > (1<<32)


@pytest.mark.parametrize('length',[1,2,10000])
@pytest.mark.parametrize('step',[0,1,-1,-(1<<63),(1<<63)-1])
def test_chirp_closed_form_and_drain(length,step):
    m=HighPurityChirp();c=HighPurityConfig((1<<64)-17,step,length)
    assert not m.tick(c,start=True)['valid']
    assert not m.tick()['valid']
    for k in range(length):
        if k==length-1:
            held=m.pending
            for _ in range(3): assert not m.tick(enable=False)['valid']
            assert m.pending==held
        r=m.tick()
        assert r['valid'] and r['index']==k
        assert r['phase']==(k*c.start_word+step*k*(k-1)//2)%(1<<64)
        assert r['chirp_start']==(k==0) and r['chirp_end']==(k==length-1)
    assert not m.tick()['valid']


def test_nco_flush_pause_reset():
    m=HighPurityNCO()
    assert m.tick(1)==(0,0,False)
    assert m.tick(enable=False)==(0,0,False)
    assert m.tick(sample_enable=False)==(131071,0,True)
    assert m.tick(sample_enable=False)==(131071,0,False)
    assert m.tick(rst=True)==(0,0,False)
