# VexRiscv simulation integration

Status: all four waveform profiles, completion/clear lifecycle, reset campaigns,
adapter formal checks, strict lint, generic synthesis, native-12-MHz LIFCL-40
preflight and the final 6.1A signoff have passed. Milestone 6.2 simulation and
verification acceptance is complete; physical CPU execution remains out of scope.
Host software chooses the waveform, RV32I firmware configures and sequences it,
and the existing dedicated RTL generates every sample. The CPU is never in the
sample path. See [pinned provenance](../third_party/vexriscv/PROVENANCE.md) and
the unchanged [ABI 1.0](control_plane.md).

The control-plane specification and pinned-source provenance retain their
Milestone 6.0/6.2A scope statements: the reusable control plane remains CPU
independent, while this optional M6.2 demonstration adds a separate CPU wrapper
and firmware. Their earlier statements that no CPU integration was included
describe the state before this demonstration; this document records the current
simulation-integration status. Neither file's ABI or pinned-source content is
changed here.

## Memory and reset contract

| Byte range | Storage / purpose |
|---|---|
| `80000000–80000fff` | 4096-byte read-only firmware, instruction and data reads |
| `80010000–800103ff` | 1024-byte writable data/stack RAM |
| `40000000–4000ffff` | Existing CSR window, original 16-bit byte offsets |
| `40010000` | Integration progress/PASS/FAIL mailbox, full-word RW |
| `40010004` | Integration sticky data-bus fault, RO; reset clears |

All other addresses fail without aliasing. The CPU resets to `80000000`.
One clock serves CPU, buses and waveform engine. System reset asserts high,
clears bus state and CSR state, and must be released synchronously. ROM words
are initialized from the build's deterministic image; padding is RV32I `jal x0,0`.
RAM has no reset loop in hardware; startup clears its entire 1 KiB before use,
copies initialized data, then sets the 16-byte-aligned stack top `80010400`.

Instruction requests are accepted only on valid/ready; a synchronous ROM returns
one ordered response the following cycle without response backpressure. Accepted
fetches complete even if the CPU subsequently flushes. Out-of-ROM fetches return
a self-loop instruction and assert error; verification treats them as failure.

## Control and fault contract

Four separate elaborations select compact/high-purity and tone/chirp; each
contains exactly one existing waveform wrapper. Tone: shadow writes, COMMIT,
RUN_ENABLE. Chirp: shadow writes, COMMIT, RUN_ENABLE, START. Tone START remains
BAD_COMMAND and is a mandatory negative test. Low/high writes remain shadow-only;
only a valid COMMIT copies the complete active tuple atomically.

DBus commands transfer with valid AND ready. The integration accepts one command
at a time and owns its captured address/data/mask until completion. Stores have
no CPU response channel; subsequent commands wait until the owned store finishes.
Loads receive registered `rsp_ready` (an input to the CPU), data and error.
The Wishbone adapter preserves byte addresses, data and SEL, holds CYC/STB and
payload stable until ACK/ERR, and inserts an idle interval before another request.
ERR returns zero read data with error asserted, never a successful response.

The CPU ignores access-error inputs and cannot trap. Integration faults therefore
also latch `40010004`; firmware explicitly checks this register. It is separate
from the frozen CSR ERROR_STATUS. CSR-window unmapped/misaligned addresses reach
the existing CSR decoder unchanged and produce its ILLEGAL_BUS_ACCESS behavior.
RAM accesses must be naturally aligned; invalid size/alignment fails with no RAM
write. Byte/halfword RAM writes use the CPU's replicated data and four lane masks.
This is a controlled bare-metal environment, not a fault-recovering OS platform.

Firmware uses only `--target=riscv32-unknown-elf -march=rv32i -mabi=ilp32`, no
libc, traps, CSR instructions, interrupts, compressed instructions, hardware
multiply/divide or floating point. Build output, final disassembly and hashes
belong under ignored `build/`. Final linked machine instructions must be audited;
compiler flags alone are insufficient. No generated CPU RTL may be edited.

