# SG4 plan: the ALU

SG4 is the fourth task of M16 in snax-forge, after SG3. The hand-written ALU
model with `snax_alu_csr.sv`'s rules (start handshake, busy, counter), in
the test datapath's place. Acceptance: `snax-alu` prints `Accelerator
Cycles: 25` and `Number of errors: 0` on SNAX-GVSoC, as on the RTL.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply` on the branch
  `ry/sg4-alu`; commits and pushes are done by hand, and the branch reaches
  main by a squash merge.
- Anything not verified is said so.

## The ALU on the RTL

From source at snax_cluster `b2672f8` (`hw/snax_alu/src/`,
`hw/templates/snax_acc_wrapper.sv.tpl`, `snax_csrman_wrapper.sv.tpl`,
`hw/chisel/.../reqRspManager/ReqRspManager.scala`, `readerWriter/Writer.scala`,
`utils/ComplexQueue.scala`). The hjson's `snax_acc_cfg` gives the ALU
`snax_num_rw_csr` 3 and `snax_num_ro_csr` 2; the shell wrapper `NumPE` 4 and
`DataWidth` 64.

- CSRs, offsets from the ALU's first CSR (978): 0 mode, 1 length, 2 start,
  read-write in the ReqRspManager; 3 busy, 4 counter, read-only. Reads are
  answered in their cycle; the read-write CSRs read back what was written,
  so 980 reads 1 after a start. A write to 3 or 4 hits a Chisel `assert`.
- Start: a write to offset 2 with bit 0 set raises `readWriteRegIO.valid`
  in its cycle s, with the registers as they stand (mode and length written
  before). `snax_alu_csr.sv` ties `ready` to 1, so the start is never held.
  A write with bit 0 clear only stores the value. Mode (bits 1:0) and length
  are latched at the end of s; the datapath uses the latched copies.
- Busy: a register, 1 from s + 1, dropped after the firing at which
  `len_counter == length - 1`. If that firing lands in s, the end wins: busy
  goes to 0 with the new mode and length latched.
- `len_counter` counts firings and is reset only at the end of a run, not by
  a start. A start while busy keeps the firings done; if they are already at
  or past the new `length - 1`, the run ends only when the 32-bit counter
  wraps. Length 0 never ends (`len_counter == 0xFFFFFFFF`).
- Counter: set to 1 by the start (visible at s + 1), then + 1 at the end of
  every busy cycle in which `len_counter != length - 1`; held after the run.
  Its final value is f - s + 1, with f the cycle of the second-to-last
  firing: f_last - s when the firings are back to back, 1 with length 1
  however long the ALU waits.
- Firing: combinational (L = 0, II = 1). Busy, A valid, B valid and the
  writer ready in one cycle; both readers are popped together and the
  writer's `valid` is the firing. Per lane, 64 bit: add (mode 0, the
  `default`), sub, mul (low 64 bits), xor. Lane i is bits `i * 64` of a beat.
- The writer's `ready` is the AND of its lane queues' `enq.ready`
  (`ComplexQueueConcat`, `pipe = false`): a full queue is not ready even when
  it is emptied in that cycle, and a word pushed is visible the next cycle.
  SG3 modelled this rule; it is now read in `Writer.scala` too.
- No register slice between the streamer and the shell: the template wires
  them directly.

## In GVSoC today

- `SnaxTestDatapath` holds the ALU's 5 CSRs and the beat ports `in_a`,
  `in_b`, `out` (probe first). It copies A or B, refuses a start while busy,
  is busy from s + 1 to its last firing, and its counter ends at
  f_last - s. `snax-alu` prints `Accelerator Cycles: 25` and `Number of
  errors: 97` on it (SG3 step 7).
- Its event runs before the streamer's step in a cycle, except possibly at
  its first cycle, which delays a reader's request by one cycle at most
  (SG3 step 7).
- The Snitch core follows Zicsr on SNAX CSRs (D120 in snax-forge): `csrrw`
  with `rd` not `x0` reads before it writes, `csrrs` / `csrrc` with a mask
  write. The RTL only writes on `csrrw` and only reads on `csrrs` /
  `csrrc` (open item 62); nothing warns on these forms.

## Not verified

- The writer's timing and the beat handshake as measured on the RTL: read
  only, in SG3 and above; `alu-timing` measures them.
- The first-cycle ordering in GVSoC against the RTL; `stream_first` is the
  case where it can show.
- What Verilator does on the ReqRspManager's `assert` for a write to 981 or
  982. The model warns and refuses it.

## The model

