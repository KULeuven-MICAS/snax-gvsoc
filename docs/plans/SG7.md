# SG7 plan: the sparse interconnect

SG7 (M16 in snax-forge, after CI1) put snax_cluster's sparse interconnect
in SNAX-GVSoC, amending D119 and D122, in five rounds; the log is
`docs/notes/NOTES.md`. It ran on two SNAX targets, `snax_alu` (the plain
pick) and `snax_alu_sparse`, with the apps `alu-timing` and `snax-alu`: all
since removed (CLN1 R2); only the sparse interconnect is modelled now.

## The sparse interconnect on the RTL

From snax_cluster `9fbf35d`: `hw/chisel/.../snax/sparse_interconnect/`,
`sparse_interconnect_wrapper.sv.tpl`, `snaxgen.py`, `snitch_cluster.sv`,
`readerWriter/`, `utils/ComplexQueue.scala`.

- Configuration. snaxgen's `sparse_config` lists ports `[width,
  granularity]`: per core each accelerator's `sparse_interconnect_config`
  (or `[snax_tcdm_ports, 1]`), `[16, 1]` per xDMA; then `[1, 1]` per core
  (no SSR); then `[1, 1]` for AXI. For `cfg/snax_alu_cluster.hjson`
  `[[12, 1], [1, 1], [1, 1], [1, 1]]`: 15 inputs (SNAX 0 to 11, cores 12
  and 13, AXI 14, packed `{axi_soc_req, tcdm_req, snax_tcdm_req_i}`), 32
  banks, 64-bit data, `priorityWidth` 1.
- Reach. Bank `(addr >> 3) & 31`. Index `j` of a port of granularity `g`
  reaches only banks `b % g == j % g`; bank `b` orders its inputs by
  `SparseConfig.get_global_idx_list(b)`, the global order when every `g` is 1.
- Pick, per bank and cycle: keep the valid requests at the highest valid
  priority (the mask). `previous` is last cycle's selection (`NumInp - 1` at
  reset). If `lock` and `previous` is in the mask, it wins; else the lowest
  masked input above `previous`; else the lowest masked input. An idle cycle
  selects the last input, so the next pick is the lowest masked one. `lock`
  is last cycle's `valid && !ready`: the winner was refused by the bank.
- Read data one cycle after the grant. Priority bit in the user field:
  streamer channels from `DataRequestor` (below), cores and AXI 0.
- The plain interconnect (`rr_arb_tree` per bank) has no priority, full
  reach, and an `rr_q` that moves past the winner and never resets on idle.
- The iDMA stays on the superbank mux under both (round 4).

## Model scope

| Kept | Left out |
|---|---|
| Per bank and cycle one winner: highest priority, then round robin from the last pick, reset after an idle bank cycle | valid / ready as signals; registers and encoders |
| A winner refused by its bank keeps its turn (the lock) | The arbiter nesting; the user-field packing |
| Reach by granularity; read data one cycle after the grant | The AMO shim; the wide-narrow mux internals |
| A request's priority taken by the RTL's hold rule | |

## The priority bit

- The hint is the lane's data-queue count after cycle c - 1: reader
  `count <= 1`, writer `count >= fifo_depth - 1`. `priorityHold` reloads in
  a cycle with no request or a firing one: a request first sent in t carries
  t - 1's hint and keeps it while resent. Without `dynamicPriority` the bit
  is `higherStaticPriority` (defaults true and false).
- SNAX-GVSoC: `priority_hint()` in `snax_streamer.cpp`, on a wire per SNAX
  port (`tcdm_prio_<i>`, `prio_<i>` on the crossbar), set before every send
  and resend. An unbound wire asks with 0, as the RTL's cores and AXI.

## The rounds

1 the sparse pick on the SNAX ports, checked against the RTL module, the
priority bit, `snax_alu_sparse`; 2 round 1's gaps (none); 3 the cores and
AXI, D125 refit, 3b its fix-ups; 4 the DMA's superbank (open item 58) and
a follow-up on its beat cycles; 5 close (snax-forge's D119, D122, STATUS,
the README). Tests: the winner check (`tests/snax/sparse_arb/`, Verilator,
by hand); `stream-timing` (new `prio_queued`, `idle_restart`),
`alu-timing`, `snax-alu` at five sizes, `core-tcdm`, `dma-tcdm`.

## Acceptance

- Round 1: the pick header gives the RTL module's selection on every bank
  and cycle of the winner check (both elaborated modules, and 12 inputs
  against 15); the compared counters (D123) of the sparse RTL and target
  equal; every prediction marked, every gap named; `make regress` passes.
- SG7: the sparse target with cores, AXI and the DMA gives the sparse RTL's
  counters, phases within SG5's target.

## Steps

All done: round 1 steps 1 to 9 and round 3's 3.1 to 3.6 on 2026-10-15;
3b.1 to 3b.5, 4.1 to 4.5, 4f.1, 4f.2 and the close 5.1 on 2026-10-16.

## Predictions

Made in step 8 from source, before any sparse RTL run; all held (round 1's
result). s is the streamer's start write.

`stream-timing`, counter 977:

| Case | Plain RTL | Sparse | Why |
|---|---|---|---|
| `zero_bound`, `a_alone`, `ab_other_banks` | 0, 9, 9 | 0, 9, 9 | No contention |
| `ab_same_banks` | 10 | 10 | Sparse: A first (pointer restarted); plain RTL: B, from `rr_q` the cores' stores leave |
| `a_stride0` | 12 | 12 | Lanes in turn on bank 0 |
| `prio_queued` | 5 (first run 5) | 6 (first run 5) | Priority: B (1) wins over A (0) |
| `idle_restart` | 5 (first run 2) | 6 (first run 2) | Idle restart: A wins where plain keeps B's turn |

`alu-timing`, compared counter:

| Case | Counter | Plain RTL | Sparse | Why |
|---|---|---|---|---|
| `alu_first`, `restart_idle` | 977 | 29, 29 | 29, 29 | No contention |
| `stream_first` | 982 | 25 | 25 | O wins from A (pointer rule); 977 131 against 132 |
| `out_one_bank` | 982 | 72 | 74 | A full writer lane wins again and again; the ALU fires in bursts |
| `len1` | 982, 977 | 1, 5 | 1, 5 | No contention |

`snax-alu` 982: 1, 25, 32, 256, 1024 at `DATA_LEN` 4, 100, 128, 1024, 4096,
plain and sparse; phases as plain.

## Result of round 1

13 ELFs on the sparse RTL, `snax_alu_sparse` and `snax_alu`: every
prediction held, `snax-alu` 0 errors on all four sides, its phases as SG5's
reference, so the RTL-against-model gaps stay SG5's (open items 65 to 67).
No new gap. The lock and granularity were exercised only by the winner check.

## Round 3: the cores and AXI

The two cores' TCDM ports and the narrow AXI port's into the crossbar on
both SNAX targets, as on the RTL; `snitch` unchanged.

### On the RTL

- A core: `reqrsp_iso` (a register each way), `reqrsp_to_tcdm`, priority 0;
  1, 2 or 4-byte accesses; a store needs only its grant, one integer load in
  flight; L1 load-to-load 4 cycles (SG5). AXI: `axi_to_tcdm`, priority 0.
- The sparse wrapper leaves the AMO shim's `core_id` and `is_core`
  undriven, so no LR/SC pair succeeds on the sparse RTL.

### The design

- Before, the cores reached the banks past the crossbar, a conflict costing
  a cycle of latency (open item 58).
- Inputs 12, 13 (`core0`, `core1`, keeping `core_latency['tcdm']`) and 14
  (`axi`), priority wires unbound; only with SNAX ports.
- Per-input `holds`: cores and AXI send once and a losing request is kept
  for the next cycle's arbitration; SNAX ports are dropped and resend.
- A read, AMO or LR/SC answered a cycle after its grant plus the request's
  latency, a write at its grant. Accesses up to 8 bytes in one bank word;
  one crossing a word is refused. LR reservations per hart.

### D125 fitted again

L1 load-to-load already 4 with `tcdm` 2 (step 3.4, `phases.py`, since
removed), which stays. The blocking L1 load cost C5 +5%, fixed in 3b.2.

### Predictions of round 3

`core-tcdm`, from source before any run:

| Case | Compare | Plain RTL | Plain target | Sparse RTL | Sparse target | Why |
|---|---|---|---|---|---|---|
| `subword` | errors, `sc` | 0, 0 | 0, 0 | 2, 1 | 0, 0 | `core_id` undriven on the sparse RTL |
| `core_vs_reader` | 977 | 18 | 18 | 17 | 17 | Plain: the core's load costs the readers a cycle; sparse: it waits behind priority-1 readers |
| `after_stores` | 977 | 5 | 5 | 6 | 6 | Plain: `rr_q` 12 from the stores, B first; sparse: A first |

### Result of round 3

16 ELFs on both RTLs and targets. `stream-timing`, `alu-timing`, `snax-alu`
equal per interconnect; the plain RTL's waveform shows B first in
`ab_same_banks`, as the plain target now. `after_stores` 5 and 6 as
predicted. `subword` as predicted (the RTL issue). `core_vs_reader` plain
target 17 against 18: GVSoC's I-cache miss (open item 65) made the core ask
10 cycles late (fixed in 3b.4).

### Acceptance of round 3

`make regress` passes with cores and AXI wired; L1 load-to-load 4; the
compared counters equal per interconnect; every prediction marked and gap
named.

## Round 3b: fix-ups of round 3

- 3b.1, `subword`: no change; one reservation per hart. Fixed in
  snax_cluster #658 (SG8).
- 3b.2: the core goes on after an L1 load answered later; the loaded
  register or the next load waits, through the Snitch scoreboard
  (`int_loads_in_flight`), not `NB_OUTSTANDING`; stores and AMOs block.
- 3b.3: GVSoC's `tohost` poll through the zero-time debug backdoor
  (`htif_poll_backdoor`); landing on a DMA copy it had moved `4x800`'s done
  from 82 to 96 and busy from 66 to 81 (RTL done 84).
- 3b.4, `core_vs_reader`: the start write and loads in one aligned function,
  run once, then measured: 18 on all four sides. Plain held; sparse 18
  against 17 predicted, since the first run leaves 2 words per lane, the
  readers ask with 0 and the pick is round robin; the sparse RTL agrees.
- 3b.5: every compared counter matches but `subword` on the sparse RTL;
  `snax-alu` C5 2% under the RTL; `dma-timing` as SG2's.

## Round 4: the DMA's superbank

### On the RTL

- Superbank: 512 / 64 = 8 banks, 4 superbanks, `(addr >> 6) & 3`. The wide
  AXI's TCDM slave sends one 64 B beat per cycle.
- `mem_wide_narrow_mux`: while the DMA's `q_valid`, it takes every bank of
  the superbank, granted at once, and every narrow `q_ready` there is 0.
- The refused winner: plain `rr_arb_tree` (`LockIn`) arbitrates the locked
  vector next cycle, `rr_q` moving only on a grant; sparse, `lock`. The
  master keeps its request.

### The design

- Before, the DMA's lines went past the crossbar, a conflict a cycle late.
- A `dma` port on the crossbar, not arbitrated; `superbank_banks` 8. A beat
  inside one aligned superbank line takes its banks for its cycle and is
  answered at once; one crossing a line is refused by name.
- `bank_refuses(b)`: a taken bank's winner is not granted and keeps its
  turn (`refused()`); a SNAX port resends, a core or AXI is held. Not
  modelled: `axi_to_mem`'s buffering, the DMA's AXI side (D121).

### Call order within a cycle

A cycle's arbitration is queued with delay 0 by its first narrow request
(or `held_event`), after every event queued before the cycle. DMA lines come
from events queued a cycle or more ahead, so a beat reaches the crossbar
before its cycle's arbitration and wins. A later beat on a superbank already
granted to a narrow request is fatal; no program hits it.

### Predictions of round 4

`dma-tcdm`'s `dma_vs_reader`, 977: 264 (first run 260) on all four sides.
Each of four beats on superbank 0 refuses A's lanes once; the ALU fires a
cycle later each time: +4. No second case: the lock between two lanes does
not show in a counter (checked by the winner checks).

### Result of round 4

18 ELFs: `dma_vs_reader` 264 (260), 0 errors, on all four sides; the plain
RTL's `sel_wide` refuses A's lanes in exactly the beat cycles. `dma-timing`
on both RTLs gives SG2's lines. Other programs unchanged. No gap in a
compared counter; the beat spacing differed (follow-up).

### Acceptance of round 4

The plain pick equals `rr_arb_tree` v1.40.0 in Verilator (a broken lock
fails); `dma-timing` as SG2's; no late beat or line-crossing request; the
compared counters equal per interconnect, every prediction marked.

## Round 4 follow-up: the DMA's beat cycles

Each beat split into (a) the DMA core's `dmcpyi` and (b) `dmcpyi` to the
beat in L1; both RTLs agree, both targets too.

### The split

`dma_vs_reader`, measured run, from A's first grant:

| Copy | (a) GVSoC | (a) RTL | (b) GVSoC before / after | (b) RTL | Beat GVSoC before / after | Beat RTL |
|---|---|---|---|---|---|---|
| 1 | +55 | +58 | 14 / 16 | 16 | +69 / +71 | +74 |
| 2 | +64 | +68 | 14 / 16 | 16 | +78 / +80 | +84 |
| 3 | +69 | +75 | 12 / 16 | 16 | +81 / +85 | +91 |
| 4 | +75 | +82 | 14 / 16 | 16 | +89 / +91 | +98 |

`dma-timing`, from `t0`:

| Copy | (a) GVSoC | (a) RTL | (b) GVSoC before / after | (b) RTL | Beat GVSoC before / after | Beat RTL |
|---|---|---|---|---|---|---|
| `1x64` | +12 | +12 | 14 / 16 | 16 | +26 / +28 | +28 |
| `4x800` 1 | +12 | +12 | 14 / 16 | 16 | +26 / +28 | +28 |
| `4x800` 2 | +21 | +22 | 18 / 20 | 19 | +39 / +41 | +41 |
| `4x800` 3 | +30 | +32 | 22 / 24 | 22 | +52 / +54 | +54 |
| `4x800` 4 | +39 | +42 | 26 / 28 | 25 | +65 / +67 | +67 |

In `4x800` copy k's first beat is the first copy's + 13 (k - 1) on both.

### Where in the DMA's path

`l2l1 1x64`, from its `dmcpyi` at c:

| Point | RTL | GVSoC before | GVSoC after |
|---|---|---|---|
| `busy` (`DMA_BUSY`, `dmstati 2`) | c + 1 to c + 14 | c to c + 13 | c to c + 13 |
| Read request to AXI | c + 2 | c + 3 | c + 3 |
| Read data at the DMA | c + 13 | c + 14 | c + 14 |
| Write leaves the DMA (the iDMA's W) | c + 14 | c + 14 | c + 14 |
| Write in L1 | c + 16 | c + 14 | c + 16 |
| Write response | c + 19 | none | none |

- DRAM read 11 cycles on both (D121's `hbm_latency` 6, `read_latency` 5);
  from the W on the two agree, and `busy` is fitted there (D121).
- A stage could run in the cycle its work arrived ((b) 12 for copy 3).
  Fixed: `one_cycle_per_stage`.
- On the RTL a beat reaches L1 2 cycles after the iDMA's W and `busy` falls
  at the W. Fixed: `tcdm_write_latency` 2, the line acknowledged when it
  leaves (`SNAX_DMA`, since moved to `DMA_TIMING` in `snax/snax_hjson.py`).

### After the fix

(b) equal per copy. The rest is (a), the core's issue timing: open item 67,
kept (D124); `dma_vs_reader`'s beats are 3, 4, 6, 7 cycles before the
RTL's, all of it (a). `dma-timing` checks the RTL's `busy`, `r` and `w` (4f.2).
Not verified: DMA reads from L1 (open item 73), an L1-to-L1 copy (72).

## Result

Every TCDM master goes through the crossbar as on the RTL: SNAX ports,
cores and AXI as inputs 0 to 14, the DMA as a wide input. On both RTLs and
both targets:

- Every compared counter equal per interconnect but `subword`'s SC on the
  sparse RTL (fixed in snax_cluster #658, SG8). Plain against sparse:
  `prio_queued`, `idle_restart` 5 and 6; `out_one_bank` 72 and 74;
  `after_stores` 5 and 6.
- `snax-alu` within SG5's target (C5 -2%, total -1%, -2%, -2% at 128, 1024,
  4096; D2 at 128 -20%, accepted in SG5).
- `dma-timing`'s `busy`, `r` and `w` equal the RTL's on every line.
- Two missed predictions, both `core_vs_reader` (3 and 3b, above).

Open in snax-forge: items 65 to 67 and 69 to 75 (AXI input unused, a store
after a pending load, L1 load after a DRAM load 13 cycles early, L1-to-L1
copies, DMA reading L1, the iDMA as sparse ports, granularity above 1).

## Decided

The model scope ("Model scope", round 4's "The design"); the priority wire
(step 6); one crossbar, each pick checked against its RTL module (steps 5,
4.2); the cores and AXI as holding inputs 12 to 14 (round 3); the core going
on past an L1 load, `tcdm` 2 (3b.2, 3.4); the `tohost` backdoor (3b.3);
`core_vs_reader` run twice (3b.4); the DMA's superbank (round 4);
`tcdm_write_latency` and `one_cycle_per_stage` (4f.1); `dma-timing` failing
when the DMA's own timing moves (4f.2).