## Verification boundary

Required evidence is real CPU execution, independent Python cycle comparison,
identical Verilator/Icarus transaction transcripts, reset seeds, adapter properties,
strict integration lint, generic synthesis, and offline LIFCL-40 implementation
at native 12 MHz. Results are recorded in the Milestone 6.2 continuation section
below. Physical CPU execution remains Milestone 6.3; no board access is part of
this work.

The following sections retain intermediate failure investigations for
provenance. Their interim STOP/FAIL outcomes are superseded by the later
resolution sections and final verification results; the listed issues were
resolved in the test observer, simulation harness, or firmware startup as
described below. They do not describe the current signoff status.

## Simulation time and generated-code warning review

Verilator 5.032 uses `--timescale 1ns/1ps` for integration lint and the equivalent
cocotb `timescale=('1ns','1ps')` build setting. The installed manual documents
`--timescale <timeunit>/<timeprecision>` as a default for modules without a
preceding declaration, unlike the override option. This matches the canonical
CPU's line 5 declaration. All 15 project-owned integration source files have no
timeunit/timeprecision/directive or procedural delays; the test drives explicit
5 ns half-periods. No clock, delay, RTL or previous baseline invocation changes.

Strict unwaived lint with this default produces no TIMESCALEMOD in any of the
four profiles. Each has exactly 79 diagnostics, all in canonical VexRiscv:
DECLFILENAME 1, WIDTHTRUNC 1, UNUSEDSIGNAL 77. The external configuration
`verification/cpu/vexriscv_waivers.vlt` lists each reviewed source line and class,
scoped exclusively to `third_party/vexriscv/VexRiscv.v`. The runner verifies the
pinned SHA256 before use. These user-authorized third-party waivers do not apply
to project-owned RTL. All other warnings remain fatal under `--Wall`; no global
warning downgrade or blackboxing is used. The existing 6.1A policy and auditor
remain unchanged; this configuration is an explicitly reviewed third-party
exception, not a change to the project-owned RTL policy.

- DECLFILENAME at 2380: the generator includes subsidiary FIFO modules in the
  canonical file. Their module names need not match its filename.
- WIDTHTRUNC at 677: a 33-bit concatenation shifted right by one is assigned to
  32 bits. The retained bits are the conditional arithmetic sign and original
  operand bits 31:1; discarded bit 32 is outside the required result.
- UNUSEDSIGNAL at the 77 individually listed declaration lines: unused generated
  debug strings, occupancy/availability metadata, intermediate sliced bits and
  disabled-feature signals. This includes the documented ignored data access-error
  input. Waiving diagnostics does not add traps or change the CPU's limitations.

The new `mailbox_o` name is an exact local rename of an invalid SystemVerilog
keyword identifier in the two new CPU modules and their cocotb observer. Width,
reset, MMIO address, assignments and implicit instance connection are unchanged.
Firmware's C pointer and transcript labels retain the descriptive word mailbox;
they are not HDL references. No frozen RTL or CSR ABI field was renamed.

## Write-response observer contract

ABI 1.0 specifies exact read results, write effects and ACK/ERR. Successful write
response data has no architectural meaning (category D); the frozen
`verification/cocotb/control_bus.py` compares it only for successful reads.
The Python model's zero return on writes is a placeholder, not a zero-data bus
requirement. Separately, the frozen adapter registers pre-execution CSR readback
on every successful access; `openrf_wb_formal.sv` proves that wiring for writes
as well as reads. The existing cross-simulator transcript retains those raw values.
These implementation checks remain unchanged.

At 33,885 ns, CPU address `0x40000028` wrote `0x19999999` to NCO_PHASE_INC_LO,
SEL=0xF, CYC/STB/WE=1, ACK=1, ERR=0. The previous shadow value `0x11` appeared
on registered slave rdata, while current CSR readback became `0x19999999`.
The new observer incorrectly required its model's write placeholder zero.

