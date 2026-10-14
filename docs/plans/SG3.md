# SG3 plan: the streamer

SG3 is the third task of M16 in snax-forge, after SG2. A streamer model with
its parameters named as in the hjson's streamer template, simple timing with
hooks, and a crossbar that arbitrates its TCDM ports per bank as the plain
interconnect does. Acceptance: standalone tests of `snax-alu`'s three
streamers; per-bank arbitration of a streamer port shown in a trace.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply` on the branch
  `ry/sg3-streamer`; commits and pushes are done by hand, and the branch
  reaches main by a squash merge.
- Anything not verified is said so.

## The streamer on the RTL

From source at snax_cluster `b2672f8` (`hw/chisel/.../streamer/`,
`readerWriter/`, `reqRspManager/`, `utils/ComplexQueue.scala`). The hjson's
`snax_alu_streamer_template` gives two readers and one writer, each with
`spatial_bounds` [4], `temporal_dim` 1, `num_channel` 4 and `fifo_depth` 8;
each channel is one 64-bit narrow TCDM port, 12 in all.

- CSRs: per mover 2 + len(`spatial_bounds`) + 2 x `temporal_dim` read-write
  CSRs (pointer low and high, spatial stride, temporal bound, temporal
  stride), 5 here; then the start CSR; then `busy` and the counter, read-only.
  That is 960 to 977. The AGU keeps the low log2(128) + 10 = 17 bits of the
  pointer, so `0x1000_0000` is TCDM offset 0.
- Start: a write of 1 to the start CSR raises `valid`; `ready` is the
  streamer being idle, so the write is taken in its cycle when the streamer
  is idle and held while it is busy. Other writes are taken at any time;
  the configuration is copied at start.
- AGU: busy the cycle after start, if every temporal bound is nonzero. Each
  cycle it pushes one group of addresses into one address FIFO per channel
  (depth `fifo_depth`, pipe), when all of them have room. The first request
  comes two cycles after start (as D32 in snax-forge).
- Requestor, per channel: a reader requests when an address waits and it
  has credit (reads in flight plus beats buffered at most `fifo_depth`; a
  pop frees credit in the same cycle), a writer when an address and data
  wait. A request is held until granted.
- Reader data: back one cycle after the grant, into one queue per channel;
  a beat (lanes x 64 bit) goes out when every channel holds data. With
  temporal stride 0 on loop 0 the beat is handed out `tbound[0]` times.
- Busy and counter: a mover is busy while its AGU is busy or an address
  waits, so a reader is done at its last grant, with data still buffered.
  The streamer goes idle the cycle after every mover is done. The counter
  resets when the streamer turns busy and counts its busy cycles. Derived,
  not measured: counter = g - s, with s the cycle the start write is taken
  and g the cycle of the last grant; 0 for a start with a zero bound, 9 for
  8 uncontended beats.

## The path around it

- Core to accelerator (`snitch.sv`, `snitch_cc.sv`,
  `snax_intf_translator.sv`, `snax_csr_mux_demux.sv`): a SNAX CSR is
  offloaded through a 2-deep cut (`isochronous_spill_register`, since
  `register_offload_req`); a write is posted, with no response. The mux is
  combinational: addresses below 18 to the streamer, the rest to the ALU's
  manager with 18 subtracted. `csrrw` only writes and `csrrs` / `csrrc`
  only read on the RTL; D120's read before a write when `rd` is not `x0`
  differs, which `snax-alu` does not hit (SG5).
- Plain interconnect (`snitch_tcdm_interconnect.sv` with
  `sparse_interconnect: false`, common_cells `stream_xbar` and
  `rr_arb_tree`): per bank one round-robin tree with `FairArb` and
  `LockIn`, no priority input (the streamer's priority bit is dropped).
  After a grant the pointer jumps to the next requester and it is not reset
  on idle cycles; when the input it points at does not request, the tree
  picks. Inputs are packed {AXI, cores, SNAX}, so the 12 SNAX ports are
  0 to 11. Read data comes one cycle after the grant. The bank is
  `(addr >> 3) & 31`. The DMA takes a whole superbank in a cycle it is
  active (`mem_wide_narrow_mux`).

## In GVSoC today

- `L1_interleaver` forwards each access to its bank without arbitration.
  Banks are `memory.Memory` with latency 0 and 8 B width: a second access
  to a bank in a cycle gets one cycle of latency from the bank's
  cyclestamp, in call order.
- `log_ico_v2` arbitrates per bank by round robin, but on io_v2 with
  `memory_v3` banks; the cores are io v1. Not reused.
- A sync `Router` with bandwidth 0 and latency 0 forwards inline and adds no
  latency (`router.cpp`), so a CSR access passes in its cycle.
- Events of one cycle run in the order they are queued; one queued with
  delay 0 runs after those already queued (`clock_engine.cpp`).

## Not verified

- The input count of the RTL crossbar (counted 15); any count from 9 to 16
  gives the same 16-leaf tree, and the model's 12-input arbiter gives the
  RTL's 15-input winners when 3 inputs are idle (Icarus, SG3 step 3).
- Whether io v1 `DENIED` and grant pass through the cores' `pe_ico`
  routers; matters only if the cores join the crossbar.
- The writer's timing and the beats to and from the accelerator against the
  RTL: they need the ALU (SG4).

Checked since step 1: the RTL build's common_cells is v1.40.0 at `1281545`,
the commit read; the counter values, equal on the RTL in all five cases of
`stream-timing` (step 5).

## The model

| Component | Kind | Ports |
|---|---|---|
| `SnaxAluAcc` | Python composite, `snax_acc[0]` | `input` (CSR), `tcdm_0` to `tcdm_11` |
| `csr_mux` | sync `Router`, bandwidth 0 | 960 to 977 to the streamer, 978 up to the ALU slot, offsets from each block's first CSR |
| `SnaxStreamer` | C++ | `input` (CSR), `tcdm_0` to `tcdm_11`; from P5 `reader_0`, `reader_1` (beats out), `writer_0` (beats in) |
| ALU slot | `alu_regs` (the stub) up to P5, then `test_datapath` (`SnaxTestDatapath`); the ALU in SG4 | `input` (the ALU's 5 CSRs); from P5 `in_a`, `in_b`, `out` |
| `SnaxTcdmXbar` | C++, in `SnitchClusterTcdm` | `in_0` to `in_<n-1>` (SNAX ports), `out_0` to `out_31` on the same banks |

- Python takes `data_reader_params` and `data_writer_params` with the
  hjson's keys (`spatial_bounds`, `temporal_dim`, `num_channel`,
  `fifo_depth`); keys of features not modelled (reader-writers, configurable
  channels, logic word sizes, datapath extensions) are refused by name. The
  target gives the cluster `snax_tcdm_ports` 12.
- One cycle in three steps: request (the streamer's event posts its
  channels' requests and offers reader beats), arbitrate (the crossbar's
  event, queued with delay 0 by the cycle's first request: one winner per
  bank, its bank access now, read data the next cycle, losers held), commit
  (the streamer's event, delay 0, queued after its requests: grants pop
  FIFOs and return credit, the AGU enqueues, busy and the counter move).
  Events run only while the streamer is busy.
- Beats between the streamer and the ALU slot are io v1 requests from the
  datapath: `OK` moves the beat this cycle, `DENIED` does not (no grant
  follows); a size-0 request is a probe. The datapath's event runs before
  the streamer's step in a cycle, so a pop returns credit in time for that
  cycle's requests.
- The test datapath copies A or B to the output, one firing at most every
  `k` cycles (mode bit 0 and bits 7:4).

## Tests

| Test | Where | Checks |
|---|---|---|
| `stream-timing` | RTL and SNAX-GVSoC | Readers only, the writer's bound 0, at most 8 beats per lane: a zero-bound start; A alone; A and B on other banks; A and B on the same banks (B = A + 1 KiB); A with spatial stride 0 (four lanes on one bank). The counter per case, equal on both sides; the same-bank case traced per bank |
| `snax-stream` | SNAX-GVSoC | `snax-alu`'s three streamers as `snax-alu` sets them (25 beats, A, B, O at +0, +800, +1600 B); the datapath copies A, then B, at k = 1 and 3; the output equals A or B |
| `snax-alu` | SNAX-GVSoC | Runs to the end; both busy polls end |
| Regression | SNAX-GVSoC | `stream-timing`, `snax-csr`, `dma-timing`, the 17 plain tests on `snitch` |

## Steps

| # | Step | Status |
|---|---|---|
| 1 | P1: this plan; the reading in the notes | done 2026-10-13 |
| 2 | P2: `SnaxAluAcc` with the CSR router and two stubs. `snax-alu`'s 22 accesses and `snax-csr`'s 108 at the cycles and values of main before P2; `snax-csr` four lines of `0 errors` | done 2026-10-14 |
| 3 | P3: `SnaxTcdmXbar`; the streamer's CSRs, start, busy, counter, AGU and readers; `stream-timing`. Counter per case on SNAX-GVSoC and the same-bank trace | done 2026-10-14 |
| 4 | The same ELF on the RTL (author's run): the printed lines and the common_cells commit in `Bender.lock` | done 2026-10-14 |
| 5 | The counter per case on both sides, each gap named. Findings only | done 2026-10-14 |
| 6 | P4: the gaps of step 5; skipped if there are none | skipped 2026-10-14: no gap |
| 7 | P5: writers, the beat ports, the test datapath; `snax-stream`; `snax-alu` runs to the end | done 2026-10-14 |
| 8 | P6: SG3 closed here, and the STATUS.md and DECISIONS.md update for snax-forge | done 2026-10-14 |

## Decided

- The crossbar copies `rr_arb_tree` as the plain interconnect uses it, not
  SNAX-MODEL's arbiter of D31 in snax-forge, which copies the sparse
  interconnect (priority mask, pointer reset on idle cycles). D31 stays
  SNAX-MODEL's; SG3's choice is D122 in snax-forge. Checked against
  common_cells' `rr_arb_tree` in Icarus and by the RTL's counter in all
  five `stream-timing` cases.
- Only the SNAX ports go through the crossbar. The cores and the DMA keep
  their paths into the same banks, where a clash with a streamer shows as
  one cycle of latency on the later access, not as a round-robin stall.
  `snax-alu` has none: the DMA is done about 1000 cycles before the start
  and the cores poll CSRs. The cores join, and the DMA's superbank priority
  comes in, when a program's numbers call for it (SG5 or later).
- A start while the streamer is busy is refused with a warning naming it;
  holding it with a pending answer (D120) waits for a program that needs
  it. `snax-alu` starts an idle streamer.
- The streamer's own timing runs on the RTL in SG3 with readers only (no
  ALU needed); timing with the writer or the ALU's counter (982) is SG4's.
- One streamer component, configured from the hjson's streamer template
  with its keys; the beats move by the accelerator's requests (a size-0
  probe, then the beat), and the accelerator's event runs before the
  streamer's in a cycle.
- A test datapath holds the ALU's place and CSR layout until SG4; it is
  not the ALU and runs on SNAX-GVSoC only.
- Per mover the streamer classes its cycles as SNAX-MODEL did and names its
  crossbar ports by owner; the structured output for the views (open item
  57 in snax-forge) comes later.
- Result: the streamer's counter equals the RTL in all five
  `stream-timing` cases; `snax-stream` moves snax-alu's three streams with
  0 errors at one firing per cycle and per 3 cycles; `snax-alu` runs to the
  end on SNAX-GVSoC.

## SG4 starts from

- The ALU model replaces `test_datapath` in `snax/snax_alu_acc.py`, on the
  same CSR range (978 to 982) and the same beat ports (`in_a`, `in_b`,
  `out`, probe first). `snax_alu_shell_wrapper.sv`, `snax_alu_pe.sv` and
  `snax_alu_csr.sv` set its rules: it takes A and B together, only while
  busy and when its output can go; busy and its counter as
  `snax_alu_csr.sv` counts them.
- The datapath's first cycle may run after the streamer's step in that
  cycle (SG3 step 7), which delays a request by one cycle at most; the ALU
  model checks it against the RTL.
- The writer's timing and the beats are not checked against the RTL yet:
  they need the ALU. `snax-alu`'s cycles on both sides (`Accelerator
  Cycles: 25` on the RTL) are SG4's acceptance; the cycles per phase SG5's.
- `snax-csr` leaves out both start CSRs; `snax-stream` uses the test
  datapath's mode bits and stays a SNAX-GVSoC test (or moves to the ALU's
  modes in SG4).
- From the reading in step 1, for SG5: the RTL's `csrrw` on a SNAX CSR only
  writes and `csrrs` / `csrrc` only read, where D120 reads before a write;
  the core's issue and polling around the CSRs; the cores' path into the
  banks outside the crossbar.
- The housekeeping pass over SG1's to SG3's code comes after SG5.
