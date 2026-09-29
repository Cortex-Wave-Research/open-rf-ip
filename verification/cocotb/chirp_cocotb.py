"""Cycle-level chirp specification comparison, with no latency array shifting."""
import csv
import os
import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from models.python.chirp import ChirpConfig, ChirpModel, linear_config


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.model = ChirpModel()
        self.config = ChirpConfig(0, 0, 0)
        self.composed = hasattr(dut, 'i_out')
        self.initialized = False

    async def cycle(self, config=None, *, start=False, enable=True, rst=False):
        if config is not None:
            self.config = config
        c, d, m = self.config, self.dut, self.model
        d.clk.value = 0
        d.rst.value = int(rst)
        d.enable.value = int(enable)
        d.start.value = int(start)
        d.start_phase_inc.value = c.start_word
        d.chirp_step.value = c.step & 0xffffffff
        d.chirp_length.value = c.length
        d.repeat_mode.value = int(c.repeat)
        await Timer(5, unit='ns')
        emit = m.busy and enable and not rst
        used_word = int(d.phase_increment.value)
        if self.initialized:
            assert used_word == m.current_word
            assert int(d.chirp_count.value) == m.index
            if not self.composed:
                assert bool(d.nco_enable.value) == emit
            if self.composed and emit:
                assert int(d.nco.q_address.value) == m.phase >> 22
                assert int(d.nco.i_address.value) == ((m.phase >> 22)+256) % 1024
        expected = m.tick(c, start=start, enable=enable, rst=rst)
        d.clk.value = 1
        await Timer(5, unit='ns')
        assert bool(d.busy.value) == m.busy
        assert int(d.phase_increment.value) == m.current_word
        assert int(d.chirp_count.value) == m.index
        for name in ('chirp_start', 'chirp_end'):
            assert bool(getattr(d, name).value) == expected[name]
        if expected['valid']:
            assert used_word == expected['word']
        if self.composed:
            assert d.i_out.value.to_signed() == expected['i']
            assert d.q_out.value.to_signed() == expected['q']
            assert bool(d.sample_valid.value) == expected['valid']
            assert int(d.nco.phase.value) == m.phase
        self.initialized = True
        return expected

    async def reset(self):
        return await self.cycle(rst=True)


@cocotb.test()
async def up_down_zero_short_and_wrap(dut):
    b = Bench(dut)
    await b.reset()
    for c in [ChirpConfig(100, 7, 25), ChirpConfig(100, -7, 25),
              ChirpConfig(123456789, 0, 35), ChirpConfig(1, 4, 1),
              ChirpConfig(2, -3, 2), ChirpConfig(0xfffffffe, 7, 40),
              ChirpConfig(2, -7, 40), ChirpConfig(0x70000000, -(1 << 31), 40),
              ChirpConfig(0, (1 << 31)-1, 40)]:
        phase = b.model.phase
        assert not (await b.cycle(c, start=True))['valid']
        for k in range(c.length):
            r = await b.cycle()
            assert r['phase'] == (phase+k*c.start_word+c.step*k*(k-1)//2) % (1 << 32)
        for _ in range(3):
            assert not (await b.cycle())['valid']


@cocotb.test()
async def repeat_and_boundary_continuity(dut):
    b = Bench(dut)
    for length in (1, 2, 17, 10000):
        await b.reset()
        c = ChirpConfig(0xf1234567, -9876543, length, True)
        await b.cycle(c, start=True)
        for _ in range(length*3):
            assert (await b.cycle())['valid']


@cocotb.test()
async def enable_start_config_and_reset(dut):
    b = Bench(dut)
    await b.reset()
    c = ChirpConfig(0x12345678, -12345, 5)
    await b.cycle(c, start=True, enable=False)
    assert not b.model.busy
    await b.cycle(ChirpConfig(1, 1, 0), start=True)
    assert not b.model.busy
    await b.cycle(c, start=True)
    other = ChirpConfig(1, 777, 1, True)
    for k in range(5):
        for _ in range(3):
            assert not (await b.cycle(other, start=True, enable=False))['valid']
        assert (await b.cycle(other, start=True))['word'] == c.word(k)
    assert not b.model.busy
    await b.cycle(c, start=True)
    await b.cycle()
    # Reset is synchronous; asserting between edges cannot change I/Q/markers.
    if b.composed:
        before = (int(dut.i_out.value), int(dut.q_out.value))
        dut.clk.value = 0
        dut.rst.value = 1
        await Timer(2, unit='ns')
        assert (int(dut.i_out.value), int(dut.q_out.value)) == before
    await b.cycle(other, rst=True, start=True, enable=False)
    await b.cycle(c, start=True)
    assert (await b.cycle())['phase'] == 0
    await b.reset()
    await b.reset()
    # Max length must not behave as zero or a signed negative count.
    await b.cycle(ChirpConfig(0xffffffff, -1, 0xffffffff), start=True)
    for _ in range(10):
        r = await b.cycle()
        assert r['valid'] and not r['chirp_end']
    await b.reset()
    # Held start: N=1 one-shot alternates acceptance (invalid) and sample.
    for k in range(12):
        r = await b.cycle(ChirpConfig(0x80000000, 1, 1), start=True)
        assert r['valid'] == bool(k % 2)


@cocotb.test()
async def randomized_controls(dut):
    b = Bench(dut)
    await b.reset()
    rng = random.Random(20260923)
    for _ in range(3000):
        c = ChirpConfig(rng.getrandbits(32), rng.randrange(-(1 << 31), 1 << 31),
                        rng.randrange(17), bool(rng.getrandbits(1)))
        await b.cycle(c, start=rng.random() < .3, enable=rng.random() < .8,
                      rst=rng.random() < .02)


@cocotb.test()
async def demonstration_10000_exact(dut):
    b = Bench(dut)
    await b.reset()
    c = linear_config(2_000_000, 20_000_000, 100_000_000, 10000)
    await b.cycle(c, start=True)
    rows = []
    for k in range(10000):
        r = await b.cycle()
        assert r['valid']
        if b.composed:
            rows.append([k, r['word'], r['phase'], dut.i_out.value.to_signed(),
                         dut.q_out.value.to_signed(), int(dut.chirp_start.value),
                         int(dut.chirp_end.value), int(dut.sample_valid.value)])
    assert not (await b.cycle())['valid']
    if b.composed and os.environ.get('CHIRP_SAMPLE_CSV'):
        with Path(os.environ['CHIRP_SAMPLE_CSV']).open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['index','phase_increment','phase','i','q','chirp_start','chirp_end','valid'])
            writer.writerows(rows)
    dut._log.info('EXACT: 10000 consecutive samples; 0 I mismatches, 0 Q mismatches; '
                  'words, phase, addresses, start/end/valid all match')
