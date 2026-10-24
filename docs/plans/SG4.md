# SG4 plan: the ALU

SG4 is the fourth task of M16 in snax-forge, after SG3. It built the
hand-written ALU model `SnaxAluShell` (since removed with the ALU, #28) with
`snax_alu_csr.sv`'s rules (start handshake, busy, counter), in the test
datapath's place. Acceptance: `snax-alu` prints `Accelerator Cycles: 25` and
`Number of errors: 0` on SNAX-GVSoC, as on the RTL. Closed 2026-10-14; the
log is `docs/notes/NOTES.md` (SG4 steps 1 to 8).

## The ALU on the RTL

From source at snax_cluster `b2672f8` (`hw/snax_alu/src/`).

- CSRs from 978: mode, length, start (read-write), busy, counter
  (read-only). A write to a read-only CSR hits a Chisel `assert`.
- Start: a write with bit 0 set raises `valid` in its cycle s; `ready` is
  tied to 1, so the start is never held. Mode and length are latched at the
  end of s.
- Busy: 1 from s + 1, dropped after the firing at which
  `len_counter == length - 1`; if that firing lands in s, the end wins.
  `len_counter` is reset only at the end of a run, not by a start; length 0
  never ends.
- Counter: set to 1 by the start, then + 1 at the end of every busy cycle in
  which `len_counter != length - 1`; its final value is f - s + 1, with f
  the cycle of the second-to-last firing.
- Firing: combinational (L = 0, II = 1), when busy, A, B and the writer are
  ready. The writer's `ready` is the AND of its lane queues' `enq.ready`: a
  full queue is not ready even when it is emptied in that cycle.

## Steps

All done 2026-10-14: P1, this plan; P2, `SnaxAluShell` in place of the test
datapath (removed), `snax-stream` on the ALU's modes; P3, the core's
warnings on the two CSR forms (removed in SG6); P4, `alu-timing` (since
removed, #28), five cases, each comparing the counter (977 or 982) that does
not depend on the core's timing; steps 5 and 6, the same ELFs on the RTL
(author's run) and the counters on both sides; P5 skipped, no gap; P6, SG4
closed in snax-forge.

## Decided

- The ALU model copies `snax_alu_csr.sv`, start while busy included.
- Timing against the RTL by running the same ELFs on both sides and
  comparing counters; no values predicted up front. "Same ELF on both
  sides" became a feature of the whole system (D123 in snax-forge).
- P3's reading found two more CSR-form differences (the RTL's `rd` on
  `csrrw`, GVSoC's write-back on the no-write forms); both fixed in SG6.
- Result: every counter that does not depend on the core's timing equals
  the RTL in `snax-alu`, `snax-stream` and all five `alu-timing` cases, with
  0 errors on both sides; `snax-alu` prints `Accelerator Cycles: 25` and
  `Number of errors: 0` on both.

## SG5 starts from

- The two start writes land about 2 cycles further apart on SNAX-GVSoC than
  on the RTL: 5 against 3 cycles (streamer, then ALU, in `snax-stream`), 6
  against 4 (ALU, then streamer, in `alu-timing`).
- The printed `mcycle` start gaps differ more than the CSR writes (-16
  against -5 in `alu_first`): they include the `mcycle` reads and the calls
  around them.
- The first-cycle ordering (SG3) is not shown wrong, only not visible in a
  counter: with full readers a refill request one cycle late is absorbed by
  the 8 beats buffered.
