# Compact waveform engine architecture

`rf_chirp_nco` composes `chirp_controller` with `rf_nco`. The reusable SystemVerilog is vendor-independent; only the board wrappers and constraints select the LIFCL-40-EVN.

| Property | Compact production configuration |
| --- | --- |
| Phase accumulator / tuning word | 32-bit unsigned, modulo 2^32 |
| Chirp step | Signed 32-bit, modular addition |
| Chirp length / index | Unsigned 32-bit |
| Phase-to-amplitude address | Upper 10 phase bits |
| LUT | Full-wave 1024 × 14-bit sine, shared I/Q reads |
| I/Q | Signed 14-bit; symmetric range −8191…8191 |
| NCO latency | One registered lookup stage |
| Throughput | One complex sample per enabled clock |

For sample k, `W[k] = (start + k*step) mod 2^32`. The NCO produces I/Q from current phase P[k], then advances phase by W[k]. Q uses the sine address; I uses that address plus one quarter turn. Low phase bits remain in the accumulator. Quantization is nearest with ties away from zero; −8192 is unused.

The checked-in LUT header holds a 4096-point normalized master grid. Elaboration selects and scales the entries needed for the requested NCO parameters; the default hardware table is 1024 × 14 bits. The deterministic Decimal generator and the independent binary64 reference compute their tables separately.

An accepted start command emits no sample. Sample 0 appears on the next enabled rising edge, with aligned registered I/Q, valid, and chirp_start. Enable pauses state and clears output flags; synchronous reset clears phase and aborts the chirp. Repeat reloads frequency/index without resetting accumulated phase. Exposed scheduling word/index describe the next sample after an output edge, not delayed metadata for that output.

The physical capture wrapper taps aligned outputs, stores the first 1024 consecutive valid records starting at chirp_start, freezes RAM, and exposes RFC1 bytes over I²C. A valid gap during capture sets a sticky error. This transport is board-specific, not part of the portable DSP interface.

Detailed contracts: [NCO RTL](nco-rtl.md), [ideal reference](nco-reference.md), [chirp controller](chirp_architecture.md), and [physical capture](physical_validation.md).
