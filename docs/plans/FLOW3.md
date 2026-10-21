# FLOW3 plan: the flow ends in a SNAX-GVSoC run

FLOW3 is a task of M14 in snax-forge (D127, D136, D137 there): `pixi run
flow` generates a design point, builds its program and runs it here, on
`snax_hjson`, and the program checks itself. Round 1 is one PR in each repo;
RET1 (SNAX-MODEL removed from snax-forge) is its round 1c.

This file is the checklist; a step is ticked here when it is committed.

## How the steps are run

- On the MICAS server, by Claude Code, in snax-forge's image
  (`ghcr.io/kuleuven-micas/snax-forge:main`).
- One commit per step on `ry/flow3`, here and in snax-forge; from step 2 on,
  snax-forge's submodule points at this branch's head. Round 1a is tagged
  `flow3-r1a` in both. Round 1b the same on `ry/flow3-2`, tagged
  `flow3-r1b`; round 2a on `ry/flow3-4`, tagged `flow3-r2a` (local).
- Acceptance is pass/fail; anything not verified is said so.

## Acceptance

Round 1a: `pixi run flow recipes/vecadd.json --platform
platforms/snax_alu.json`, and the same for `recipes/vsum.json`, end in a
checked SNAX-GVSoC run (passed, exit 0), in the container and in snax-forge
CI's `gvsoc` job.

Round 1b: the same two flows at `--trace task` pass, the converter's
invariants hold, and they write `report/design.md` and `report/run.md`; at
`--trace off` the profile comes from the `summary` lines alone; `pixi run
view` opens the two task-level runs on the profile page; `make regress`
here and snax-forge's `pixi run test` pass in the container, and CI on both
branches.

Round 2a: in the container, `pixi run flow` on `recipes/vecadd.json` and
`recipes/vsum.json` (`platforms/snax_alu.json`) passes at `--trace off`,
`task`, `beat`, `stall` and `finegrained`, every converter invariant
holding; tracing changes nothing: each run's `forge cycles:` is its `off`
run's, and the `profile.json` of its `beat`, `stall` and `finegrained` runs
is byte-identical to its `task` run's; one flow with `--vcd` writes the VCD,
each SNAX signal named, and `view.gtkw` into `run/`; `make regress` here and
snax-forge's `pixi run test` pass; the sizes of `events.log` and
`trace.jsonl` at `beat` and `stall`, per line kind and per output element,
are in the findings; snax-forge CI's `gvsoc` job also runs vecadd at
`--trace stall`.

## The rounds

