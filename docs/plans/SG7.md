# SG7 plan: the sparse interconnect

SG7 is a task of M16 in snax-forge, after CI1: snax_cluster's sparse
interconnect in SNAX-GVSoC, amending D119 (plain interconnect) and D122
(the SNAX crossbar copies the plain interconnect). It runs in five rounds;
this file covers all five and details round 1, the sparse interconnect on
the SNAX ports. Acceptance below.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- On the MICAS server, by Claude Code. GVSoC, `sw/`, sync and
  `make regress` in snax-forge's image (`ghcr.io/kuleuven-micas/snax-forge:main`);
  snax_cluster's `rtl-gen`, `vsim_preparation` and the Chisel elaboration
  in the snax image `d3d8f5572ff4`; `bin/snitch_cluster.vsim` built and run
  on the host, where Questa is. Each container mounts the folder that
  holds the repos, at the same path.
- One commit per step on `ry/sg7-sparse`, never pushed, no pull request;
  snax-forge is read only in round 1.
- snax_cluster at the pin of `sw/README.md` (`9fbf35d`), in
  `../snax_cluster` for the sparse build and `../snax_cluster_plain` for
  the plain one, so neither build cleans the other.
- Anything not verified is said so.

## The sparse interconnect on the RTL

From source at snax_cluster `9fbf35d`:
`hw/chisel/.../snax/sparse_interconnect/`, `hw/templates/sparse_interconnect_wrapper.sv.tpl`,
`util/snaxgen/snaxgen.py`, `hw/snitch_cluster/src/snitch_cluster.sv`,
`readerWriter/` and `utils/ComplexQueue.scala`.

- Configuration. `cfg/snax_alu_cluster.hjson` is `snax_alu_cluster_old.hjson`
  with `tcdm.sparse_interconnect: true`, the bender target
  `sparse_interconnect`, and the accelerator's `snax_narrow_tcdm_ports: 12`
  and `snax_wide_tcdm_ports: 0` replaced by
  `sparse_interconnect_config: [[12, 1]]`. snaxgen builds the module's
  `sparse_config`, a list of ports `[width, granularity]`: per core, each
  accelerator's `sparse_interconnect_config` (or `[snax_tcdm_ports, 1]`
  without one) and `[16, 1]` for an xDMA; then `[1, 1]` per core (no SSR
  assumed); then `[1, 1]` for the AXI port. Here `[[12, 1], [1, 1], [1, 1],
  [1, 1]]`: 15 inputs, `NumOut` the 32 banks, `memAddrWidth` 9
  (log2 of 512 words per bank), `tcdmAddrWidth` 17, 64-bit data,
  `priorityWidth` 1. `snitch_cluster.sv` packs the inputs
  `{axi_soc_req, tcdm_req, snax_tcdm_req_i}`, so the SNAX ports are 0 to
  11, the cores 12 and 13, AXI 14, as the list says.
- Bank and reach. The bank is `addr[7:3]`, `(addr >> 3) & 31`. Input `k`,
  index `j` within a port of granularity `g`, may reach only banks
  `b` with `b % g == j % g` (an assertion on the RTL). Bank `b` sees
  `width / g` inputs of each port, in its local order
  `SparseConfig.get_global_idx_list(b)`: ports in order, and within a port
  `first + i * g + b % g` for `i` from 0. With every `g` 1 that is the
  global order.
- Pick, per bank and cycle (`ArbitrationTree`, `PriorityRoundRobinArbiter`,
  `RoundRobinArbiter`): among the valid requests, keep those whose priority
  equals the highest valid priority (the mask). The register `previous`
  holds last cycle's selection, `NumInp - 1` at reset. If `lock` is set and
  `previous` is in the mask, it wins; else the lowest masked input above
  `previous`; else the lowest masked input. `previous` takes the selection
  every cycle: with no request the selection is `PriorityEncoder(0)`, the
  last input, so after a cycle in which the bank had no request the pointer
  is `inputs - 1` and the next pick is the lowest masked input. `lock` is
  `valid && !ready` of last cycle: the winner was refused by the bank.
- Grant and data. The winner's request goes to the bank and its `ready` is
  the bank's `q_ready`; read data comes back one cycle after the grant,
  routed by the registered bank select (the module assumes 1-cycle banks;
  `register_tcdm_cuts` is false).
- Priority bit per master, in the request's user field (`tcdm_priority`):
  - SNAX streamer channels: `DataRequestor`. With `dynamicPriority` (the
    default) the hint is the lane's data queue (`ComplexQueueConcat`) count,
    reader `count <= 1` (`priority_empty`), writer `count >= depth - 1`;
    a register holds it, reloaded only in a cycle with no request or when
    the request fires, so the bit is stable while a request waits. Without
    it, `higherStaticPriority` sets a constant bit. Set per reader and
    writer by `stream_param_gen.scala.tpl`'s `dynamicPriority` and
    `higherStaticPriority` lists (defaults true and false).
  - Cores and AXI: `reqrsp_to_tcdm` sets the user field to 0 (the cores'
    `core_id` and `is_core` are added after it): priority 0.
  - An xDMA's channels (none here): the same requestor logic in its
    wrapper.
- Against the plain interconnect (`snitch_tcdm_interconnect.sv`,
  common_cells `stream_xbar` and `rr_arb_tree`, D122): the plain one has no
  priority (the bit is dropped), every input reaches every bank, and its
  per-bank tree keeps a state `rr_q` that moves to the next requester above
  it after a grant and is never reset on idle cycles. The sparse one masks
  by priority, limits reach by granularity, keeps the last pick as its
  pointer and resets it after an idle cycle.
- The iDMA stays under both, on the superbank mux (`mem_wide_narrow_mux`
  per 8 banks): in a cycle the DMA requests a superbank it takes it and the
  narrow side's `q_ready` is 0, so a sparse winner on those banks is refused
  and locked.

## Model scope

The model says what each port sees per cycle, not RTL signals or module
structure.

| Kept | Left out |
|---|---|
| Per bank and cycle one winner: highest priority first, then round robin from the last pick, the pointer reset after an idle bank cycle | valid / ready as signals; registers and encoders as such |
| A winner refused by its bank keeps its turn (the lock) | The `ArbitrationTree` / `PriorityRoundRobinArbiter` nesting |
| A channel reaches only the banks its granularity allows | The user-field packing; payload-stability rules |
| Read data one cycle after the grant | The AMO shim; the wide-narrow mux internals; register cuts |
| A request's priority taken by the RTL's hold rule and kept while it waits | |

In round 1 only the 12 SNAX ports go through the crossbar; the cores, AXI
and the DMA keep their paths (rounds 3 and 4).

## The priority bit

