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
| 2 | RTL generation for `snax_alu_cluster.hjson`; the streamer header compared; a second module elaborated with granularity | |
| 3 | `sw/`: the sparse hjson copied, its headers checked against the old one's | |
| 4 | The crossbar's sparse pick (`interconnect`, `sparse_config`) in a shared header | |
| 5 | The winner check against both RTL modules | |
| 6 | The streamer's priority bit | |
| 7 | The `snax_alu_sparse` target; regress, CI, README | |
| 8 | Predictions, and new `stream-timing` cases | |
| 9 | Runs on the RTL and both targets; the comparison | |

## Predictions

Filled in step 8, before any sparse RTL run.

## Decided

- Round 1 puts only the SNAX ports through the sparse crossbar; the
  plain target stays as it is.
- The model describes what each port sees per cycle; the table above is
  its scope.