The corrected CPU observer checks ownership, stable request payload, translated
address, WE/data/SEL, one execution/completion and exact ACK/ERR. It checks all
shadow words, active fields and CSR flags/state against the independent model
on every edge. Reads remain exact; error response data remains zero. Successful
write rdata is recorded but is not interpreted as architectural data.

Focused regression commands (both PASS, identical nine-transaction records):

```sh
.venv/bin/python verification/cpu/run_write_response.py verilator
.venv/bin/python verification/cpu/run_write_response.py icarus
```

The regression reproduces old-value readback, exercises partial-byte writes,
readback, atomic COMMIT, RO-write rejection and duplicate-execution checks.
Deliberately corrupted request/termination/read-data fields must be rejected.
The previous full CPU rerun passed the former failure but stopped at a separate pause
assertion: valid output with mailbox still 0x40. Firmware enables RUN before its
later mailbox=0x50 store. The subsequent review and correction are recorded below.

## Progress mailbox and pause/resume

The mailbox is firmware test-progress/debug telemetry (category B). Its memory-map
description is progress/PASS/FAIL; the local memory block stores accepted full-word
writes to 0x40010000 and exposes them for observation/readback. It has no connection
to waveform control. Firmware writes RUN_CONTROL separately before mailbox=0x50.
It is not an atomic synchronization state or a hardware pause signal.

The frozen control contract applies RUN_ENABLE at CSR execution edge B; the engine
uses the new value at edge C. Disabled engine edges clear valid/markers and hold
phase/IQ and pending pipeline state. Resume follows the existing compact/HP
pipeline, including any retained HP sample. The independent models determine the
exact output each edge, without a mailbox timing assumption or alignment search.

Unchanged compact-tone firmware trace, zero-based cycles and rising-edge times:

| Event | Cycle | Edge (ns) | Fetch PC | RUN after edge | Valid after edge | Mailbox after edge |
|---|---:|---:|---|---:|---:|---|
| CPU DBus accepts write 0x40000024=1, mask F | 4464 | 44645 | 0x80000760 | 0 | 0 | 0x40 |
| Wishbone captures request A | 4465 | 44655 | 0x80000764 | 0 | 0 | 0x40 |
| CSR executes B; ACK becomes 1, ERR=0 | 4466 | 44665 | 0x80000764 | 1 | 0 | 0x40 |
| Response consumed C; first resumed sample | 4467 | 44675 | 0x80000764 | 1 | 1 | 0x40 |
| CPU accepts mailbox store 0x40010000=0x50 | 4470 | 44705 | 0x80000768 | 1 | 1 | 0x50 |

The prior assertion sampled cycle4467 after settling at44680ns. Both tone markers
remain0. Sample count is307 before resume,308 after the first resumed edge,311
at mailbox update. Phase holds0xb333327b during pause and becomes0xcccccc14 on
resume, exactly one0x19999999 increment. The full pre/post event trace includes
MMIO payload/handshake, CYC/STB/WE/ACK/ERR, phase, valid and markers. Fetch PC is not
claimed to identify the retiring store instruction.

The corrected observer retains mailbox progress checks but bases pause checks on
pre-edge modeled RUN_ENABLE from real CPU CSR transactions. Every edge checks
actual phase against the independent model; disabled edges additionally check
held waveform state and cleared valid/markers. HP pending sample state and chirp
scheduler state are included when those profiles are exercised. Exact I/Q and
marker comparisons remain active across resume, detecting skipped/duplicate data.

Focused command: `scripts/run_vexriscv_signoff.py --stage pause --sim verilator
--hp 0 --kind 0` with the project Python interpreter. It runs unchanged firmware
through32 resumed samples: PASS,4499cycles,529 paused engine edges. The equivalent
Icarus run FAILS at31725ns while converting CPU d_data containing unknown bits;
it has not verified pause/resume or cross-simulator agreement. Its build also emits
timescale-inheritance warnings for the three new CPU modules and missing explicit
time-unit/precision diagnostics for12 existing design elements. No suppression or
unknown-value coercion was applied. The runner reached simulation automatically
before these build diagnostics were reviewed. The main full test was not rerun
after this focused failure, and later signoff stages remain blocked.