From `DataRequestor.scala`, `ComplexQueue.scala`, `Reader.scala` and
`Writer.scala` (step 6):

- The hint is combinational on the lane's data queue (`dataBuffer`, the
  `Queue` per lane, `fifo_depth` deep): reader `count <= 1`, writer
  `count >= fifo_depth - 1`. `count` comes from the queue's registers, so in
  cycle c it is the count after cycle c - 1's enqueue and dequeue. A
  reader's word enters at the response, one cycle after the grant, and
  counts from the cycle after that; a writer's beat counts from the cycle
  after the accelerator gives it, and leaves at its grant.
- `priorityHold` is reloaded at the end of every cycle in which the
  channel has no request or its request fires. So a request first sent in
  cycle t carries the hint of cycle t - 1 (the channel had no request then,
  or its previous one fired), and a request resent keeps the bit it was
  first sent with.
- With `dynamicPriority` false the bit is `higherStaticPriority`. The
  streamer template's keys are lists per reader or writer, defaults true and
  false.
- In SNAX-GVSoC the bit is the count during t - 1 of the words visible by
  then and not popped before it (`priority_hint()` in `snax_streamer.cpp`),
  taken when the channel makes a new request and kept while it is resent.
- Carried on a `wire<bool>` per SNAX port (`tcdm_prio_<i>` on the streamer,
  `prio_<i>` on the crossbar), set just before every send and resend of the
  request and holding for that cycle only. Not in the request's argument
  slots, which routers push and pop: a port that never sets its wire, as a
  core's reaching the crossbar through routers in round 3, asks with
  priority 0, as the RTL's cores and AXI do.

## The rounds

| Round | Content |
|---|---|
| 1 | The sparse interconnect on the SNAX ports: the crossbar's sparse pick, checked against the elaborated RTL module; the streamer's priority bit; the `snax_alu_sparse` target; predictions, then runs on the sparse RTL and both targets |
| 2 | The gaps round 1 names, in the crossbar or the streamer |
| 3 | The cores and AXI into the crossbar (priority 0, after the SNAX ports as snaxgen orders them); D125's core latencies fitted again, since part of what they hold is the interconnect |
| 4 | The DMA's superbank as a wide input that refuses the narrow requests on its banks in a cycle it is active: the lock's first user (open item 58 in snax-forge) |
| 5 | Close: snax-forge's docs (D119, D122, STATUS), the README, this file |

## Acceptance

- Round 1: the pick header gives the RTL module's selection on every bank
  in every cycle of the winner check, for both elaborated modules and for
  12 inputs against the 15-input module; on the sparse RTL and the sparse
  target the compared counters of `stream-timing`, `alu-timing` and
  `snax-alu` (D123) are equal, every prediction is marked held or not, and
  every gap is named; `make regress` passes on both targets.
- SG7: the sparse target with cores, AXI and the DMA in the crossbar gives
  the sparse RTL's counters, and its phases are within SG5's target
  (`SG5.md`, "The target"), on the same programs.

## Tests

| Test | Where | Checks |
|---|---|---|
| Winner check (`tests/snax/sparse_arb/`) | Verilator in `d3d8f5572ff4` (no Icarus there), by hand | The pick header against `SparseInterconnect.sv`, per bank and cycle, under random valid, addresses, priorities and refusals |
| `stream-timing`, `alu-timing`, `snax-alu` at five sizes | Sparse RTL and both targets | The compared counters, the phases of `snax-alu` |
| New `stream-timing` cases | Plain and sparse RTL, both targets | A winner that priority or the idle reset changes |
| Regression | Both targets | Every SNAX program exits 0 on `snax_alu` and `snax_alu_sparse`, the plain tests on `snitch` |
| `core-tcdm` (round 3) | Plain and sparse RTL, both targets | The cores' sub-word accesses, AMO and LR/SC through the interconnect; a core's load against reader lanes; the plain pointer the cores' stores leave |

## Steps

| # | Step | Status |
|---|---|---|
| 1 | This plan | done 2026-10-15 |
| 2 | RTL generation for `snax_alu_cluster.hjson`; the streamer header compared; a second module elaborated with granularity | done 2026-10-15 |
| 3 | `sw/`: the sparse hjson copied, its headers checked against the old one's | done 2026-10-15 |
| 4 | The crossbar's sparse pick (`interconnect`, `sparse_config`) in a shared header | done 2026-10-15 |
| 5 | The winner check against both RTL modules | done 2026-10-15 |
| 6 | The streamer's priority bit | done 2026-10-15 |
| 7 | The `snax_alu_sparse` target; regress, CI, README | done 2026-10-15 |
| 8 | Predictions, and new `stream-timing` cases | done 2026-10-15 |
| 9 | Runs on the RTL and both targets; the comparison | done 2026-10-15 |
| 3.1 | Round 3: this section ("Round 3") | done 2026-10-15 |
| 3.2 | The crossbar: inputs that hold, sub-word accesses; nothing wired | done 2026-10-15 |
| 3.3 | The cores and AXI into the crossbar on both SNAX targets | done 2026-10-15 |
| 3.4 | D125's `tcdm` latency fitted again | done 2026-10-15 |
| 3.5 | `core-tcdm` and its predictions | done 2026-10-15 |
| 3.6 | Runs on both RTLs and both targets; the comparison | done 2026-10-15 |
| 3b.1 | Round 3b: this section ("Round 3b"); `subword` on the sparse RTL noted | done 2026-10-16 |
| 3b.2 | The core goes on after an L1 load answered later | done 2026-10-16 |
| 3b.3 | GVSoC's `tohost` poll | done 2026-10-16 |
| 3b.4 | `core_vs_reader`'s layout | done 2026-10-16 |
| 3b.5 | Runs on both targets against round 3's RTL numbers | done 2026-10-16 |
| 4.1 | Round 4: this section ("Round 4") | done 2026-10-16 |
| 4.2 | The plain path's lock; its check against `rr_arb_tree` | done 2026-10-16 |
| 4.3 | The DMA's wide input on both SNAX targets | done 2026-10-16 |
| 4.4 | `dma-tcdm` and its predictions | done 2026-10-16 |
| 4.5 | Runs on both RTLs and both targets; the comparison | done 2026-10-16 |
| 4f.1 | Round 4 follow-up: where the DMA's beat cycles come from; the TCDM write path and the stages fixed | done 2026-10-16 |
| 4f.2 | `dma-timing` checks `busy`, `r` and `w` against the RTL | done 2026-10-16 |

## Predictions

