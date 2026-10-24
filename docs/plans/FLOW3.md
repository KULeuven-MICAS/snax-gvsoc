# FLOW3 plan: the flow ends in a SNAX-GVSoC run

FLOW3 is a task of M14 in snax-forge (D127, D136, D137 there): `pixi run
flow` generates a design point, builds its program and runs it here, on
`snax_hjson`, and the program checks itself. Round 1 is one PR in each repo;
RET1 (SNAX-MODEL removed from snax-forge) is its round 1c. Branches
`ry/flow3`, `-2`, `-4`, `-6`, `-7`; tags `flow3-r1a`, `-r1b`, `-r2a`,
`-r3a`, `-r3b` (the last three local).

## Acceptance

- 1a: `pixi run flow` on `recipes/vecadd.json` and `recipes/vsum.json` with
  `--platform platforms/snax_alu.json` (since removed; now
  `platforms/snax_forge.json`) ends in a checked SNAX-GVSoC run (exit 0).
- 1b: both pass at `--trace task`, the converter's invariants holding, and
  write `report/design.md` and `report/run.md`; at `off` the profile comes
  from the `summary` lines alone; `pixi run view` opens them.
- 2a: both pass at `off`, `task`, `beat`, `stall` and `finegrained`; each
  `forge cycles:` is its `off` run's and each `profile.json` above `task`
  the `task` run's, byte for byte; `--vcd` writes the VCD, each SNAX signal
  named, and `view.gtkw`; the trace sizes measured.
- 3a: `make regress` passes with the class check; vecadd and vsum pass at
  the defaults (windows 226 and 255) and at `N=512` with `W=4` and `W=8`, at
  every level; on the `N=512` runs the schedule's segments cover the window
  exactly, each fold a quiet stretch of at least 16 cycles, a lane per core,
  the DMA, each mover and the accelerator; stepping visits exactly the event
  and boundary cycles; the cluster answer at a cycle names only its lines.