## Icarus four-state continuation

The original unknown `d_data` was unused store data on an ABI_VERSION read,
not `d_rdata`. At cycle3172/31725ns, PC80000200 executes `lw a0,4(a2)`;
its immediate bits select uninitialized x4 on the unused second register port.
The observer now omits read-command data and idle payload conversion, retaining
exact write payload, valid read-response, ownership and CSR side-effect checks.
A new DBus response observer rejects unresolved required read responses.

Icarus12.0 already receives documented `+timescale+1ns/1ps` through cocotb.
A simulation-only compilation-unit `timeunit 1ns; timeprecision 1ps;` source,
followed by project sources and canonical VexRiscv last, eliminates both missing
and inherited-timescale warnings under `-g2012 -Wall`. Old/new compiled scopes
have identical1ns/1ps effective timing. Production RTL and clock are unchanged.

The new `--stage x-state --sim icarus --hp 0 --kind 0` test stops at28805ns:
main prologue `sw s0,8(sp)` atPC800001b4 writes32Xbits to RAM800103f8,
valid/ready/write1,maskF. Startup has not initialized callee-saved s0. Unlike the
original read payload, this is a real write; its relevance to later execution
requires review. No firmware change, X coercion or exclusion was applied.
This is not evidence of an X on a completed CPU read. Verilator equivalent,
new pause/main runs and subsequent signoff stages were not run after this stop.
The prior focused Verilator pause PASS remains historical only.

## Deterministic software entry