Made in step 8, from source and before any sparse RTL run. The rules are
those above. Each case's requests and their timing come from the source of
the streamer, the ALU and the program; where a case has contention, the
cycles were worked through with a throwaway Python restatement of these
rules (`build/sg7/predict.py`, not committed), which first gave every grant
of the plain target exactly (cycle, bank and winner: `alu-timing`'s 1212,
every `stream-timing` case, `snax-alu` at the five sizes) before it was run
with the sparse rule. The same values hold for the sparse RTL and the
sparse target: the compared counters do not move when either start moves by
up to 3 cycles, and on the RTL the cores' stores before a run are followed
by idle cycles, so the pointer has restarted there as in the model, which
has no cores in the crossbar. s is the streamer's start write; f the ALU's
first firing. Plain RTL values are SG3's, SG4's and SG6's.

`stream-timing`, counter 977:

| Case | Plain RTL | Sparse | Grants against plain, and why |
|---|---|---|---|
| `zero_bound` | 0 | 0 | No request |
| `a_alone` | 9 | 9 | No contention |
| `ab_other_banks` | 9 | 9 | No contention |
| `ab_same_banks` | 10 | 10 | Banks 0 to 3 at s + 2, both readers asking with 1 (counts 0): the pointer has restarted (idle), so A, the lowest input, wins, as on the plain target; B follows a cycle later. On the plain RTL B wins there, the tree's pick for `rr_q` 12 left by the core's stores (the cores are in the RTL's interconnect, not in the model's), which the counter cannot show |
| `a_stride0` | 12 | 12 | Bank 0 at s + 2 to s + 4: lanes 0, 1, 2 in turn, the next input above the last pick, as plain |
| `prio_queued` (new) | 5 (first run 5) | 6 (first run 5) | Priority: at s + 2 on banks 0 to 3, B asks with 1 (count 0) and A with 0 (4 beats left by the first run), so B wins; plain gives A (`rr_q` 0 to 3 from A's first run, on the RTL too). A, with 4 beats, then ends a cycle later |
| `idle_restart` (new) | 5 (first run 2) | 6 (first run 2) | Idle restart: at s + 2 on banks 0 to 3 both ask with 1 (counts 0 and 1); the sparse pointer restarted after the idle cycles, so A wins; plain keeps B's turn (`rr_q` 4 to 7 from B's first run). B, with 4 beats, then ends a cycle later |

`alu-timing`, the compared counter of each case (SG4):

| Case | Counter | Plain RTL | Sparse | Grants against plain, and why |
|---|---|---|---|---|
| `alu_first` | 977 | 29 | 29 | No contention: A, B and O four banks apart in every cycle |
| `stream_first` | 982 | 25 | 25 | Pointer rule. At f + 1, B and O on banks 8 to 11 (bits 0): B wins, as plain (pointer restarted, B the lower input). At f + 2, A and O there: the sparse pointer is B's lanes, O is next above, so O wins where plain gives A. O then runs one beat behind the ALU instead of two, A one behind; no further contention, the ALU never waits. 977 one lower than plain at the same start gap (not compared; 131 on the RTL if its gap is as before) |
| `out_one_bank` | 982 | 72 | 74 | Priority and hold. Every word of O on bank 0: a writer lane whose queue holds 7 or 8 sends each new request with 1 and wins again and again while the other lanes' held requests keep their 0; each lane is drained a few words at a time, so the ALU fires in bursts of three every 12 to 13 cycles instead of once every 4, and its second-to-last firing comes 2 cycles later. The readers' lane-0 requests on bank 0 wait longer (held with 0) but 8 beats are queued, so the ALU never waits on input. 977 as plain at the same gap: bank 0 serves the same words (210 on the RTL if its gap is as before) |
| `len1` | 982, 977 | 1, 5 | 1, 5 | No contention |
| `restart_idle` | 977 | 29 | 29 | No contention |

`snax-alu`, `Accelerator Cycles` (982) and the phases:

| `DATA_LEN` | Plain RTL | Sparse | Grants against plain, and why |
|---|---|---|---|
| 4 | 1 | 1 | No contention |
| 100 | 25 | 25 | As `stream_first`: O wins banks 8 to 11 from A at the second conflict (pointer rule); the streamer ends a cycle earlier (977 42 to 41 on SNAX-GVSoC; the app does not read it); the ALU fires in the same cycles |
| 128, 1024, 4096 | 32, 256, 1024 | 32, 256, 1024 | B on A's banks: at s + 2 A first on both; at s + 15 and s + 16 the sparse pointer restarts after idle cycles, so A goes first where plain gives B; the ALU fires in the same cycles |

Phases: equal to the plain RTL's on the sparse RTL and to the plain
target's on the sparse target, but C4 at 100, which may end one poll
earlier (the streamer ends a cycle earlier). The cores' loads meet no
other master in the banks in these programs, and a lone request is granted
in its cycle by both interconnects with its data a cycle later.

## Result of round 1

Step 9 (`docs/notes/NOTES.md`): the same 13 ELFs on the sparse RTL (Questa),
on `snax_alu_sparse` and on `snax_alu`, and the two new cases on the plain
RTL. Every prediction above held:

- `stream-timing`: every counter equal on the sparse RTL and the sparse
  target; `prio_queued` and `idle_restart` 6 there and 5 on the plain RTL
  and target, first runs 5 and 2 everywhere.
- `alu-timing`: every compared counter equal on the sparse RTL and the
  sparse target (29, 25, 74, 1 and 5, 29), `out_one_bank`'s 982 74 against
  the plain 72; `stream_first`'s 977 131 on both sparse sides against 132.
- `snax-alu`: 982 and 0 errors at the five sizes on all four sides; every
  phase of the sparse RTL equals SG5's plain RTL reference, every phase of
  the sparse target equals the plain target's. So the RTL-against-model
  gaps are SG5's, unchanged (open items 65 to 67 in snax-forge).
- No new gap. Not observed: individual grants on the RTL (no grant trace),
  so the plain RTL's different winner in `ab_same_banks` (cores in its
  interconnect) stays a prediction; the lock and the granularity warning
  are exercised only by the winner check, nothing refuses in GVSoC yet.

## Round 3: the cores and AXI

Round 1 named no new gap, so round 2 had nothing to fix. Round 3 puts the
two cores' TCDM ports and the narrow AXI port's into the crossbar, on both
SNAX targets, numbered as on the RTL. The DMA keeps its path (round 4); the
`snitch` target is not changed.

### On the RTL

From source at `9fbf35d`: `hw/snitch_cluster/src/snitch_cluster.sv`,
`snitch_cc.sv`, `hw/tcdm_interface/src/reqrsp_to_tcdm.sv` and
`axi_to_tcdm.sv`, `hw/snitch_cluster/src/snitch_amo_shim.sv`,
`hw/templates/sparse_interconnect_wrapper.sv.tpl`, `util/snaxgen/snaxgen.py`.

