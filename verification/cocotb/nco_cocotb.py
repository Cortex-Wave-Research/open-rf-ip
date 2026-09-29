"""Cycle-by-cycle port-level checks; no DUT internals or RTL ROM file reads."""

import os
import random

import cocotb
from cocotb.triggers import Timer

from models.python.nco import frequency_to_phase_increment
from models.python.nco_lut import LutNCO

SAMPLE_RATE_HZ = 100_000_000


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.bits = int(os.environ["NCO_LUT_ADDR_WIDTH"])
        self.phase_bits = int(os.environ["NCO_PHASE_WIDTH"])
        self.output_bits = int(os.environ["NCO_OUTPUT_WIDTH"])
        self.quarter = 1 << (self.phase_bits - 2)
        self.mask = (1 << self.phase_bits) - 1
        self.peak = (1 << (self.output_bits - 1)) - 1
        self.model = LutNCO(self.bits, phase_bits=self.phase_bits, output_bits=self.output_bits)
        self.cycles = 0
        dut.clk.value = 0
        dut.rst.value = 0
        dut.enable.value = 0
        dut.phase_increment.value = 0

    def outputs(self):
        return (
            self.dut.i_out.value.to_signed(),
            self.dut.q_out.value.to_signed(),
            bool(self.dut.sample_valid.value),
        )

    async def cycle(self, increment=0, *, enable=True, rst=False):
        # Drive on the falling edge; check after the rising-edge NBA settles.
        self.dut.clk.value = 0
        self.dut.rst.value = int(rst)
        self.dut.enable.value = int(enable)
        self.dut.phase_increment.value = increment
        await Timer(5, unit="ns")
        self.dut.clk.value = 1
        expected = self.model.tick(increment, enable=enable, rst=rst)
        await Timer(5, unit="ns")
        actual = self.outputs()
        self.cycles += 1
        assert actual == expected, (
            f"cycle={self.cycles} width={self.bits} increment=0x{increment:08x} "
            f"enable={enable} rst={rst}: RTL={actual}, Python={expected}"
        )
        assert (int(self.dut.i_out.value), int(self.dut.q_out.value)) == self.model.output_words
        return actual

    async def reset(self):
        await self.cycle(rst=True)

    def word32(self, value):
        """Preserve the fractional-turn meaning of a 32-bit test tuning word."""
        if self.phase_bits >= 32:
            return value << (self.phase_bits - 32)
        return value >> (32 - self.phase_bits)


@cocotb.test()
async def reset_behavior(dut):
    bench = Bench(dut)
    await bench.reset()
    await bench.cycle(bench.quarter)
    before = await bench.cycle(bench.quarter)
    assert before == (0, bench.peak, True)
    # Reset asserted between edges must not asynchronously clear the outputs.
    dut.clk.value = 0
    dut.rst.value = 1
    await Timer(2, unit="ns")
    assert bench.outputs() == before
    assert await bench.cycle(bench.mask, rst=True) == (0, 0, False)
    await bench.cycle(rst=True, enable=False)
    assert await bench.cycle(enable=False) == (0, 0, False)
    assert await bench.cycle(bench.quarter) == (bench.peak, 0, True)


@cocotb.test()
async def enable_disable(dut):
    bench = Bench(dut)
    await bench.reset()
    for _ in range(4):
        await bench.cycle(bench.word32(0x12345678), enable=False)
    await bench.cycle(bench.quarter)
    for _ in range(20):
        assert await bench.cycle(bench.mask, enable=False) == (bench.peak, 0, False)
    assert await bench.cycle(bench.quarter) == (0, bench.peak, True)
    rng = random.Random(101)
    for _ in range(500):
        await bench.cycle(bench.word32(0x13579BDF), enable=bool(rng.getrandbits(1)))


@cocotb.test()
async def zero_increment(dut):
    bench = Bench(dut)
    await bench.reset()
    for _ in range(100):
        assert await bench.cycle(0) == (bench.peak, 0, True)
    await bench.cycle(bench.quarter)
    for _ in range(100):
        assert await bench.cycle(0) == (0, bench.peak, True)


async def fixed_tone(dut, frequency):
    bench = Bench(dut)
    await bench.reset()
    if bench.phase_bits == 32:
        increment = frequency_to_phase_increment(frequency, SAMPLE_RATE_HZ)
    else:
        # Integer nearest/ties-away for these nonnegative test frequencies.
        increment = (2 * frequency * (1 << bench.phase_bits) + SAMPLE_RATE_HZ) // (2 * SAMPLE_RATE_HZ)
    for _ in range(10000):
        await bench.cycle(increment)
    dut._log.info(
        "EXACT MATCH: 10000 consecutive I/Q samples, 0 mismatches; requested f=%d Hz, fs=%d Hz, "
        "FCW=0x%x, phase=%d output=%d LUT=%d bits",
        frequency, SAMPLE_RATE_HZ, increment, bench.phase_bits, bench.output_bits, bench.bits,
    )


@cocotb.test()
async def tone_1mhz_10000_samples(dut):
    await fixed_tone(dut, 1_000_000)


@cocotb.test()
async def tone_10mhz_10000_samples(dut):
    await fixed_tone(dut, 10_000_000)


@cocotb.test()
async def near_nyquist(dut):
    bench = Bench(dut)
    await bench.reset()
    # Largest positive tuning word strictly below Nyquist; includes low-bit carry.
    for _ in range(10000):
        await bench.cycle((1 << (bench.phase_bits - 1)) - 1)


@cocotb.test()
async def accumulator_wraparound(dut):
    bench = Bench(dut)
    await bench.reset()
    # Phase progression: 0, maximum unsigned phase, 1, 2 ... .
    assert await bench.cycle(bench.mask) == (bench.peak, 0, True)
    await bench.cycle(2)
    await bench.cycle(1)
    # Exercise carry from low bits into every LUT bin, not just aligned words.
    for _ in range(10000):
        await bench.cycle(bench.word32(0xFEDCBA99) | 1)


@cocotb.test()
async def iq_quadrature_and_all_lut_entries(dut):
    bench = Bench(dut)
    await bench.reset()
    size = 1 << bench.bits
    samples = [await bench.cycle(1 << (bench.phase_bits - bench.bits)) for _ in range(size)]
    assert samples[0] == (bench.peak, 0, True)
    assert samples[size // 4] == (0, bench.peak, True)
    assert samples[size // 2] == (-bench.peak, 0, True)
    assert samples[3 * size // 4] == (0, -bench.peak, True)
    for k, (i, q, _) in enumerate(samples):
        assert i == samples[(k + size // 4) % size][1]
        assert q == -samples[(k + size // 2) % size][1]


@cocotb.test()
async def phase_continuity_on_increment_change(dut):
    bench = Bench(dut)
    await bench.reset()
    rng = random.Random(20260921)
    # Arbitrary tuning updates stress continuity without a chirp controller.
    for _ in range(2000):
        await bench.cycle(rng.getrandbits(bench.phase_bits))
