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
| 4 | The DMA's superbank as a wide input that refuses the narrow requests on its 8 banks in a cycle it is active: the lock's first user (open item 58 in snax-forge) |
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
| 3.5 | `core-tcdm` and its predictions | |
| 3.6 | Runs on both RTLs and both targets; the comparison | |

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

### Acceptance of round 3

- 3.2: nothing wired; `make regress` passes; the SNAX programs' `run.log`
  files and crossbar traces equal round 1's on both targets.
- 3.3: `make regress` passes with the cores and AXI wired.
- 3.4: L1 load-to-load 4 on both targets; `snax-alu` within SG5's target.
- 3.6: the compared counters of `stream-timing`, `alu-timing`, `snax-alu`
  and `core-tcdm` equal on the plain RTL and the plain target, and on the
  sparse RTL and the sparse target; every prediction marked held or not;
  every gap named with its likely cause.

## Decided

- Round 1 puts only the SNAX ports through the sparse crossbar; the
  plain target stays as it is.
- The model describes what each port sees per cycle; the table above is
  its scope.
- The priority bit travels on a wire per SNAX port, not in the request
  (step 6).
- The sparse target shares the plain one's ELFs: the two hjsons give the
  same headers, which sync checks (step 3).