- Each passed in the container, with `make regress` here and snax-forge's
  `pixi run test`; CI's `gvsoc` job runs the flows (vecadd also at `--trace
  stall`), its runs on `ry/flow3*` waiting for a dispatch.

## The rounds

| Round | Content |
|---|---|
| 1a | `gvsoc/Makefile` names the image's tools, so the flow calls make from pixi; `gvrun` on `GVRUN_PYTHON`; the window and `forge_check()` in place of the marks; the stages lower, gen, build, sw, gvsoc, check; CI's `gvsoc` job |
| 1b | An `events` `vp::Trace` per SNAX component (`docs/EVENTS.md`, D137); snax-forge's converter into its C§7; levels `task`, `beat`; the reports |
| 1c | RET1: SNAX-MODEL removed from snax-forge |
| 2a | `grant`, `dma`, `stall`, `burst`, `fire`, `push`, `fifo` linked by ids; the `stalls` trace; levels `beat`, `stall`, `finegrained`; the source filter; VCD signals |
| 2b | snax-forge's memory (D96) and movement (D97) views on 2a's events |
| 3 | The schedule inside the window, a lane per core, folded stretches, and the cluster view at a cycle (D57); 3a G1, S0 to S4, 3b S5 to S7 |

## Round 1a steps

Steps 0 to 5, all done.

## Round 1b steps

Steps 0 to 7, all done.

## Round 2a steps

Steps 0 to 7, all done.

## Round 3 steps

All done. G1: the unit's and the streamer's `class` lines in `beats`,
`tests/snax/classes.py`'s check on `make regress`'s forge/ runs. G1b: those
runs write their traces to `trace.log`, not stdout (the program's output
cut a `class` line in two). S0 to S6 are snax-forge's. S7: `classes.parse`
fails on a `trace.log` line it cannot parse, naming file and line, and the
forge/ runs write only the unit's and the streamer's traces there.

## Round 2a findings

- **The probe (step 1).** An `IoReq` argument slot set by the streamer
  reaches the crossbar and the unit unchanged (the TCDM backend's delayed
  writes carry it themselves); the AXI backend knows a read's data at the
  request's cycle plus its latency plus `read_latency`, a write's ack in the
  request's cycle; a `pe0/insn` line is 209 to 235 bytes; a
  `declare_user_property` is set per run by `--param`, nothing rebuilt.
- **`qmax` is not the RTL's count (step 1).** A writer's push and pop share
  a cycle, push first, so `data.size()` reaches 2 while the RTL's count
  stays 1. Since step 3 `qmax` is the highest RTL count (vecadd's writer 2
  to 1).
- **The crossbar and the iDMA (step 2).** vecadd at `stall`: 192 `grant`
  (12 lanes x 16), 4 `stall`, 24 `dma`, 10 `burst`; vsum 65 grants, 10
  `dma`; task-level `events.log` unchanged. `trace_inputs=core0,dma` keeps
  those sources only; an unknown name stops the run.
- **The streamer and the unit (step 3).** At `stall`: vecadd 16 `fire`, 16
  `push`, 32 `fifo`; vsum 64 `fire`, one `push`. Every `b` a firing names is
  granted on every lane of its mover with the fire's values, every push's
  value is its writer's grants', every lane's `fifo` count is visible minus
  popped, 0 at the end. No fixture has a reader with a repeat.
- **VCD signals (step 4).** `--vcd --event-tags=snax` names 98 SNAX signals,
  their values agreeing with the lines; a value known a cycle ahead is set in
  its cycle (`SnaxSignals`); `--vcd` changes neither `events.log` nor stdout.
- **The converter (snax-forge step 6).** Events at task, beat, stall,
  finegrained: vecadd 49, 307, 343, 494; vsum 41, 182, 186, 374. A trace
  regex with an alternation gave no lines (not looked into).
- **Acceptance (step 7).** Fresh clones of `ry/flow3-4` in the image: here
  (`9f73fa3d`) `make build`, the unit tests (35 OK), `make regress`;
  snax-forge (`192d5e2`) every flow, `pixi run test` 1055 passed, 3 skipped.
- **Sizes (step 7, snax-forge open item 39).** Bytes per run and per output
  element (vecadd's `C` 64, vsum's one sum), beat lines only (the rest of
  `events.log` is 53716 B on vecadd and 49709 B on vsum; of `trace.jsonl`,
  4693 B and 3840 B):

  | Run | Kind | `events.log` lines | B | B per element | `trace.jsonl` B | B per element |
  |---|---|---:|---:|---:|---:|---:|
  | vecadd `beat` | all | 623 | 102873 | 1607 | 66116 | 1033 |
  | vecadd `stall` | all | 659 | 108039 | 1688 | 69504 | 1086 |
  | vecadd | `grant` | 192 | 34502 | 539 | 42674 | 667 |
  | vecadd | `dma` | 24 | 6571 | 103 | 9426 | 147 |
  | vecadd | `fire` | 16 | 3553 | 56 | 4877 | 76 |
  | vsum `beat` | all | 485 | 73181 | 73181 | 31412 | 31412 |
  | vsum `stall` | all | 489 | 73745 | 73745 | 31749 | 31749 |
  | vsum | `grant` | 65 | 11650 | 11650 | 14347 | 14347 |

  GVSoC's header is 55% of vecadd's beat and stall lines' bytes; a grant is
  180 B in `events.log` and 222 B in `trace.jsonl`. Per element, vecadd at
  `stall` is 1.7 KB of `events.log` and 1.1 KB of `trace.jsonl`, of which
  the grants are 539 B and 667 B.

## Round 1b findings

- **One file in simulation order (step 1a).** Several `--trace` regexes
  naming one file land in it in order; a message from a component's `stop()`
  lands last, so end-of-run counters are written there.
- **Function names without the instruction trace (step 1b).** The ELF is
  registered whatever the traces are, so the core writes `func` with the
  name itself (all 31 SNAX CSR accesses resolved).
- **The barrier wait (step 1c).** `Iss::barrier_update` stalls with
  `exec.insn_stall()` unless the barrier is reached; boot holds barriers too.
- **The window and the `mcycle` reads.** The window is the program's own two
  `mcycle` reads: the `snitch` core writes an `mcycle` line per read, and
  snax-forge cuts the trace, the profile and the cores' classes there,
  checking they are `forge cycles:` apart (round 1b fix; it replaced the
  `[func main, func forge_check)` window, vecadd 211 against 226). vecadd:
  reads at 2812 and 3038 on core 0; vsum: boot 2286, 255.
- **Unit, streamer and crossbar (step 2).** The traces come from
  `snax/snax_events.hpp`; the unit's run line is the summary's `run
  index=<i> ...` line. vecadd: 15 crossbar `input` lines and 32 `bank` lines
  of 6 reads and 6 writes; output unchanged (226 cycles, counter 19).
- **Core and iDMA (step 3).** The SNAX targets build `pulp/pulp/idma/`
  (`idma_fe_xdma.cpp`); `pulp/models/ips/pulp/idma_v2/` is an unused copy.
  The core's `state` and `func` are behind `CONFIG_GVSOC_ISS_SNAX_EVENTS`
  (`snitch` only). vecadd's DMA: `transfers=3 busy=54 r_beats=24 w_beats=24
  bytes_to_l1=1024 bytes_from_l1=512`.
- **Acceptance (step 7).** Fresh clones of `ry/flow3-2`: here `make
  build`, the unit tests, `make regress`; snax-forge's four flows, each
  core's classes adding up to the window, `pixi run test` 1810 passed, 5
  skipped; the viewer page by eye is Ryan's.

## Findings (round 1a)

- **What pixi's environment changes (step 1).** Its env's `bin/` first on
  `PATH` (`python3`, `make` 4.4.1, conda's binutils as plain `ld`, `as`) and
  conda's compiler setup (`CC`, `CXX`, flags, `CMAKE_ARGS`, ...); so
  `gvsoc/Makefile` puts `/usr/bin/` after the image's Python and unexports it.
- **The three checks hold (step 1).** A plain-shell build then `pixi run make
  -C gvsoc build`: the three `CMakeCache.txt` byte-identical, nothing
  rebuilt; the same ELF sha256 and stdout from both.
- **The window and the counters without marks (step 2).** Full `make
  regress` passes (64 runs). Windows: vecadd 226, vecmul 226, vsum 255,
  vsum_tree 207 cycles; counters 19, 19, 67, 19, as with the marks.
- **The flow on SNAX-GVSoC (step 3).** vecadd 226 and 19, vsum 255 and 67,
  exit 0, about 3 s a flow once built; this tree stays clean.
- **The program's exit code is not its error count (step 3).** Two wrong
  goldens print `forge errors: 2` and exit 1, so the flow reads the counts
  from the printed lines and only pass or fail from the exit.
- **Acceptance (steps 4 and 5).** Both flows passed; `pixi run test` 1733
  passed, 6 skipped. The `gvsoc` job rehearsed on a fresh clone (`-j4`, no
  ccache): build 314 s, flows 20 s and 6 s; timeout 45 minutes.
