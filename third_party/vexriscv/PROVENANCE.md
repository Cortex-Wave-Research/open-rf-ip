# Pinned VexRiscv RTL

This generated RTL is intentionally vendored for an optional, separate control
processor demonstration. It is not used by the waveform IP or its normal builds.
**Do not hand edit, reformat, or convert `VexRiscv.v`.** Regeneration is a
maintenance operation; ordinary open-rf-ip simulation and synthesis require no
Scala, SBT, SpinalHDL, Java, or network access.

| Item | Pinned/confirmed value |
|---|---|
| Official project | [SpinalHDL/VexRiscv](https://github.com/SpinalHDL/VexRiscv) |
| Upstream revision | `baf7dc82f855eddaf5b0a20a6802c526f127e38a` |
| Generator | `vexriscv.demo.GenSmallestNoCsr` |
| JDK used for both successful generations | OpenJDK `17.0.20.1` |
| SBT | `1.6.0` |
| Project Scala | `2.12.18` (SBT's internal Scala is separate) |
| SpinalHDL core/lib/compiler plugin | `1.13.0` |
| SpinalHDL runtime git head | `d9d72474863badf47d8585d187f3e04ae4749c59` |
| ISA / firmware target | RV32I, little endian; `-march=rv32i -mabi=ilp32`, limitations below |
| Reset vector | `0x80000000` |
| Top | `VexRiscv` |
| RTL SHA256 | `0929e8fa42b8f6641fbb4c09b2ca65132ae7cf63777f16010151fa372852463c` |
| RTL size | 134,457 bytes, 2520 newline-terminated lines |
| License | MIT, Copyright (c) 2016 Spinal HDL contributors |
| Unmodified upstream LICENSE SHA256 | `230178ba3f6cb6cf94ec301a9208fa6870e62c1ed83f20543f059622c3619760` |

The operator reported successful JDK 17 generation A and B. An independent
offline audit of both raw files found the SHA256 above for **each**, 2520 lines
and 134,457 bytes each, and `cmp` exit **0**. The canonical file was copied
byte-for-byte from A and independently rehashed. No generation was repeated
during closure. Successful Java/SBT execution is operator-confirmed; the RTL
header independently records the upstream and SpinalHDL revisions. Local SBT
compilation records confirm the Scala 2.12.18 and SpinalHDL 1.13.0 classpath.

## Source evidence and implemented configuration

All source links below refer to the exact revision:

- [Generator](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/demo/GenSmallestNoCsr.scala)
  selects the simple buses, integer ALU, light iterative shifter, synchronous
  32-by-32 register file, hazard interlocks without forwarding, and late branches.
- [Build](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/build.sbt)
  pins project Scala and SpinalHDL; [SBT version](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/project/build.properties)
  pins SBT. The different Mill build was not used.
- [Integer ALU](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/IntAluPlugin.scala),
  [shifter](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/ShiftPlugins.scala),
  and [branch decoder](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/BranchPlugin.scala)
  provide RV32 integer register/immediate arithmetic, comparisons, logical
  operations, six shifts, LUI/AUIPC, six conditional branches and JAL/JALR.
  The data plugin decodes LB/LH/LW/LBU/LHU and SB/SH/SW.
- Generated RTL contains 32-bit register/data/address paths and a 32-entry
  register file (lines 655, 750–767), PC increments of four with aligned fetch
  addresses (657–658, 1383–1388, 1479), and no compressed decode
  (`isRvc = 0`, line 1490). ALU/shifter/branch logic and the load/store lane
  selection are present, not inferred only from the generator name.
- `VexRiscv.v:2113–2115` explicitly resets the PC to `32'h80000000`.
  Load byte selection at 1569–1584 and store mask/data at 1531–1566 establish
  little endian behavior: lowest addressed byte is bits 7:0 of an aligned word.

No M, A, C, F/D, Zicsr, caches, MMU, architectural CSR/trap handler, interrupt
controller, or debug plugin is instantiated. The RV32I firmware target describes
the integer execution subset, **not certification of a complete privileged or
exception-capable RISC-V execution environment**. ECALL/EBREAK traps and
privileged instructions are unavailable. FENCE is decoded as no additional
operation by DBusSimplePlugin; IBusSimplePlugin similarly accepts FENCE.I as
an empty action. Do not infer self-modifying-code synchronization or a tested
Zifencei implementation. Firmware should use fixed code and ordered MMIO.

## Complete external port inventory

Directions are relative to `VexRiscv`; every top-level port is listed here.

| Port | Direction / width | Meaning |
|---|---|---|
| `clk` | input 1 | Rising-edge clock |
| `reset` | input 1 | Active-high asynchronous assertion (`posedge reset`) |
| `iBus_cmd_valid` | output 1 | Instruction request offered |
| `iBus_cmd_ready` | input 1 | Instruction request accepted with valid |
| `iBus_cmd_payload_pc` | output 32 | Byte PC; bits 1:0 zero |
| `iBus_rsp_valid` | input 1 | Instruction response valid |
| `iBus_rsp_payload_error` | input 1 | Fetch error indication; no trap handling here |
| `iBus_rsp_payload_inst` | input 32 | Instruction word |
| `dBus_cmd_valid` | output 1 | Data request offered |
| `dBus_cmd_ready` | input 1 | Data request accepted with valid |
| `dBus_cmd_payload_wr` | output 1 | 1 store, 0 load |
| `dBus_cmd_payload_mask` | output 4 | Active-high byte lanes |
| `dBus_cmd_payload_address` | output 32 | Full byte address, including offset |
| `dBus_cmd_payload_data` | output 32 | Store data, replicated for subword stores |
| `dBus_cmd_payload_size` | output 2 | 0 byte, 1 halfword, 2 word; 3 unsupported |
| `dBus_rsp_ready` | input 1 | Read response available/completed, **not CPU backpressure** |
| `dBus_rsp_error` | input 1 | Unused with access-fault catching disabled |
| `dBus_rsp_data` | input 32 | Full aligned read word, CPU selects/sign-extends lanes |

No interrupt, debug/JTAG, architectural state/trace, reset-vector configuration,
timer, external register-file, Wishbone, or other architectural ports exist.
The file also contains internal `StreamFifoLowLatency` and `StreamFifo` modules.
Data pipeline/register-file contents are not all reset (`zeroBoot=false`).
Future system reset must reset adapters too, discard stale responses and release
reset synchronously to the clock; firmware must initialize the state it uses.

## Bus semantics and architectural suitability

**YES:** the unchanged core can connect instruction bus to firmware ROM/RAM and
data bus to an address decoder and future adapter to the existing open-rf-ip
Wishbone/CSR control plane. These are external modules; no CPU editing is needed.
No such integration has happened in this milestone.

[IBusSimpleBus/Plugin source](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/IBusSimplePlugin.scala):
commands transfer on a rising edge with valid AND ready. Responses are an
unbackpressured Flow: exactly one ordered response per accepted command, no
response-ready output and no transaction IDs. Minimum response latency is one
cycle. `pendingMax=7` is a configured upper bound, not a requirement to accept
seven requests externally. A serialized memory can backpressure commands.
`cmdForkPersistence=false`: an unaccepted fetch may be withdrawn on pipeline
flush; capture only on handshake. Accepted fetches must still receive their
responses after a branch flush; the CPU discards obsolete responses internally.
Do not treat a stalled, unaccepted request as a committed memory transaction.

[DBusSimpleBus/Plugin source](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/DBusSimplePlugin.scala):
commands likewise transfer with valid AND ready. A load enters the memory stage
after acceptance, stalls there until `dBus_rsp_ready`, and consumes `rsp_data`.
Return a registered response no earlier than the following cycle; there is no
CPU response-ready output. Stores finish at command acceptance with **no separate
write-response channel**. Preserve ordering and never acknowledge a write unless
the adapter owns/completes it. A conservative adapter can hold command ready low
until Wishbone ACK/ERR, then register load response data for the following cycle.
Drive each Wishbone request once, obey its termination/re-arm timing, and handle
bus errors explicitly outside the CPU; neither error input causes a CPU trap.

For size 0/1/2 the mask is `(0001/0011/1111 << address[1:0]) & 1111`.
Byte stores repeat the low byte four times; halfword stores repeat the low half
twice; word stores use the full register. Map mask directly to Wishbone SEL and
preserve lanes in the returned aligned word. Require naturally aligned accesses;
misalignment is neither fixed up nor trapped. Decode all 32 address bits before
forming the existing 16-bit **byte-addressed** CSR offset. Upstream's illustrative
Wishbone converter uses word addresses and must not be copied blindly.
An external CSR is ordinary memory-mapped I/O; absence of the CPU CsrPlugin
does not prevent access to it. The CPU stays outside the waveform sample path.

## Illegal-instruction warning and firmware obligations

The generator warns: “This VexRiscv configuration is set without illegal
instruction catch support.”
[DecoderSimplePlugin](https://github.com/SpinalHDL/VexRiscv/blob/baf7dc82f855eddaf5b0a20a6802c526f127e38a/src/main/scala/vexriscv/plugin/DecoderSimplePlugin.scala)
emits this because `catchIllegalInstruction=false`. Unsupported opcodes have no
reliable exception/recovery contract and must not be treated as safe NOPs.
This is acceptable for the intended controlled bare-metal polling firmware,
provided Milestone 6.2 enforces all of the following:

- Compile every source, startup object and runtime library for exactly
  `-march=rv32i -mabi=ilp32` (LLVM also `--target=riscv32-unknown-elf`).
- Audit the final linked disassembly, including compiler helpers and runtime
  paths, for unsupported instructions. Do not assume compiler flags alone suffice.
- Avoid CSR/privileged/atomic/compressed/multiply/divide/floating-point
  instructions, ECALL/EBREAK, trap-based termination and runtimes relying on
  illegal-instruction traps. Use supported software arithmetic helpers as needed.
- Initialize stack/data/state, obey alignment, and use explicit polling/status
  completion with external MMIO error handling. No interrupts or fault recovery.

No CPU features were enabled merely to remove this warning. This milestone
does not perform an ISA compliance test or execute firmware.

## Exact regeneration procedure

The selected SBT generation task, from the pinned checkout, is exactly:

```sh
"$JAVA_HOME/bin/java" -Xmx2G -Dsbt.supershell=false \
  -jar "$SBT_LAUNCH_JAR" 'runMain vexriscv.demo.GenSmallestNoCsr'
```

Here `JAVA_HOME` selects a JDK 17 (tested generation: OpenJDK 17.0.20.1), and
`SBT_LAUNCH_JAR` is the official SBT 1.6.0 launcher. This is the reproducible
task invocation; the operator's successful terminal transcript/ancillary JVM
flags were not archived, so they are not represented as independently observed.
The generation task and tool versions are operator-confirmed and source-audited.

Official launcher distribution:
[sbt-1.6.0.tgz](https://github.com/sbt/sbt/releases/download/v1.6.0/sbt-1.6.0.tgz),
archive SHA256 `639db170f6510d0f885ff40054644e0ec85bb836f9a09038e6bf4e4f6271bacc`;
`sbt/bin/sbt-launch.jar` SHA256
`627ddd9b3524369edaf891577a0c59e8bf70e783f751c12f4be779663ad29844`.

Use the [maintenance helper](../../scripts/regenerate_vexriscv.py) from the
repository root:

```sh
python3 scripts/regenerate_vexriscv.py --check third_party/vexriscv/VexRiscv.v
python3 scripts/regenerate_vexriscv.py --regenerate \
  --java-home "$JAVA_HOME" --sbt-launch "$SBT_LAUNCH_JAR"
```

Optional `--checkout /path/to/clean/pinned/VexRiscv` uses a local official checkout
as the clone source. The helper verifies its origin, revision and tracked-file
cleanliness, creates a fresh checkout under ignored `build/`, and checks both
Java and javac major version 17 and the exact launcher hash. It selects the
pinned SBT/Scala/SpinalHDL build unchanged, isolates caches, logs the exact expanded
Java command, and compares raw output bytes/hash against the canonical snapshot.
Network and generator tools are needed only for explicit regeneration (unless
already supplied/cached); they are never normal build dependencies. PASS/FAIL
is explicit. The helper has no canonical overwrite mode. Its offline comparison
and rejection paths were checked at closure; full generation through this newly
written helper was intentionally not rerun. The A/B evidence is the existing
operator generation, not a claimed third generation.

## Validation boundary

CPU-only Verilator 5.032 parse/elaboration and Icarus 12.0 parse/elaboration
passed on this same canonical file. Strict Verilator `--Wall` initially exited
1 due to 79 warnings: 1 DECLFILENAME, 77 UNUSEDSIGNAL, 1 WIDTHTRUNC. All diagnostics
were retained; a reviewed `--Wall -Wno-fatal` run exited 0. No blackboxing or RTL
warning-suppression edits were used. The 33-to-32-bit right-shift truncation at
line 677 deliberately retains `{SRA && sign, operand[31:1]}`; the discarded
extension bit cannot change the 32-bit result. Unused signals are generated
metadata/disabled features (including the documented error/trap limitation),
and subsidiary module names explain DECLFILENAME. No semantic blocker was found.

Yosys 0.52 read/hierarchy/process lowering, `check -assert`, generic synthesis,
and final `check -assert` passed without warnings. The CPU hierarchy contains
5697 generic leaf cells, including 1586 FF bits. Before memory mapping there is
one 32x32 register-file memory (two synchronous reads, one write); afterward no
memories remain. Coarse arithmetic includes five `$alu` and two `$macc_v2`
cells with **zero products**, plus a mask shift; no multiplier/divider exists.
These are generic counts, not LIFCL resources, mapping or timing results.

CPU/CSR integration has **NOT** happened. Firmware integration/execution has
**NOT** happened. Physical FPGA CPU execution has **NOT** happened. No hardware
was accessed. The next stage is separately verified Milestone 6.2 simulation
integration, preserving this canonical RTL unchanged.