| Round | Content |
|---|---|
| 1a | The flow on SNAX-GVSoC: snax-forge's `gvsoc/Makefile` names the image's tools, so the flow calls make from pixi; `gvrun` runs on `GVRUN_PYTHON`; the program's window and `forge_check()` in place of the marks; the flow's stages lower, gen, build, sw, gvsoc, check; snax-forge CI's `gvsoc` job |
| 1b | The events (snax-forge D137): an `events` `vp::Trace` per SNAX component here, in this repo's own grammar (component path, port, address, cycle; class runs; counters at the end of the run), enabled per path; snax-forge's converter into its C§7; levels `task` and `beat`; the reports again |
| 1c | RET1: SNAX-MODEL removed from snax-forge, in round 1's PR |
| 2a | The beat- and stall-level events (`docs/EVENTS.md`): the crossbar's `grant`, `dma` and `stall`, the AXI backend's `burst`, the unit's `fire` and `push`, the streamer's `fifo`, linked by ids and carrying values (snax-forge open items 23, 25); the `stalls` trace; the levels `beat`, `stall` and `finegrained` (the cores' `insn`); the crossbar's source filter; VCD signals, a gtkwave dump only; snax-forge's converter for them, with its invariants |
| 2b | snax-forge's memory view (D96) and movement view (D97) rebuilt on 2a's events, on `ry/flow3-5` |
| 3 | The schedule inside the program's window, with a lane per core and folded stretches (snax-forge D57) |

## Round 1a steps

| # | Step | Status |
|---|---|---|
| 0 | Docs in both: snax-forge D136, D137, D135, D128, D127 and D57 amended, C§7 and C§16, STATUS (FLOW3, RET1 folded in, open items 56, 57, 60 closed, 82 opened), ARCHITECTURE; this file | done |
| 1 | Tools: snax-forge's `gvsoc/Makefile` names Python, CMake and the host compilers and unexports what pixi sets; every `cmake` in this Makefile is `$(CMAKE)`; `gvrun` ends in `exec "${GVRUN_PYTHON:-python3}"`. Checked by hand: no rebuild from pixi after a plain-shell build, the same ELF and stdout from both | done |
| 2 | snax-forge `lower/c.py`: the marks out; each counter in `forge_counter[]`; `forge_check(t0)` prints `forge cycles:` then the self-check; forge/ refreshed; `make regress` | done |
| 3 | snax-forge: the flow's stages after design are lower, gen, build, sw, gvsoc, check; `run.json` | done |
| 4 | snax-forge CI: the `gvsoc` job, the flow on vecadd and vsum | written, rehearsed on a fresh clone; its GitHub run waits for a dispatch on `ry/flow3` |
| 5 | Acceptance in the container and in CI; tag `flow3-r1a` | container: done; CI: waits for step 4's run |

## Round 1b steps

The grammar is `docs/EVENTS.md`.

| # | Step | Status |
|---|---|---|
| 0 | Docs in both: snax-forge D137 amended, C§7 for its `run/` (and its contract test), STATUS; this table, `docs/EVENTS.md` | done |
| 1 | Probe, no code kept: (a) one `--trace` file collects several components' traces in simulation order; (b) `func` names resolve on a plain `snax_hjson` run; (c) the barrier wait is an `insn_stall` | done |
| 2 | Unit, streamer and crossbar: the three traces, their lines, the crossbar's counters; `make regress` | done |
| 3 | Core and iDMA hooks (`pulp/pulp/idma/fe/idma_fe_xdma.cpp`, the front end the SNAX targets build); `make regress`; one fixture's `events.log` at task level | done |
| 4 | snax-forge `run/`: profile, trace, cluster, events, outputs, and their tests | done |
| 5 | snax-forge `run/convert.py`, the flow's `convert` stage, a recorded vecadd `events.log` as a test fixture | done |
| 6 | snax-forge's viewer and reports on `run/`, the reports written by the flow | done |
| 7 | Acceptance in both; CI's `gvsoc` job runs the two flows at `--trace task`; tag `flow3-r1b` | container: done; CI: waits for a dispatch on `ry/flow3-2` in both |

## Round 2a steps

The grammar is `docs/EVENTS.md`.

| # | Step | Status |
|---|---|---|
| 0 | Docs in both: snax-forge STATUS (RET1 done, round 2 as 2a and 2b), D137 amended, C§7 and `run/trace.py`'s docstring; `docs/EVENTS.md`, this table | done |
| 1 | Probe, no code kept: (a) an `IoReq` argument slot set by the streamer and by the TCDM backend reaches the crossbar unchanged; (b) the streamer can return `b` to the unit with a beat; (c) the AXI backend's path, where a burst's `back` is known; (d) the TCDM backend computes `l2` per beat (1D, 2D); (e) a `pe<i>/insn` line on `snax_hjson`; (f) `--trace-format`; (g) the crossbar's inputs property set per run without a rebuild | done |
| 2 | Crossbar and iDMA: `grant`, `dma`, `stall`, `trace_inputs`; the TCDM backend's `id`, `i`, `l2`; the AXI backend's `burst`; traces off change nothing; `make regress`; snax-forge's submodule bumped | done |
| 3 | Streamer and unit: `b` numbered and passed; `fifo`; `fire` and `push`; `make regress`; one fixture's `events.log` at `stall` parses; submodule bumped | done |
| 4 | VCD signals on the unit, streamer, crossbar and iDMA, tagged `snax`; a `make run` with `--vcd` writes a VCD naming each; submodule bumped | done |
| 5 | snax-forge `run/`: `regions_of`, `Cluster.bank_row` and `dma_beat_bytes`, the grammar of `beats`, `stalls` and `insn`, the trace's kinds and levels | done |
| 6 | snax-forge's converter (beat, stall, finegrained, every invariant), the flow's `--trace LEVEL[:SOURCES]` and `--vcd`, a recorded vecadd `events.log` at `stall`, `docs/RUN.md` in both | done |
| 7 | Acceptance in both; snax-forge CI's `gvsoc` job at `--trace stall`; sizes (snax-forge open item 39); tag `flow3-r2a` | todo |

## Round 2a findings

- **The probe (step 1).** forge/vecadd on `snax_hjson` with temporary
  prints, then reverted; each answer from a run unless said.
  (a) Holds. Argument slot 15 set by the streamer on its requests arrives
  at the crossbar's `req` unchanged, `arg_current_index()` 0 (the streamer
  is bound straight to `in_<i>`; the cores' requests come through
  `cores_ico` with slot 15 still 0). The TCDM backend's slots 13 to 15
  arrive at `dma_req` unchanged for reads; its writes go through the
  delayed request (`tcdm_write_latency`, `delayed_req`), which must carry
  the slots itself: tagged there, all 16 write beats arrived tagged.
  (b) Holds. A slot the streamer's `reader_req` sets on the unit's
  `beat_req` is read by the unit after `move` (32 tags, one per port and
  firing, in order).
  (c) The AXI backend is `/chip/soc/cluster_0/idma/axi_read` and
  `.../idma/axi_write` (`IDmaBeAxi`, a `vp::Block`). Every request
  returned `IO_REQ_OK` with its latency (reads 6 or 7, writes 6): a read's
  data is back at `read_handle_req_end`, the request's cycle plus that
  latency plus `read_latency`; a write is acknowledged in
  `write_handle_req_end`, called at once on `IO_REQ_OK`, so in the
  request's cycle. On `IO_REQ_PENDING` both would be known at
  `axi_response`. A router rewrites a request's address during `req`, so
  the address is taken before it.
  (d) Holds, 1D and 2D (one load as 4 rows of 128 B, the store as 2 rows of
  256 B, temporarily in forge/vecadd's `main.c`): `IDmaBe::write_data`
  moves a row transfer's `dst` and `size` as data goes, so the row's `src`
  and `dst` are kept when `IDmaBe::enqueue_transfer` takes it; the other
  side's address of a beat at `a` is then that row's start plus `a`'s
  offset in it. All 24 beats' `l2` were right.
  (e) A `pe0/insn` line (5353 on vecadd) is GVSoC's header, then
  `<func>:<n>` padded, the mode (`M`), the PC in hex without `0x`, the
  mnemonic, its operands and the registers it writes and reads (`a0=...`,
  `sp:...`, `PA:...`), not `<cycle> <kind> key=value`; 209 to 235 bytes.
  (f) From the code (`trace_engine.cpp`, `trace.cpp`): `--trace-format
  short` writes `<ps>ps <cycles> `, without the path the converter names a
  line by; `long` (the default) pads the path to the longest one (72
  characters here) inside ANSI colour codes. No shorter form keeps the
  path.
  (g) A property declared in `snax_tcdm_xbar.py` with
  `declare_user_property` (a gvrun `TargetParameter`) is set by `--param
  chip/soc/cluster_0/tcdm/snax_xbar/<name>=<value>`: the C++ read the
  given value from `get_js_config()`. `snax_hjson` builds its tree from
  Python at run time for a design point's cluster file, so nothing is
  rebuilt.
- **A queue's count: `qmax` is not the RTL's count (step 1).** `qmax` is
  the highest `data.size()` after any push or pop, so within a cycle; the
  priority hint reads the RTL queue's count, the words visible by then and
  not popped before. A writer's beat is pushed by the unit and the head
  word popped at the commit in one cycle, the push first: `data.size()` is
  2 for a moment while the RTL's count stays 1. On vecadd, from both
  counts per lane: readers 2 and 1 both ways, the writer `qmax` 2 against
  a highest count of 1, on all four lanes. So a `fifo` line cannot carry
  one count whose maximum is `qmax` and that is also the words visible
  minus the words popped.

- **The crossbar and the iDMA (step 2).** forge/vecadd and forge/vsum on
  `snax_hjson`: at task level their `events.log` is byte-identical to the
  one before the change; with `beats` and `stalls` on too, their stdout is
  the same and so are their `summary` and `events` lines. vecadd at
  `stall`: 192 `grant` lines (the 12 streamer lanes, 16 each), 4 `stall`,
  24 `dma` (copies 2 and 3 eight writes each into L1, copy 4 eight reads,
  `i` 0 to 7 in each) and 10 `burst` (two 512-byte reads, eight 64-byte
  writes, each acknowledged in its own cycle); vsum 65 grants, 10 `dma`.
  With `trace_inputs=core0,dma` the crossbar writes core 0's 322 grants
  (from boot) and the DMA's beats only; an unknown name stops the run.

- **The streamer and the unit (step 3).** `qmax` is now the highest RTL
  count (the decision after step 1), so of the forge fixtures only
  vecadd's summary changes, its writer's `qmax` from 2,2,2,2 to 1,1,1,1
  (vecmul's the same way); vsum's `events.log` at task level is
  byte-identical, and every stdout is. At `stall`: vecadd 16 `fire` (`b`
  0 to 15 on both readers), 16 `push` and 32 `fifo`; vsum 64 `fire` and one
  `push` (`first=0 last=63`); vsum_tree 16 and one; `forge-reduce`'s
  vsum-r16 64 `fire` and four `push` (`first` 0, 16, 32, 48). Checked
  against each other by a script on all five (not kept; snax-forge's
  converter checks the same from step 6): every `b` a firing names is
  granted on every lane of its mover with the fire's values, every push's
  value is its writer's grants', and every lane's `fifo` lines are the
  words visible (a read's `back` plus one, a push plus one) minus those
  popped (the last firing naming the beat, the writer's grant), 0 at the
  end, their highest the summary's `qmax`. No fixture has a reader with a
  repeat, so several firings naming one `b` is checked by the code only.
  This repo has no test of its own for an events file; the stall-level
  file is parsed by snax-forge's converter from step 5 on.

- **VCD signals (step 4).** forge/vecadd with `--vcd --event-tags=snax`
  (snax-forge's `gvsoc/Makefile`'s `run` with these in `GVRUN_ARGS`):
  `all.vcd` (194 kB) and `view.gtkw` name all 98 SNAX signals (the unit's
  4, the streamer's 16, the crossbar's 45 for its 15 inputs and 32 for its
  banks, the DMA's busy), beside the cores' own. Their values agree with
  the lines: the unit busy from 2933 to 2951 (start at 2932), `fire` high
  through its 16 firings, `reader0_lane0_count` changing at 2935, 2936,
  2951 and 2952 as its `fifo` lines, `dma_busy` from 2887 to 2926 and from
  2974 to 2989. GVSoC dumps a signal when it is set, so a value known a
  cycle ahead is queued and set in its cycle (`SnaxSignals`,
  `snax/snax_events.hpp`). With and without `--vcd` the `events.log` at
  task level is byte-identical, as are the program's lines (gvrun adds
  its gtkwave lines to stdout).

- **The converter and the flow (snax-forge step 6).** In the container,
  with the submodule at `fec4c219`, `pixi run flow` on vecadd and vsum
  (`platforms/snax_alu.json`) at `off`, `task`, `beat`, `stall` and
  `finegrained`, and vecadd at `stall --vcd`, all passed with every
  invariant: vecadd 49 events at task, 307 at beat, 343 at stall, 494 at
  finegrained; vsum 41, 182, 186, 374. Each `forge cycles:` is the `off`
  run's (226, 255) and each `profile.json` above `task` is the task run's,
  byte for byte. One regex with an alternation,
  `--trace='/idma/axi_(read|write)/beats$:F'`, gave no lines, though the
  engine compiles its regexes `REG_EXTENDED` (why was not looked into); the
  flow names the two traces apart.

## Round 1b findings

- **One file in simulation order (step 1a).** snax-forge's vecadd ELF on
  `snax_hjson` with `--trace='/trace$:FILE'`: 18046 lines of 82 components
  in one file, the header's time never decreasing. With a second regex
  naming the same file (`--trace='pe0/insn$:FILE'`) both land in it,
  interleaved in order (5353 `insn` lines among them): the trace engine
  opens a file once per name. A message written from a component's
  `stop()` lands last (cycle 20001), so counters at the end of the
  simulation can be written there.
- **Function names without the instruction trace (step 1b).** The cores'
  `binaries` property names the ELF on a plain run, and `Trace::build`
  registers it whatever the traces are; `iss_trace_pc_info` parses the
  symbols on first use. Called from `Iss::snax_csr_request` on a run with
  no `insn` trace, all 31 SNAX CSR accesses resolved (`forge_core_0`), none
  failed. So the core writes `func` with the name itself; the fallback (the
  PC only, names looked up by the converter) is not needed.
- **The barrier wait (step 1c).** `Iss::barrier_update` stalls with
  `exec.insn_stall()` (`is_stalled()` true after it) unless the barrier is
  already reached, and `Iss::barrier_sync` releases; `Exec::busy_exit` ran
  only at reset and at the program's end (cycles 19302 and 19313), never in
  a barrier. Boot holds barriers too (core 0 waits from 1958 to 2106 and
  2161 to 2796).
- **The window and the `mcycle` reads.** On core 0, `main` is entered at
  cycle 2799 and `forge_check` at 3010, a window of 211 cycles; `forge
  cycles:` says 226, the reads being at 2812 (13 cycles in) and 3038 (28 in:
  an I-cache refill in `forge_check`'s prologue). Each read comes before
  the core leaves its function (`forge_core_0` at 2845, `printf_` at
  3044), so snax-forge's converter checks that `forge cycles:` lies in what
  the two reads allow: at least `forge_check`'s entry minus the cycle main
  is left, at most the cycle `forge_check` is left minus main's entry.
  Before `main`, `snrt_main` runs from 1929.
- **Unit, streamer and crossbar (step 2).** The three traces come from
  `snax/snax_events.hpp`. The unit's `SnaxUnitRule::run_line` is now the
  summary's `run index=<i> ...` line, so its debug trace, the unit tests'
  cases and `regress.py`'s counter check read that form. snax-forge's
  vecadd ELF with `--trace='/summary$:F' --trace='/events$:F'`: the
  streamer's three `start` lines at 2931, the unit's `start` at 2932,
  `done` lines for reader0 (2948), reader1 (2949), the unit (2951, firings
  at 2936 to 2951) and writer0 (2952), the streamer's `mover` lines at 2953;
  at the end the crossbar's 15 `input` lines (12 streamer lanes with 16
  grants each, `core0`, `core1` and `axi` marked `whole_run=1`) and 32
  `bank` lines, each bank 6 reads and 6 writes (the streamer's 192 words and
  the DMA's 192, over 32 banks). The run's output is unchanged (226 cycles,
  counter 19). `make regress` on a fresh build passes.
- **Core and iDMA (step 3).** The iDMA the SNAX targets build is
  `pulp/pulp/idma/` (`pulp.idma.snitch_dma`), whose front end has SG2's busy
  wire and the beat wires; `pulp/models/ips/pulp/idma_v2/` is a copy no SNAX
  target compiles, left as it is. `issue` is written in `enqueue_copy`, where
  the copy gets its ID, `done` in `ack_transfer`; the busy cycles follow
  `update_busy`'s edges as `DMA_BUSY` counts them, the beats `send_beats`.
  The core's `state` and `func` come from the exec code every core shares,
  so they are behind `CONFIG_GVSOC_ISS_SNAX_EVENTS`, set for the `snitch`
  core only. forge/vecadd at task level (`--trace='/summary$:F'
  --trace='/events$:F'`), `build/work/forge-vecadd-task/events.log`, 362
  lines: on core 0 `func main` at 2799 and `func forge_check` at 3010; the
  busy CSR's reads fold into `poll ... first=2933 last=2951 count=10`, then
  one read of 0 at 2953; the barrier before the start waits from 2912 to
  2930; the DMA's three copies (IDs 2 to 4) issued at 2887, 2905 and 2974
  and done at 2909, 2926 and 2989; its summary `transfers=3 busy=54
  r_beats=24 w_beats=24 bytes_to_l1=1024 bytes_from_l1=512`; core 0 wrote
  18 SNAX CSRs and read 13. Boot shows too: `func` lines from 1713, two
  barriers per core before `main`. `make regress` on a fresh build passes.
- **The converter on the flows (snax-forge steps 5 and 6).** vecadd at
  `--trace task`: main's entry at 2799 (the boot), `forge_check`'s 211
  cycles later, inside what the two `mcycle` reads allow for `forge
  cycles: 226`; 48 events in the window. vsum: boot 2273, window 246
  against 255, 40 events. At `off` the profile comes from the `summary`
  lines alone; with the events the same profile plus the cores' classes and
  waits.
- **Acceptance (step 7).** On fresh clones of `ry/flow3-2` in the image:
  here, `make build` (snax-forge's image, `SNAX_TARGETS`), the unit tests
  (`python3 -m unittest discover -s tests/snax`, 35 OK) and `make regress`
  passed. snax-forge with the submodule at `5a8bfbd4`: `pixi run flow` on
  `recipes/vecadd.json` and `recipes/vsum.json` with
  `platforms/snax_alu.json` passed at `--trace task` and `--trace off`, the
  converter's invariants held (it fails the flow otherwise), each wrote
  `report/design.md` and `report/run.md`; the viewer served both task runs
  (`/api/run/<name>` with the profile, the cluster and the trace's window;
  the profile page by eye is Ryan's); `pixi run lint` clean and `pixi run
  test` 1811 passed, 5 skipped; both trees clean after. CI's python job
  rehearsed on a clone without the submodule (`-e ci`): lint clean, 1787
  passed, 29 skipped. The workflows run on pushes to main, pull requests
  and dispatch only, so their runs on `ry/flow3-2` wait for a dispatch from
  GitHub.

- **One window (round 1b fix).** The converter cut the trace and the
  cores' classes at `[func main, func forge_check)` (vecadd 211 cycles)
  while the profile used `forge cycles:` (226). The `snitch` core now writes
  an `mcycle` line for every read of `mcycle` (and `mcycleh`), from
  `Csr::mcycle_csr_access`, so snax-forge cuts all three at the program's
  own two reads, picked by the function span each falls in, and checks they
  are exactly `forge cycles:` apart. vecadd: reads at 2812 and 3038 on core
  0, 226 apart, boot 2812; vsum: boot 2286, 255. On fresh clones of
  `ry/flow3-2` in the image: here `make build`, the unit tests and `make
  regress` passed; snax-forge's four flows (vecadd and vsum at `--trace
  task` and `off`) passed, each window equal to `forge cycles:`, each core's
  classes adding up to it, and `pixi run test` 1810 passed, 5 skipped.

## Findings (round 1a)

- **What pixi's environment changes (step 1).** `env` under `pixi run`
  against the image's plain shell: pixi puts its env's `bin/` first on
  `PATH` (its `python3`, `make` 4.4.1, `ninja`, and conda's binutils as
  plain `ld`, `as`, `ar`), and adds conda's compiler setup: `CC`, `CXX`,
  `CPP`, `GCC`, `GXX`, the `*_FOR_BUILD` compilers, `CFLAGS`, `CXXFLAGS`,
  `CPPFLAGS`, `LDFLAGS`, `LDFLAGS_LD`, the `DEBUG_*` flags, `AR`, `AS`,
  `LD`, `NM`, `RANLIB`, `STRIP`, `OBJCOPY`, `OBJDUMP`, `READELF` and the
  other binutils names, `CONDA_BUILD_SYSROOT`, `HOST`, `BUILD` and their
  aliases, `MESON_ARGS`; CMake-relevant, `CMAKE_ARGS` and
  `CMAKE_PREFIX_PATH` (pixi's env first). It also sets `CONDA_PREFIX`,
  `PIXI_*`, `JAVA_HOME`, `DACE_default_build_folder`, `SNAX_FORGE_HW_OUT`,
  `OMP_NUM_THREADS=1` and `GSETTINGS_SCHEMA_DIR`, which no build reads.
  `PYTHONPATH` and `LD_LIBRARY_PATH` are untouched. The host gcc finds `ld`
  and `as` through `PATH` (`gcc -print-prog-name=ld` is `ld`), so
  snax-forge's `gvsoc/Makefile` puts the host compilers' folder
  (`/usr/bin/`) right after the image's Python on its recipes' `PATH`, and
  unexports the compiler setup above; `CC` and `CXX` are its own unless
  given on make's command line.
- **The three checks hold (step 1).** With `out/snax-gvsoc/` wiped, `make
  -C gvsoc build` in the plain shell (this branch's checkout as
  `SNAX_GVSOC`), then `pixi run make -C gvsoc build`: the three
  `CMakeCache.txt` (GVSoC, gvrun, config_tree) byte-identical before and
  after, no object or library newer than before it, none of the build's
  `Building` or `Linking` lines; the cache names `/usr/bin/gcc`, `g++`,
  `ar` and `ld`. `make sw APPS=forge` on snax-forge's generated vecadd,
  with `build/sw/` and snax-forge's `out/snax-gvsoc/sw/` wiped before each:
  ELF sha256 `4fe8f544...4d28dd` from both. `make run` on `snax_hjson`:
  byte-identical stdout (`forge data: 0 errors (64 words)`, `forge counter
  add_acc: 19`, `forge errors: 0`), exit 0 from both.
- **The window and the counters without marks (step 2).** forge/ refreshed
  from snax-forge's generator (only the four `main.c` changed); full `make
  regress` on a fresh build passes (64 runs). The windows: vecadd 226,
  vecmul 226, vsum 255, vsum_tree 207 cycles; the counters are the marked
  programs' (19, 19, 67, 19). `forge-reduce` is hand-written and never used
  the marks: unchanged. With one accelerator task, clang keeps the static
  `forge_counter[1]` as one symbol, `forge_counter.0`.
- **The flow on SNAX-GVSoC (step 3).** `pixi run flow` on vecadd and vsum
  (`platforms/snax_alu.json`) gives the fixtures' windows and counters
  (226 and 19, 255 and 67), exit 0; its first run built GVSoC (the build's
  folder came from another checkout), the next ones found it up to date
  (about 3 s a flow). The build, `make sw` and `make run` leave this repo's
  tree clean (`git status --porcelain` empty), so a flow does not see its
  own build as a dirty tree.
- **The program's exit code is not its error count (step 3).** A vecadd
  program with two goldens changed by hand prints `forge errors: 2` and the
  run exits 1 (`make: *** [Makefile:110: run] Error 1`), so the flow reads
  the counts from the printed lines and only pass or fail from the exit.
- **Acceptance in the container (step 5).** `pixi run flow` on
  `recipes/vecadd.json` and `recipes/vsum.json` with
  `platforms/snax_alu.json`: passed, exit 0, both. snax-forge's `pixi run
  test`: 1733 passed, 6 skipped (the reports, the memory and movement
  views, loop1, dot twice).
- **The `gvsoc` job, rehearsed (step 4).** Its steps on a fresh shallow
  clone of snax-forge's `ry/flow3` with the submodule, in the image, with
  `-j4` and no ccache: the build 314 s, `pixi install -e ci` 18 s, the two
  flows passed (20 s and 6 s, the build found up to date), the two tests
  marked `gvsoc` passed; both trees clean after. The job's timeout is 45
  minutes. The python job, rehearsed on a clone without the submodule:
  lint clean, 1711 passed, 28 skipped. The workflow runs on pushes to main,
  pull requests and dispatch only, so its run on `ry/flow3` is a dispatch
  from GitHub.