- Inputs. Both interconnects take `{axi_soc_req, tcdm_req, snax_tcdm_req_i}`:
  the SNAX ports 0 to 11, core 0's TCDM port 12, core 1's 13, AXI 14.
  snaxgen's `sparse_config` lists them in that order: the accelerators'
  ports, `[1, 1]` per core (no SSR assumed), `[1, 1]` for AXI. The plain one
  is the same `snitch_tcdm_interconnect` with 15 inputs, of which round 1
  modelled 12 (the same tree of 16 leaves).
- A core's path (`snitch_cc.sv`). The LSU's request goes through
  `reqrsp_iso` (a register on the request and one on the response:
  `register_core_req` and `register_core_rsp` are true), `reqrsp_demux`
  (the cluster's TCDM range, else `data_req_o` to the narrow AXI) and
  `reqrsp_to_tcdm` to its port. The cores are rv32ima with no SSR and no
  FPU: one TCDM port each, and accesses of 1, 2 or 4 bytes with byte
  strobes into the 64-bit bank word. `reqrsp_to_tcdm` sets the user field
  to 0 and `snitch_cluster.sv` adds `core_id` and `is_core`: priority 0.
- AXI's path. The narrow AXI crossbar's TCDM slave, `axi_to_tcdm`
  (`axi_to_reqrsp`, then `reqrsp_to_tcdm`, user 0): port 14, priority 0.
- What a core sees: its request waits at the interconnect until granted;
  read data comes one cycle after the grant; a store needs only its grant
  (up to 4 accesses in flight, `num_int_outstanding_mem`, and one integer
  load, `num_int_outstanding_loads`). From one load to the next, 4 cycles
  from L1 (SG5): the interconnect's cycle, the two registers and the write
  back.
- AMOs and LR/SC go through the AMO shim before each bank (left out of the
  model, as in round 1). The shim keeps an LR's reservation by `core_id`
  and lets an SC succeed only when its `core_id` equals the reservation's.
  The sparse wrapper leaves the memory side's user field unconnected
  ("user signal not used"), so on the sparse RTL the shim's `core_id` and
  `is_core` are not driven.

### In SNAX-GVSoC before round 3

- Core i's data port goes to its router `pe<i>_ico`, whose TCDM map (and
  `tcdm_alias` map) leads to `tcdm.in_<i>`, the `L1_interleaver` and the
  bank, with `core_latency['tcdm']` (2) added on the map; the rest goes to
  `narrow_axi` with `core_latency['narrow']` (6).
- The bank answers at once. When two accesses meet in a bank in one cycle,
  the later one gets a cycle of latency (`next_packet_start`) instead of a
  round-robin wait (open item 58 in snax-forge), and the cores' accesses
  never move the crossbar's pointers.
- `narrow_axi`'s TCDM map goes into `pe0_ico`: an AXI access to the TCDM
  takes core 0's router and its latency.
- The core's LSU (`lsu.cpp`, io v1, one request at a time): on
  `IO_REQ_OK` the core goes on, a load's register is scoreboarded with the
  request's latency, and one integer load is in flight by `load_wait`
  (D125); on `IO_REQ_PENDING` the core stalls until the response. Routers
  forward a request (`req_forward` keeps the core's response port), so a
  grant and a response from the crossbar reach the core's LSU directly;
  `Lsu::data_grant` does something only with
  `CONFIG_GVSOC_ISS_LSU_NB_OUTSTANDING`, which the Snitch core does not set
  (`nb_outstanding` 1): a grant is a no-op for it, as `io.hpp`'s default
  grant callback is for a master that sets none.

### The design

- Inputs 12 + i, after the SNAX ports in core order: core i's TCDM and
  `tcdm_alias` maps in `pe<i>_ico`, which keep `core_latency['tcdm']`.
  Input 14: `narrow_axi`'s TCDM map, straight to the crossbar at TCDM
  offsets. Named `core0`, `core1`, `axi` in the trace; their priority wires
  stay unbound (priority 0). Only when the cluster has SNAX ports.
- A per-input property `holds`. An input that holds (cores, AXI) sends a
  request once and waits; the crossbar keeps a request that loses and puts
  it in the next cycle's arbitration, with its priority bit. An input that
  does not hold (the SNAX ports) is dropped when it loses and sends again,
  as in round 1. While a request is held, an event at the start of the next
  cycle queues that cycle's arbitration behind the events already queued, so
  the arbitration still comes after every master's request of the cycle.
- What a holding input gets back: a read, an AMO or an LR/SC is answered one
  cycle after its grant, plus the latency the request carries (the core's
  `tcdm` cycles) and any the bank adds; a write is answered at its grant,
  as the RTL core waits only for a store's grant. The core waits on
  `IO_REQ_PENDING` until then, so its loads block, and one integer load is
  in flight by construction. A request answered after its grant carries no
  latency in the response: the cycle of the response holds it all.
- Accesses of 1, 2, 4 or 8 bytes inside one bank word, at the bank-local
  address with the byte offset; one that crosses a word is refused with a
  warning naming the input. AMOs and LR/SC go to the bank as on the L1
  path (the bank keeps an LR's reservation by the request's initiator, the
  hart).
- Plain: 15 inputs. Sparse: the `sparse_config` gets `[1, 1]` per core and
  `[1, 1]` for AXI after the accelerators' ports, as snaxgen builds it.
- `grant()` is sent at the grant as before.

### D125 fitted again

Before round 3, `core_latency['tcdm']` 2 gives 4 cycles from one L1 load to
the next: the answer's latency 2, a cycle for the write back, and the next
load one cycle later (SG5 P5). The crossbar now adds its cycle (data one
cycle after the grant) and the core waits for the response. Step 3.4
measures the L1 load-to-load cycles in `snax-alu`'s check loop as SG5 P5 did
(`phases.py --show 'C5 check loop'`), on both targets with `tcdm` still 2,
then sets `tcdm` so it is 4 again (expected 1). `narrow` is unchanged. Then
`snax-alu` at the five sizes: phases against round 1's step 9 and SG5's plain
RTL reference, within SG5's target, each change named.

Result (3.4, notes): 4 already with `tcdm` 2, which stays. The crossbar's
cycle takes the place of the cycle the LSU added to a synchronous answer;
the core goes on in the cycle after the response. What changes is that a
core's L1 load now blocks the core until its data (3 cycles more per element
in the check loop, C5 +5% against the RTL); tiers 1 and 2 still hold.

### Predictions of round 3

Made in step 3.5 from source, before any run of `core-tcdm` on the RTL or on
SNAX-GVSoC. The cases with contention were worked through with a throwaway
restatement (`build/sg7/r3/predict3.py`, not committed): round 1's predictor
plus a core as input 12, asking with priority 0, its losing request held,
its next L1 load 4 cycles after the previous one's grant (D125). Without the
core it gives round 1's counters with 15 inputs as with 12.