| Component | Kind | Ports |
|---|---|---|
| `SnaxAluShell` (`alu` in `SnaxAluAcc`) | C++, after `snax_alu_shell_wrapper.sv` | `input` (the ALU's 5 CSRs), `in_a`, `in_b`, `out` |

- Parameters: `csr_base`, `num_pe` (4) and `data_width` (64), as the shell
  wrapper's `NumPE` and `DataWidth`. Named after the shell wrapper:
  `snax_alu.py` is the target.
- The rules above, computed from s and the firing cycles when read, as the
  test datapath and the streamer do. A start in s takes effect at the end of
  s: a firing in s uses the old mode and length.
- Start while busy is taken as the RTL takes it, never refused. A warning,
  not a refusal, for a start with length 0 and for one that keeps a
  `len_counter` at or past the new `length - 1`; it does not stop the run
  (`force_warning_no_error`: GVSoC runs with `werror`, and the RTL just
  stays busy).
- A firing probes `in_a`, `in_b` and `out`, then moves all three or none, as
  the test datapath did. Its event runs every cycle while busy.
- How the ALU waits for its inputs and its output (`try_fire`) and what it
  does with a beat (`compute`) are one method each, so a later accelerator
  with another data interface changes only those.
- Trace: each firing; at the end of a run its cycle classes in D59's order
  at II = 1 (`busy` > `stall_out` > `stall_in` > `idle`), for open item 57
  in snax-forge.
- `SnaxTestDatapath` is removed.
- The Snitch core warns once per run on `csrrw` with `rd` not `x0` and once
  on `csrrs` / `csrrc` with a mask, in `SnaxCsr::handle()` (an upstream
  file): the forms where SNAX-GVSoC and the RTL differ. They warn without
  stopping the run, so `snax-csr` still tests D120's paths.

## Tests

| Test | Where | Checks |
|---|---|---|
| `snax-alu` | RTL and SNAX-GVSoC | `Accelerator Cycles: 25`, `Number of errors: 0` |
| `snax-stream` | RTL and SNAX-GVSoC | `snax-alu`'s three streams through its library, one run per mode (add, sub, mul, xor), 25 beats, 64-bit data with wrap; errors, the streamer's counter (977) and the ALU's (982) per run |
| `alu-timing` | RTL and SNAX-GVSoC | One ELF, five cases (below); errors, 977, 982 and the `mcycle` gap between the two starts per case |
| `snax-csr` | SNAX-GVSoC | Four lines of `0 errors` and the two CSR-form warnings |
| Regression | SNAX-GVSoC | `stream-timing`, `dma-timing`, the 17 plain tests on `snitch` |

`alu-timing`'s cases. The gap between the streamer's start and the ALU's is
the core's timing (SG5's), so each case names the counter that does not
depend on it; that is the one compared.

| Case | Order and layout | Counter compared | What it checks |
|---|---|---|---|
| `alu_first` | ALU (add, 25 beats), then the streamer; `snax-alu`'s layout | 977 | The path reader → ALU → writer and the writer's last grant |
| `stream_first` | The streamer, a wait of about 100 cycles (readers full), then the ALU | 982 | Firing from full readers; the first-cycle ordering |
| `out_same_banks` | As `stream_first`, O on A's banks lane by lane | 982 | The writer's back-pressure on the ALU |
| `len1` | Length 1, ALU first | 982 and 977 | The counter's end rule |
| `restart_idle` | Start (add, 100), start again (sub, 25), then the streamer | 977, O = A - B | A start while busy latches the new mode and length |

## Steps

| # | Step | Status |
|---|---|---|
| 1 | P1: this plan; the reading in the notes | done 2026-10-14 |
| 2 | P2: `SnaxAluShell` in the test datapath's place (removed); `snax-stream` on the ALU's modes. `snax-alu` prints `Accelerator Cycles: 25` and `Number of errors: 0` on SNAX-GVSoC; `snax-stream` 0 errors in all four modes | done 2026-10-14 |
| 3 | P3: the core's warnings on the two CSR forms; `snax-csr` four lines of `0 errors` and both warnings | done 2026-10-14 |
| 4 | P4: `alu-timing`; its counters and errors on SNAX-GVSoC | todo |
| 5 | The same ELFs on the RTL (author's run): `snax-alu`, `snax-stream`, `alu-timing`, the printed lines | todo |
| 6 | The counters per case on both sides, each gap named. Findings only | todo |
| 7 | P5: the gaps of step 6; skipped if there are none | todo |
| 8 | P6: SG4 closed here, and the STATUS.md and DECISIONS.md update for snax-forge | todo |

## Decided

- The ALU model copies `snax_alu_csr.sv`, start while busy included: the
  start is always taken and latches mode and length, `len_counter` is kept,
  the end wins over a start in the same cycle. A common start/busy protocol
  for all accelerators, with the snax_cluster changes it needs, is an open
  item in snax-forge (P6), formalized later.
- The test datapath is removed; `snax-stream` moves to the ALU's modes and
  runs on both sides, and timing lives in `alu-timing` only.
- Timing against the RTL by running the same ELFs on both sides and
  comparing counters (977, 982); no values predicted up front.
- "Same ELF on both sides" becomes a feature of the whole system (build
  once, run SNAX-GVSoC and RTL, compare); recorded in snax-forge's STATUS in
  P6, for SG5's regression and FLOW3 and GEN2.
- The ALU is SNAX's baseline, not the template of the accelerators made
  from BRMs (GEN3 in snax-forge): those may need the interface towards the
  data modelled more generally, and hooks for how an accelerator waits for
  its data. Taken up then; for now the waiting and the compute sit in one
  method each.
- SNAX-GVSoC keeps Zicsr on SNAX CSRs (D120); the RTL is fixed in
  snax_cluster later (`snitch.sv` decode, `snax_intf_translator.sv`), after
  the SG series. Until then SNAX-GVSoC warns on the two forms that differ,
  from SG4 on, since the same ELFs start running on both sides here.
- Two more findings from P3's reading, fixed right after the SG series
  together with the RTL: on the RTL, `csrrw` / `csrrwi` with `rd` not `x0`
  writes `rd` with `rs1` or the immediate plus the CSR number (the decoder's
  default ALU add), not with the CSR's value; and GVSoC's ISS (`priv.hpp`,
  shared by every core) writes on `csrrc` with `x0` and on `csrrsi` /
  `csrrci` with 0, where Zicsr writes nothing (`csrrs` already does not).
  SG4 only warns: no SNAX program uses these forms.
