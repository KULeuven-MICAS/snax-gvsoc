# SG3 plan: the streamer

SG3 is the third task of M16 in snax-forge, after SG2. It built a streamer
model (`SnaxStreamer`) with its parameters named as in the hjson's streamer
template, simple timing with hooks, and a crossbar (`SnaxTcdmXbar`) that
arbitrates its TCDM ports per bank as the plain interconnect does (the plain
arbitration since removed, #28; the crossbar models the sparse interconnect,
SG7). Acceptance: standalone tests of `snax-alu`'s three streamers; per-bank
arbitration of a streamer port shown in a trace. Closed 2026-10-14; the log
is `docs/notes/NOTES.md` (SG3 steps 1 to 8).

## The streamer on the RTL

From source at snax_cluster `b2672f8` (`streamer/`, `readerWriter/`,
`reqRspManager/`, `utils/ComplexQueue.scala`); the ALU's streamer has two
readers and one writer of 4 channels each, one 64-bit TCDM port per channel.

- CSRs: per mover 2 + len(`spatial_bounds`) + 2 x `temporal_dim` read-write
  CSRs, then the start CSR, then `busy` and the counter, read-only.
- Start: a write of 1 to the start CSR is taken in its cycle when the
  streamer is idle and held while it is busy; the configuration is copied
  at start. The first request comes two cycles after start.
- Requestor, per channel: a reader requests when an address waits and it
  has credit (reads in flight plus beats buffered at most `fifo_depth`; a
  pop frees credit in the same cycle), a writer when an address and data
  wait. A request is held until granted; read data comes one cycle later.
- Busy and counter: a reader is done at its last grant, with data still
  buffered; the streamer goes idle the cycle after every mover is done. The
  counter counts its busy cycles: counter = g - s, with s the cycle the
  start write is taken and g the cycle of the last grant.
- Core to accelerator: a SNAX CSR is offloaded through a 2-deep cut; a
  write is posted, with no response.
- Plain interconnect: per bank one `rr_arb_tree` with `FairArb` and
  `LockIn`, no priority input.

## The model

- `L1_interleaver` forwards each access to its bank without arbitration; a
  second access to a bank in a cycle gets one cycle of latency, in call
  order. A sync `Router` with bandwidth 0 and latency 0 adds no latency.
- Events of one cycle run in the order they are queued; one queued with
  delay 0 runs after those already queued (`clock_engine.cpp`).
- The model's cycle in three steps: request (the streamer posts its
  channels' requests), arbitrate (the crossbar's event: one winner per bank,
  losers held), commit (the streamer's event: grants pop FIFOs and return
  credit). Events run only while the streamer is busy.
- Beats between the streamer and the accelerator are io v1 requests from
  the accelerator: `OK` moves the beat, `DENIED` does not; a size-0 request
  is a probe. The accelerator's event runs before the streamer's step.

## Steps

P1, this plan and the reading (2026-10-13); then on 2026-10-14: P2,
`SnaxAluAcc` (since removed, #28) with the CSR router and two stubs; P3,
`SnaxTcdmXbar`, the streamer's readers, `stream-timing`; steps 4 and 5, the
same ELF on the RTL (author's run) and the counter on both sides; P4
skipped, no gap; P5, writers, the beat ports, the test datapath (replaced
in SG4), `snax-stream` (since removed, #28); P6, closed in snax-forge.

## Decided

- The crossbar copies `rr_arb_tree` as the plain interconnect uses it
  (D122 in snax-forge), not SNAX-MODEL's (since removed, RET1) arbiter of
  D31, which copies the sparse interconnect. Checked against common_cells'
  `rr_arb_tree` in Icarus and by the RTL's counter.
- Only the SNAX ports go through the crossbar (replaced in SG7 round 3).
- One streamer component, configured from the hjson's streamer template;
  keys of features not modelled are refused by name.
- Result: the streamer's counter equals the RTL in all five
  `stream-timing` cases; `snax-stream` moved snax-alu's three streams with
  0 errors at one firing per cycle and per 3 cycles; `snax-alu` ran to the
  end on SNAX-GVSoC.