`core-tcdm`:

| Case | Compare | Plain RTL | Plain target | Sparse RTL | Sparse target | Why |
|---|---|---|---|---|---|---|
| `subword` | errors, `sc` | 0, 0 | 0, 0 | 2, 1 | 0, 0 | Each access stays in one bank word, at the byte offset, and reaches the bank as on the L1 path. On the sparse RTL the AMO shim's `core_id` and `is_core` are not driven (the wrapper leaves the memory side's user field unconnected), so the SC's test of the reservation's core against its own is unknown and the SC fails: `sc` 1, the word stays 7, the LR/SC group counts 2 errors and the program returns 2. `amoadd.w` does not use `core_id`. On the plain RTL the user field passes through (core 0, a core); on SNAX-GVSoC the bank keeps the reservation by hart |
| `core_vs_reader` | 977 | 18 | 18 | 17 | 17 | 16 reader requests on bank 0, all asking with priority 1 (queue counts 0 and 1). Plain: the core's bank-0 load gets its turn after the 8 lanes' first requests, at s + 11 for any arrival from s + 4 to s + 10, and costs the readers a cycle. Sparse: the core, with 0, waits until the readers are done (s + 18). Both hold for the core's first load (bank 16) issued 0 to 6 cycles after the start write |
| `after_stores` | 977 | 5 | 5 | 6 | 6 | Plain: core 0's stores leave `rr_q` at 12 on banks 0 to 3 (13 would give the same), from which the tree takes B first; A then waits a cycle, B ends at s + 5. Sparse: the pointer restarts after the idle cycles, A goes first, B ends a cycle later. The plain target before round 3 (`rr_q` 0 from reset) would give 6. So the plain RTL's 5 shows its pointer at the core's input, round 1's open prediction for `ab_same_banks` |

The other programs, with the cores in the crossbar on both targets:

- Every compared counter of `stream-timing`, `alu-timing` and `snax-alu` as
  in round 1 on each side, and the plain RTL's at the pin as SG3's, SG4's
  and round 1's values. In these programs the cores' accesses meet no
  streamer request (the core reads only CSRs while the streamer and the ALU
  run), and the counters do not move with the plain pointer the cores leave
  (the predictor with `rr_q` 0, 12 or 13 at the start). The plain target's
  grants now follow the cores' stores: in `ab_same_banks` B goes first on
  banks 0 to 3 at s + 2, as on the plain RTL (round 1's prediction), the
  counter still 10.
- `snax-alu`'s phases on both RTLs: SG5's reference (the same ELFs, the RTL
  unchanged); on the targets, step 3.4's.
- What is not compared may move on SNAX-GVSoC with the core's timing: start
  gaps, `polls`, `mcycle`, 977 where it is not compared.

### Result of round 3

Step 3.6 (`docs/notes/NOTES.md`): the same 16 ELFs on the plain RTL, the
sparse RTL and both targets.

- `stream-timing`, `alu-timing`, `snax-alu`: every compared counter equal on
  the plain RTL and the plain target, and on the sparse RTL and the sparse
  target; every prediction held. The plain RTL's runs at the pin give SG3's
  and SG4's values. The plain RTL's grants, read from its waveform, settle
  round 1's open prediction: in `ab_same_banks` B goes first, from the
  pointer core 0's stores leave, and so does the plain target now.
- `snax-alu`'s phases: on both RTLs as SG5's reference; on the targets
  step 3.4's, within SG5's target.
- `core-tcdm`: `after_stores` 5 plain, 6 sparse on both sides, as
  predicted. `subword` 0 errors but on the sparse RTL, whose SC fails as
  predicted: the sparse wrapper leaves the AMO shim's `core_id` undriven (an
  RTL issue). `core_vs_reader` 18 on the plain RTL, 17 on the plain target
  (predicted 18): GVSoC's I-cache misses the line holding the start write
  and the core's loads (open item 65), so the core asks 10 cycles later than
  on the RTL, beyond what the case tolerates; 17 on both sparse sides.
- So round 3's acceptance holds for `stream-timing`, `alu-timing` and
  `snax-alu`, and not for two `core-tcdm` counters: one gap in the RTL, one
  in the case's layout against the core's fetch timing.

### Acceptance of round 3

- 3.2: nothing wired; `make regress` passes; the SNAX programs' `run.log`
  files and crossbar traces equal round 1's on both targets.
- 3.3: `make regress` passes with the cores and AXI wired.
- 3.4: L1 load-to-load 4 on both targets; `snax-alu` within SG5's target.
- 3.6: the compared counters of `stream-timing`, `alu-timing`, `snax-alu`
  and `core-tcdm` equal on the plain RTL and the plain target, and on the
  sparse RTL and the sparse target; every prediction marked held or not;
  every gap named with its likely cause.

## Round 3b: fix-ups of round 3

Before round 4, the three things round 3 left that SNAX-GVSoC or a program
can fix, and one that only snax_cluster can. Results in the notes.

- `subword` on the sparse RTL (no change). Its SC fails there because
  snax_cluster's sparse wrapper leaves the memory side's user field
  undriven, so the AMO shim sees `core_id` X and `is_core` 0 and no LR/SC
  pair can succeed. SNAX-GVSoC keeps the plain RTL's behaviour, a
  reservation per hart, which is the correct one; snax_cluster is fixed
  after SG7. The case stays as it is: 0 errors on three sides, 2 on the
  sparse RTL until then.
- 3b.2, the core's L1 loads. Round 3 made the core stall on every L1 load
  until its data (`IO_REQ_PENDING`), so C5 went from 44 to 47 cycles per
  element (RTL 45). The RTL core goes on after issuing a load; an
  instruction that reads or writes the loaded register waits for its data,
  and with `num_int_outstanding_loads` 1 the next load waits for the
  previous load's data (D125). The Snitch core does that now for a load
  answered later, as it does for one answered at once with latency, behind
  `int_loads_in_flight` (the `snitch` target unchanged). Stores, AMOs and
  LR/SC keep their behaviour. Done with the Snitch core's own scoreboard
  (`scoreboard_reg_valid`, checked before every integer instruction, which
  the FP subsystem's results already use), not the `NB_OUTSTANDING` path,
  which would make stores and AMOs non-blocking too.
- 3b.3, GVSoC's `tohost` poll. GVSoC's host model reads `tohost` from DRAM
  through the core's data port and `narrow_axi` every 1000 cycles; landing
  on a DMA copy it delays the copy's DRAM read (`dma-timing`'s 4x800 B from
  done 82, busy 66 to 96, 81; RTL 84 for done). The RTL has no such poll.
  Made a zero-time debug access, on the SNAX targets, if it can be without
  changing what programs see or the period. Done with GVSoC's debug
  backdoor (`vp/debug_mem.hpp`) behind the core's data port, for the cores
  and their FP subsystems (`htif_poll_backdoor`).