The original `sw s0,8(sp)` at PC800001b4 belongs to main's prologue. The
compiler saves callee-saved s0/s1 before using them for CSR/mailbox bases across
calls. Startup had not initialized them. The saved values are never reloaded in
this nonreturning main; both registers are explicitly assigned before address use.
Unspecified incoming saved-register values are compatible with the
[RISC-V calling convention](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/#_integer_register_convention),
but accepted writes must be deterministic under this project's verification policy.

Only firmware/start.S changed: after RAM/data setup,29ADDI instructions zero
x3–x31; final stack setup establishes sp=80010400 and callmain establishes ra.
x0 is not written. gp/tp are unused zero context values: no TLS, small-data or
global-pointer relaxation. No CRT,trap framework or CPU reset modification.
A read-only startup observer checks all31 writable register values from actual
CPU commit signals before main's first instruction retires. Existing X checks
remain intact for every accepted write and required read response.

Reproducible LLVM21.1.8/LLD22.1.8 build:601 RV32I instructions,ILP32,2404-byte
payload in4096-byteROM,entry80000000. X-state tests PASS bothsimulators32980ns:
prologue saveszero,ABI_VERSION00010000,SCRATCH81234567; exact transaction match.
Pause tests PASS both45280ns:529pausededges,32resumedsamples,exactphase/waveform.
Maincompacttone PASS both382770ns:10000-sample acceptance,zeroI/Q/marker mismatches,
noalignmentcorrection,two toneSTART/BAD_COMMAND rejections,exactcross-sim results.

Next compactchirp Verilator test stops at143740ns:10000samples matched, but final
assertion requires modelDONE=true after firmware has issued CLEAR_STATUS before
itsPASS mailbox. That assertion was not changed. No laterprofile,resetcampaign,
formal,synthesis,LIFCL orfinalbaseline run followed this failure.

## Milestone 6.2 continuation — completion lifecycle and final verification

The earlier compact-chirp final `m.done` assertion was a testbench final-state
assumption error. In the signed-off design, engine completion is a one-cycle
event on the final valid chirp sample. The CSR captures it into sticky
`STATUS.DONE`; firmware polls until `BUSY=0`, reads and verifies `DONE=1`, then
issues `CLEAR_STATUS`. That command intentionally clears sticky DONE and errors
before firmware writes its PASS mailbox. The Python model's `m.done` is the
sticky software-visible DONE state, not the one-cycle engine event. The observer
checks the full lifecycle while retaining exact waveform comparisons.

Compact-chirp Verilator and Icarus trace, zero-based engine cycles:

| Event | Cycle |
|---|---:|
| START accepted | 3,664 |
| 10,000th/final sample and end marker; engine done event | 14,193 |
| BUSY deasserts and sticky STATUS.DONE asserts | 14,194 |
| Firmware poll observes BUSY=0 | 14,198 |
| Firmware explicitly observes DONE=1 | 14,216 |
| CLEAR_STATUS executes and DONE clears | 14,250 |
| Firmware PASS mailbox | 14,373 |

The focused completion lifecycle regression passes in both simulators with
matching event cycles. Compact chirp and high-purity chirp each produce exactly
10,000 accepted comparison samples; both tone profiles also produce exactly
10,000. I, Q, valid, start-marker and end-marker mismatch counts are all zero,
with no post-hoc alignment. Tone uses COMMIT then RUN_ENABLE; chirp adds START
after RUN_ENABLE. Illegal tone START commands return BAD_COMMAND and preserve
active configuration.

The complete firmware and waveform tests pass under Verilator and Icarus for all
four compact/high-purity tone/chirp profiles. Main and reset result records match
across simulators. Reset stress aborts and restarts at boot, active waveform and
pause locations for every profile; compact tone is also repeated at seed 6202.
Focused pause/resume checks 529 paused edges and at least 32 exact resumed
samples, preserving phase and pipeline state. CPU X-state checks require fully
resolved accepted write payloads and completed read responses.

The DBusSimple/Wishbone adapter has eight SAT assertions and six individually
reached cover goals. Yosys 0.52 proves the assertions by temporal induction at
depth 5. The environment constrains ACK/ERR to be mutually exclusive and
qualified by active CYC/STB. Read-response data is checked exactly; write
response data remains outside the architectural contract. Strict `--Wall`
integration lint passes for all four profiles; reviewed line/class waivers apply
only to immutable generated VexRiscv. Project-owned RTL remains unwaived. Generic
Yosys synthesis and `check -assert` pass: 32,369 compact-tone cells, 33,337
compact-chirp, 49,510 high-purity-tone and 50,897 high-purity-chirp cells.
Yosys reports that the existing CSR `shadow` array is replaced by registers to
implement its byte-write behavior. This expected memory-lowering warning is
not suppressed; the resulting netlists pass `check -assert`.

Offline nextpnr-nexus preflight routes both chirp profiles on LIFCL-40-9BG400C
against the documented native 12 MHz target. Compact reaches 91.78 MHz and uses
6,728 OXIDE_COMB, 1,496 OXIDE_FF and 1 OXIDE_EBR. High-purity reaches 94.41 MHz
and uses 6,836 OXIDE_COMB, 1,700 OXIDE_FF and 8 OXIDE_EBR. These are synthetic
preflight pins, not a board interface or physical measurement.

The final `scripts/run_verification_signoff.py` run passes: 247 tests, strict
baseline lint, randomized reset, Verilator/Icarus cross-simulation, 133 formal
assertion instances and 49/49 cover goals. Its frozen hash check passes; the
separate 170-entry Milestone 6.2 protected-hash manifest also has zero changes.
The CPU runner's `--stage all` evidence audit also passes, checking all four
profile transcripts, focused regressions, reset seeds, formal covers, synthesis,
preflight results and protected hashes together.
Canonical VexRiscv SHA256 remains
`0929e8fa42b8f6641fbb4c09b2ca65132ae7cf63777f16010151fa372852463c`. Firmware
remains RV32I/ILP32 with deterministic startup. ABI 1.0 and all production
control/waveform RTL remain unchanged. No hardware, sudo, openFPGALoader or Git
publication action was used.