- 3b.4, `core_vs_reader` on the plain target (17 against the plain RTL's
  18). GVSoC's I-cache misses the line holding the start write and the
  core's loads (open item 65), so the core asks 10 cycles later than on the
  RTL. First the traces are checked for the arbitration rule on both sides;
  then one layout change that fetches that line before the measured run. If
  the four sides do not then agree, the case's counter is marked as
  depending on the core's fetch timing (shown, not compared, D123). No
  model change.

  The change: the start write and the two loads in one non-inlined
  function, the block aligned to a 32 B line, called for a first run and
  then for the measured one, the loaded words returned in registers.
  Prediction, from round 3's predictor with the arbiters' state carried
  from the first run, before any run: the measured counter 18 on the plain
  RTL and target, 17 on both sparse sides, for the core's first load 0 to 6
  cycles after the start write with the bank-0 pointer the first run leaves
  (7 on the RTL, 12 on GVSoC, where the core asks later); expected on
  GVSoC 1 to 3 cycles after the start write (the line in the I-cache), as
  the RTL's 1. First run: 18, 17, 17, 17 (on GVSoC the line still misses).

  Result: the measured counter 18 on all four sides, first run 18, 17, 17,
  17; the core's loads at s + 1 and s + 5 on the plain RTL and the plain
  target, granted at s + 1 and s + 11 on both. So the layout stays. Plain:
  held. Sparse: not held, 18 on both sides against 17 predicted. The
  predictor started the measured run with empty reader queues; the streamer
  keeps the first run's 2 words per lane (ALU off), so the readers ask with
  0, as the core, and the sparse pick is round robin as plain. The sparse
  RTL agrees with the model. What the compared counter no longer shows: the
  core waiting behind priority-1 readers on the sparse interconnect; only
  the first run, not compared, does.
- 3b.5, the programs again on SNAX-GVSoC, against round 3's RTL numbers.
  Result: every compared counter matches on each interconnect but
  `subword` on the sparse RTL (above), `core_vs_reader` now included;
  `snax-alu` within SG5's target, C5 2% under the RTL; `dma-timing` as
  SG2's.

## Round 4: the DMA's superbank

The DMA's TCDM accesses go through the SNAX crossbar as one wide input, on
both SNAX targets; `snitch` is not changed. The DMA's own timing (D121) does
not change.

### On the RTL

From source at `9fbf35d`: `hw/snitch_cluster/src/snitch_cluster.sv`,
`hw/mem_interface/src/mem_wide_narrow_mux.sv`,
`hw/snitch_cluster/src/snitch_tcdm_interconnect.sv`, common_cells v1.40.0
(`1281545`) `rr_arb_tree.sv` and `stream_xbar.sv`, and the Chisel
`RoundRobinArbiter` (round 1).

- Superbanks. `BanksPerSuperBank = WideDataWidth / NarrowDataWidth`, the
  hjson's `dma_data_width / data_width`, 512 / 64 = 8; `NrSuperBanks =
  NrBanks / BanksPerSuperBank`, 4. Superbank `i` holds banks `8i` to
  `8i + 7`, so an address's superbank is `(addr >> 6) & 3`.
- The DMA's path. The wide AXI crossbar's TCDM slave goes to
  `i_axi_to_mem_dma` (`axi_to_mem_interleaved`, `NumBanks` 1, 512 bit): one
  64 B request per cycle, a read or a write, a partial beat with its
  strobes. Then `i_dma_interconnect`, a `snitch_tcdm_interconnect` with one
  input and one output per superbank (a pass-through tree), which drops the
  address's low 6 bits. Every wide AXI access into the TCDM takes it: the
  iDMA's and any other wide master's.
- The mux, one per superbank, `sel_wide_i = sb_dma_req[i].q_valid`. While
  set, every bank of the superbank gets the DMA's request (its 64-bit
  slice and strobes, no AMO), the DMA's `q_ready` is 1 (asserted:
  `ImmediateGrantWide`), and every narrow `q_ready` of the superbank is 0
  (`SilentNarrow`). A beat with partial strobes takes all 8 banks too.
  Otherwise the narrow requests pass.
- The refused narrow winner, plain. The bank output is `stream_xbar`'s
  `rr_arb_tree`, `LockIn` 1, `FairArb` 1, `AxiVldRdy` 1, no spill register:
  its `gnt_i` is the bank's `q_ready`. With `req_o && !gnt_i` it sets
  `lock_q`, and in the next cycle it arbitrates `req_q`, the request vector
  it arbitrated, instead of `req_i`: the same decision while it stays
  refused. `rr_q` moves only with `gnt_i && req_o`, to the first requester
  above it in the vector arbitrated. A request that comes while it is
  locked is not seen until the locked one is granted; one that was seen may
  not be dropped (`lock_req`), and the masters hold their requests until
  `q_ready`.
- The refused narrow winner, sparse: the `lock` register is `valid &&
  !ready` of the last cycle, and the last pick wins again if it is in the
  mask (round 1's reading).
- The master sees `q_ready` 0: it keeps its request, and gets no response.

### In SNAX-GVSoC before round 4

- `SnitchDma`'s TCDM back-end (`IDmaBeTcdm`) sends lines of `tcdm_width`
  (64 B on the SNAX targets), cut at `tcdm_width` boundaries, and needs
  `IO_REQ_OK` (it is fatal on anything else), with a latency. It and `wide_axi`'s TCDM and `tcdm_alias`
  maps go to `tcdm.i_DMA_INPUT`.
- There, `DmaInterleaver` cuts a request into bank words, forwards each to
  its bank and answers `IO_REQ_OK` with the largest bank latency. A bank
  (`memory.Memory`, 8 B wide, latency 0) gives the second access of a cycle
  one cycle of latency. So a DMA line and a narrow grant on one bank in one
  cycle both go through, the later in call order a cycle late (open item 58
  in snax-forge); the crossbar never sees the DMA.

### The design

- A port `dma` on the crossbar, not one of its arbitrated inputs; on both
  SNAX targets `tcdm.i_DMA_INPUT` goes to it instead of `DmaInterleaver`.
- The superbank: property `superbank_banks`, the target's
  `dma_data_width / data_width` (8 in `snax_alu.py`), with the cluster
  checking that the DMA's `tcdm_width` is the superbank's bytes. A DMA
  request inside one aligned superbank line is a beat: it takes all banks
  of that superbank in its cycle and accesses only the bank words it covers
  (fewer bytes or an unaligned start: the RTL's beat with partial strobes).
  It is answered at once, `IO_REQ_OK` with the largest bank latency, as
  today: no latency added. Two in one cycle (an L1-to-L1 copy's read and
  write) take both superbanks.
- A request crossing a superbank line would be two beats in two cycles on
  the RTL (`axi_to_mem`). Nothing in SNAX-GVSoC sends one: the DMA cuts its
  lines at 64 B, and no other wide master reaches the TCDM. It is refused
  by name (a warning naming the address and size, `IO_REQ_INVALID`); step
  3 checks that no program hits it.
- `bank_refuses(b)`: the DMA took `b`'s superbank in this cycle. The winner
  of such a bank is not granted. Plain: `rr_q` does not move, and the bank
  is locked: in the next cycle it arbitrates the locked vector (this
  cycle's requests that still ask), which gives the same winner while that
  winner still requests, and `rr_q` then moves over that vector. Sparse:
  `refused()`, as since round 1. The input that lost then does as any
  loser: a SNAX port's request is dropped and sent again, a core's or AXI's
  held.
- Trace: `Superbank s: grant dma (read|write addr, size)` per DMA beat, and
  `Bank b: refused <input> (dma)` per refused narrow winner with the inputs
  held.

| Kept | Left out |
|---|---|
| A DMA beat takes its whole superbank in its cycle and is never refused | `axi_to_mem`'s buffering and the DMA's AXI side (D121's fit) |
| A narrow winner on a taken bank is refused and locked, by the bank's interconnect's rule | A request crossing a superbank line (refused) |

### Call order within a cycle

GVSoC runs a cycle's events in the order they were queued; one queued with
delay 0 goes after those already queued. The arbitration of a cycle is
queued with delay 0 by the cycle's first narrow request (or by
`held_event`), so it runs after every event that was queued for the cycle
before the cycle began. The DMA's TCDM lines come from its back-ends'
events, which it queues one or more cycles ahead (`enqueue()` defaults to
1; the only delay-0 one, a read line held for a destination not ready,
sends a TCDM line only in an L1-to-L1 copy), and from calls made inside
them. So a DMA beat of cycle c reaches the crossbar before c's arbitration,
whether its event runs before or after the narrow masters' requests of c.
The `dma` port records its superbank as taken in c when the beat comes, and
the arbitration of c refuses the narrow winners there: the DMA wins
whichever of the two calls first.

A DMA beat that comes after its cycle's arbitration, on a superbank where
a narrow request was granted in that cycle, cannot win: that grant is out.
The crossbar stops with an error naming the superbank, as it does for a
narrow request after the arbitration (round 3). On a superbank with no
grant in that cycle the late beat is taken as any other. Step 3 runs every
program with this check.

### Predictions of round 4

Made in step 4 from source, before any run of `dma-tcdm` on the RTL or on
SNAX-GVSoC.

`dma-tcdm` (`sw/apps/dma-tcdm/README.md`), counter 977, first run in
brackets:

| Case | Plain RTL | Plain target | Sparse RTL | Sparse target | Why |
|---|---|---|---|---|---|
| `dma_vs_reader` | 264 (260) | 264 (260) | 264 (260) | 264 (260) | The ALU first, A, B and O each alone on its banks: beats + 4 without contention, as `alu_first`'s 29 for 25. First run: the copies on superbank 3, which no mover uses: 260. Measured: each of the four beats on superbank 0 refuses A's four lanes in a cycle they ask; they ask again in the next and win (alone, locked or not), one beat late, and the ALU, taking one beat of A and B per cycle with no slack in A's queue, fires a cycle later each time: +4. B runs up to 4 beats ahead (its credit is 8). Plain and sparse alike: nobody competes with A |

The beats land some 65 to 90 cycles after the DMA core leaves the barrier
(a 50-cycle wait, the issue, the DRAM read), the movers ask from s + 2 to
s + 257; the counter holds while the two cores leave the barrier within
about 60 cycles of each other. The ALU's counter (982) moves with the gap
between the two start writes, as in `alu-timing`, and is not compared;
on each side it is predicted 4 above its first run's.

A second case was not added. A writer refused on its banks costs a cycle
in the same way (nothing new). The lock keeping a lane's turn against
another lane on the sparse interconnect changes which of the two goes
first after the refusal, not when the bank's last grant comes (one grant
per bank and cycle either way), so a counter would not show it; and placing
a DMA beat on a contested cycle needs the cores' timing to the cycle,
against D123. The lock is checked against the RTL by the two winner checks.

The other programs, with the DMA in the crossbar on both targets: no DMA
beat meets a narrow request (`dma-timing`: no core touches L1 during the
copies, round 3 step 3; `snax-alu`: both cores are at the barrier or in CSR
setup during its two copies, SG2; the others have no DMA copy), so every
`run.log` stays round 3b's and every compared counter round 3b's on each
side.

### Result of round 4

Step 5 (`docs/notes/NOTES.md`): the same 18 ELFs; `dma-tcdm` and
`dma-timing` on both RTLs, every program on both targets.

- `dma-tcdm`'s `dma_vs_reader`: 264 (first run 260) on the plain RTL, the
  plain target, the sparse RTL and the sparse target, errors 0: the
  prediction held. On the plain RTL's waveform the four DMA beats raise
  superbank 0's `sel_wide` and refuse A's four lanes in exactly those
  cycles, which are granted the next, as on both targets' traces.
- `dma-timing`: both RTLs at the pin give SG2's RTL lines; both targets
  round 3b's; `busy` equal on every line.
- The other programs: no DMA beat meets a narrow request on either target,
  every output and `snax-alu` phase as round 3b's; their RTL comparison
  stands. `make regress` passes.
- No gap in a compared counter. Not compared and different: the DMA's beat
  spacing into L1 and the ALU's counter (the start gap). The beats' cycles
  are split in the follow-up below.

### Acceptance of round 4

- 4.2: the plain pick equals `rr_arb_tree` v1.40.0 (`FairArb`, `LockIn`,
  `AxiVldRdy`) in every selection under random requests and `gnt_i`, in
  Verilator, for 15 inputs (the targets') and 12; a copy of the pick with
  a broken lock rule fails the check. `make regress` passes and every
  `run.log` equals round 3b's.
- 4.3: `dma-timing` on both targets equal on every line to round 3b's
  (SG2's); `make regress` passes; every other `run.log` equal to round
  3b's or each difference named; no DMA beat after its cycle's arbitration
  and no request crossing a superbank line in any program.
- 4.4: `dma-tcdm`'s predictions in this file before any RTL run.
- 4.5: `dma-tcdm`'s compared counters equal on the plain RTL and the plain
  target, and on the sparse RTL and the sparse target; `dma-timing` and
  the other programs as round 3b on the targets; every prediction marked
  held or not, every gap named.

## Round 4 follow-up: the DMA's beat cycles

`dma_vs_reader`'s four beats landed at +69, +78, +81, +89 from A's first
grant on GVSoC and +74, +84, +91, +98 on the plain RTL. Each beat's cycle is
split into (a) the cycle the DMA core issues that copy's `dmcpyi` and (b)
`dmcpyi` to the beat in L1, the DMA's own path; the same for `dma-timing`'s
`l2l1 1x64` and `4x800` (second runs, from `t0`, the `mcycle` before the
first start). The method and the files are in `docs/notes/NOTES.md`.

### The split

Both RTLs give the same DMA events cycle for cycle in both programs, and
both targets the same; the numbers hold for all four sides. GVSoC before
and after the fix below.

`dma_vs_reader`, measured run, from A's first grant:

| Copy | (a) GVSoC | (a) RTL | (b) GVSoC before / after | (b) RTL | Beat GVSoC before / after | Beat RTL |
|---|---|---|---|---|---|---|
| 1 | +55 | +58 | 14 / 16 | 16 | +69 / +71 | +74 |
| 2 | +64 | +68 | 14 / 16 | 16 | +78 / +80 | +84 |
| 3 | +69 | +75 | 12 / 16 | 16 | +81 / +85 | +91 |
| 4 | +75 | +82 | 14 / 16 | 16 | +89 / +91 | +98 |

First run (superbank 3): (a) +73, +100, +105, +120 on GVSoC against +75,
+90, +97, +107; (b) 14 on GVSoC before, 16 after and on the RTL, each copy.

`dma-timing`, from `t0`:

| Copy | (a) GVSoC | (a) RTL | (b) GVSoC before / after | (b) RTL | Beat GVSoC before / after | Beat RTL |
|---|---|---|---|---|---|---|
| `1x64` | +12 | +12 | 14 / 16 | 16 | +26 / +28 | +28 |
| `4x800` 1 | +12 | +12 | 14 / 16 | 16 | +26 / +28 | +28 |
| `4x800` 2 | +21 | +22 | 18 / 20 | 19 | +39 / +41 | +41 |
| `4x800` 3 | +30 | +32 | 22 / 24 | 22 | +52 / +54 | +54 |
| `4x800` 4 | +39 | +42 | 26 / 28 | 25 | +65 / +67 | +67 |

In `4x800` the copies after the first wait behind the 13 beats of the one
ahead: on both sides copy k's first beat is the first copy's + 13 (k - 1),
whenever it was issued, so their (b) differ by their (a).

### Where in the DMA's path

`l2l1 1x64`, from its `dmcpyi` at c (every copy above has the same steps):

| Point | RTL | GVSoC before | GVSoC after |
|---|---|---|---|
| `busy` (`DMA_BUSY`, `dmstati 2`) | c + 1 to c + 14 | c to c + 13 | c to c + 13 |
| Read request to AXI | c + 2 | c + 3 | c + 3 |
| Read data at the DMA | c + 13 | c + 14 | c + 14 |
| Write leaves the DMA (the iDMA's W) | c + 14 | c + 14 | c + 14 |
| Write in L1 | c + 16 | c + 14 | c + 16 |
| Write response | c + 19 | none | none |

- DRAM read: the read request to its data is 11 cycles on both, D121's
  `hbm_latency` 6 and `read_latency` 5. The parameters hold.
- Queue: the RTL sends the read request 2 cycles after `dmcpyi`, the model
  3 (midend, backend, AXI read, a cycle each), and its data comes a cycle
  after the RTL's R, in the cycle the RTL's iDMA sends the W. From there the
  two agree; `busy` is fitted on it (D121), so it stays.
- Queue, a model gap: a stage whose event was already queued for the cycle
  its work arrived in ran in that cycle. `dma_vs_reader`'s third measured
  copy, issued in the cycle the first one finished, went to AXI 1 cycle
  after its `dmcpyi`, not 3: (b) 12. Fixed: `one_cycle_per_stage`, each of
  the midend, the backend and the AXI read takes work from the cycle after
  it arrives.
- TCDM write, a model gap: on the RTL the beat crosses the wide crossbar's
  cut and `axi_to_mem_interleaved`, 2 cycles after the iDMA's W, and
  `busy_o` falls at the W: `dmstati` sees a copy done 2 cycles before its
  last beat is in L1. The model wrote L1 in the cycle the beat left the DMA.
  Fixed: `tcdm_write_latency` 2, the line acknowledged when it leaves, so
  `busy` and the DMA's done stay where they were.
- Bursts in flight: not involved.

Both are DMA properties set by the SNAX targets (`SNAX_DMA` in
`snax_alu.py`, as `read_latency`); `snitch` and the other targets keep the
model as it was. The beat reaches the crossbar from an event queued 2 cycles
ahead, so it still comes before its cycle's arbitration (round 4's call
order).

### After the fix

- (b) is equal per copy on both sides: 16 for every `dma_vs_reader` copy
  and for `1x64`; in `4x800` the beats are equal from `t0`.
- What is left is (a), the core's issue timing: a copy's `dmsrc`, `dmdst`,
  `dmcpyi` take 9 cycles on GVSoC against 10 on the RTL in `dma-timing`, 9,
  5, 6 against 10, 7, 7 between `dma_vs_reader`'s copies, more in the first
  run with a cold instruction cache. That is open item 67 in snax-forge
  (the core's own timing beyond its loads), kept (D124). `dma_vs_reader`'s
  beats are now 3, 4, 6, 7 cycles before the RTL's, all of it (a).
- `dma-timing` on both targets: every line equal to round 4's, so `busy`,
  `r` and `w` equal the RTL's on every line. `dma-tcdm`: 264 (260) on both
  targets. `make regress`: every `run.log` equal to round 4's.

`dma-timing` holds the RTL's `busy`, `r` and `w` per case (SG2 step 3,
the same at the pin in round 4) and returns the cases off them with its copy
errors, so `make regress` and CI fail when the DMA's own timing moves
(4f.2). `issue` and `done` are printed, not compared.

Not verified: the DMA's reads from L1 (`l1l2`): where the bank read falls
inside D121's 5-cycle read path on the RTL was not split, and the TCDM
back-end's own queue has no `one_cycle_per_stage`; no program has the DMA
read L1 against a narrow request. An L1-to-L1 copy's read and a delayed
write in the same cycle both go (the RTL's `axi_to_mem` takes one a
cycle); no program makes one.

## Decided

- Round 1 puts only the SNAX ports through the sparse crossbar; the
  plain target stays as it is.
- The model describes what each port sees per cycle; the table above is
  its scope.
- The priority bit travels on a wire per SNAX port, not in the request
  (step 6).
- The sparse target shares the plain one's ELFs: the two hjsons give the
  same headers, which sync checks (step 3).
