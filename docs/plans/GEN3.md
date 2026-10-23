# GEN3 plan: a generated accelerator on SNAX-GVSoC

GEN3 is a task of M14 in snax-forge (D127 to D130 there): a BRM's design
point gives a generated accelerator on SNAX-GVSoC. It is fully decoupled
from the flow, with hooks for FLOW3. Acceptance below.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- On the MICAS server, by Claude Code, in snax-forge's image
  (`ghcr.io/kuleuven-micas/snax-forge:main`), as SG7.
- One commit per step on `ry/gen3`, here and in snax-forge, never pushed,
  no pull request.
- Anything not verified is said so.

## What it models

From source; snax_cluster at the pin of `sw/README.md` (`05615e4`).

- snax-forge `hw/chisel/.../elementwise/ElementwiseTiledSpatial.scala`:
  `lanes` lanes, `opSel` (`ElementwiseOp`, xor = 5), `loopCount` (0
  refused), start, busy, done; Decoupled `a`, `b`, `out`.
  `a.ready = b.ready = busy && out.ready`; `out` is valid when both inputs
  fire. Latency 0, II 1.
- snax-forge `hw/chisel/.../samples/Accumulator.scala` (round 4, D133
  there): `loopCount` (n) and `len` (T), start, busy, done as
  `ElementwiseTiledSpatial`'s (0 in either ignored); Decoupled `in`, `out`;
  one output per `len` inputs, the last at the n-th. One register holds the
  sum and the result: `in.ready = busy && !allIn && (!valid || out.ready)`,
  the next input loaded as a result leaves, so no drain cycle. Latency 1,
  II 1.
- snax_cluster `hw/chisel_acc/.../gemmx/BlockGemmRescaleSIMD.scala`: the
  `ctrl` bundle, and the generator writing
  `snax_streamer_gemmX_shell_wrapper.sv`: `csr_reg_set_i` to the
  configuration fields, `csr_reg_set_valid_i` / `csr_reg_set_ready_o` to
  ctrl valid / ready, `ro_set[0]` busy, `ro_set[1]` the counter,
  `stream2acc` / `acc2stream` to the data ports.
- snax_cluster `hw/chisel_acc/.../gemm/BlockGemm.scala:240`: `ctrl.ready`
  is idle.
- snax_cluster `hw/chisel/.../reqRspManager/ReqRspManager.scala`: a start
  is bit 0 written to the last read-write CSR.
- snax_cluster `hw/templates/snax_acc_wrapper.sv.tpl`: CSR mux, CSR
  manager, streamer, shell wrapper; `snax_barrier_o` tied 0.

## The binding

An implementation's `binding` in a BRM (D129), for `elementwise_add`:

```json
{"block": "ElementwiseTiledSpatial",
 "args": {"lanes": "W", "supportedOps": "op"},
 "control": "counted",
 "csrs": [{"field": "loopCount", "value": "n"}],
 "wait": "lockstep"}
```

- Every value in `args` and `csrs` is an expression in snax-forge's
  `expr.py` grammar.
- The data width comes from the ports' `dtype`, which all ports of a unit
  share; a mismatch is an error.
- A fixed op gives no `opSel` CSR.
- `control`: `counted` (the block counts its firings), the only kind; the
  start's configuration holds the count. `csrs` may hold more than one
  field: `accumulate`'s `chisel_accumulator` (round 4):

  ```json
  {"block": "Accumulator",
   "args": {},
   "control": "counted",
   "csrs": [{"field": "loopCount", "value": "n"}, {"field": "len", "value": "T"}],
   "wait": "pipelined"}
  ```

  `SnaxUnit`'s `config` names each configuration word's role, `count` or
  `rate` (`["count", "rate"]` here; `["count"]` by default, not written).
- `wait`: `lockstep` (all inputs and room on `out` in one cycle),
  `pipelined` (an L-stage pipeline or output register; D35's rule),
  `buffered` later.

## Where things go

- C++ in `snax/`: `SnaxUnit` and `SnaxShell` (D128). SNAX components read
  every property with `get_js_config`, never from the compiled config
  struct: a target's platform tree holds its components and bindings, not
  SNAX properties, which reach the C++ only through the JSON config (step 0b).
- The generator in one snax-forge package. Its output in snax-forge
  `out/gvsoc/<design>/`: the composite, a target putting it in
  `snax_alu`'s accelerator slot, two headers in `include/`, `manifest.json`.
- gvrun reads it with `--target-dir`, the install's `targets` and
  `generators` passed too. It has no platform tree (only a build makes one),
  so gvrun warns and runs it on the JSON config path (`runner_gvrun2.py`,
  round 1b F1).
- A generated or snax-forge target never takes the name of an installed
  target: the install's `targets` come first on gvrun's path and shadow
  `gvsoc/targets` and the generator's output (tried in round 1b F4), as
  they do for any module a target imports. Every generated module starts
  with `forge_`; with an install, the generator refuses a name its
  `targets` or `generators` hold and checks that the modules the files
  import are there (snax-forge D132).
- One fixture per design point `make regress` runs, in `forge/<design>/`
  here (`forge/README.md`): the generator's output, untouched, refreshed by
  hand, its diff the check (snax-forge D128). vecadd and vecmul at W = 4,
  vsum at W = 1.
  The generator's output names the design point by its path from
  snax-forge's root and is byte-identical wherever it is written (round 2b
  F3), so snax-forge's `tests/gen/test_fixture.py` generates it again and
  compares byte for byte when its submodule holds `forge/`. Regress runs a
  fixture through `--target-dir`, never through `TARGETS`.

## Hooks for FLOW3

- `generate(design_point, out_dir, install=None, root=None) -> Manifest`, with a thin
  command (`pixi run gen-gvsoc`); the manifest lists the bound graph's
  `symbols` (vecadd's `{"N": 64}`), the target, the files, the
  `--target-dir`s, the unit's trace path, the CSR layout and each
  accelerator task's beats. `make regress` reads it with plain json
  (`FORGE` in `tests/snax/regress.py`), and `forge-elementwise` and
  `forge-reduce` size their data by `symbols.N`.
- `snax_alu.py` takes its accelerator as a board class attribute
  (`SnaxAluBoard.accelerator`, step 2), as `snax_alu_sparse.py` overrides
  the interconnect.
- `SnaxUnit` prints `run <i>: firings <f> busy <b> stall_in <si> stall_out
  <so> flush <fl>` at the end of a run (`SnaxUnitRule::run_line`); busy +
  stall_in + stall_out + flush is the run's busy cycles, which SnaxShell's
  counter counts (round 1b F2).
- Not in GEN3: the runner, the converter.

## The rounds

| Round | Content |
|---|---|
| 1 | Steps 0a and 0b in snax-forge, 1 and 2 here |
| 1b | Fix-ups F1 to F4, below |
| 2 | LNK1 in snax-forge (D131), steps 3 and 4: done |
| 2b | Fix-ups F1 to F4, below: done |
| 3 | Steps 5, 6a and 7: done |
| 4 | Step 6b, in seven steps across both repos: done |

## Acceptance

As GEN3's row in snax-forge `docs/STATUS.md`.

## Steps

| # | Step | Status |
|---|---|---|
| 0a | SNAX-GVSoC from snax-forge: this repo a submodule at snax-forge `gvsoc/snax-gvsoc`, never fetched by its CI (D128); `gvsoc/Makefile` (`build`, `sw`, `run`) and `gvsoc/targets/` | done |
| 0b | Probe: a target from `--target-dir` that reuses built components starts without a rebuild (GVSoC names a component's `.so` by its sources and flags, `get_generated_component` in `engine/python/gvsoc/systree.py`). Found: nothing compiles and properties reach the C++ through the JSON config, but gvrun stopped on a target without its platform tree; since round 1b F1 it warns and runs it on the JSON config path | done |
| 1 | `SnaxUnit`: `lockstep` and `pipelined`, the op table; standalone tests | done |
| 2 | `SnaxShell`: the CSR manager's behaviour, a start held while busy, busy, the counter; a CSR test (`snax-shell` on the hand-written `snax_tiled_add`) | done |
| 3 | In snax-forge, after LNK1: the binding in `elementwise_add`, the generator (`snax_alu.py`'s accelerator is a board attribute since step 2); it refuses a target name the install has. `forge_vecadd` (W = 4 on `platforms/snax_alu.json`) runs snax-shell with `snax_tiled_add`'s program and unit run lines, after the no-platform-tree warning; nothing compiled | done |
| 4 | The headers: the accelerator's CSRs and the streamer's map, equal to `sw/`'s copy for `snax_alu`'s template. In `include/` of the generator's output, listed in the manifest: `streamer_csr_addr_map.h` (the Chisel header's defines, values and order) and `<instance>_csr.h` (`snax-alu-lib.h`'s form; vecadd's `ACC_RW_LOOP_COUNT` 978 to `ACC_RO_PERF_COUNT` 981) | done |
| 5 | A hand-written vecadd program on the generated headers (`sw/apps/forge-elementwise/`, until GEN2a), the fixture `forge/vecadd/`, `make regress` from its manifest (its counter through `check_counter`, the manifest's `symbols` and beats); snax-forge reproduces the fixture byte for byte | done |
| 6a | `elementwise_mul`: `elementwise_add`'s binding with op mul (2); the test kernel `vecmul` and `recipes/vecmul.json` in snax-forge; the fixture `forge/vecmul/`, run by `forge-elementwise` at `MODE=2` | done |
| 6b | `accumulate`, `control: counted`, `wait: pipelined`: the Chisel Accumulator rewritten with start, busy and no drain cycle (snax-forge D133); `SnaxUnit` folds one input with a runtime rate (`config` `count`, `rate`), five rate cases; the binding (`loopCount` = n, `len` = T) and its adapter; the test kernel `vsum` (`recipes/vsum.json`, W 1, N 64); the fixture `forge/vsum/`, run by `forge-reduce`; snax-forge reproduces it, and `AccumulatorRateSpec` drives the Chisel block through the rate cases, run lines included | done |
| 7 | The lockstep half of the unit cross-check: snax-forge's `ElementwiseTiledSpatialLockstepSpec` drives `ElementwiseTiledSpatial` through every lockstep case of `tests/snax/unit/cases/` (`SNAX_GVSOC_UNIT_CASES`, canceled without it) and checks fire, push and busy per cycle and each start's answer: the four cases agree; a flipped busy bit fails | done |

Round 1b, fix-ups after round 1:

| # | Fix-up | Status |
|---|---|---|
| F1 | gvrun runs a target without its platform tree on the JSON config path, with a warning; snax-forge's `alu_probe` runs, and `tiled_add_sparse_probe` (a component tree no build made) | done |
| F2 | `flush` in the unit's run line: the cycles after the last firing with results still in the pipeline (not frozen), so the four classes add up to the run's busy cycles; the unit test checks that on every case | done |
| F3 | `snax-shell` without layout constants: it prints its first run's counter and `make regress` checks it against the unit's first run line (`check_counter`, for step 5's programs too) | done |
| F4 | Docs: the target-name rule; round 1's open edge cases into Open | done |

Round 2b, fix-ups after round 2 (all in snax-forge):

| # | Fix-up | Status |
|---|---|---|
| F1 | `pixi.lock` written with pixi 0.41.4 (CI's and the image's): main's lock plus `hjson-py`, without the PyPI `cmake`, `distro`, `scikit-build` and `setuptools` that DaCe's `setup.py` asks for only when no cmake >= 3.15 is on PATH (ESAT's Vitis cmake 3.3.2); nothing uses them | done |
| F2 | `pixi run -e ci test` in full (1693 passed); `memory.fit`'s C§14 row says what its fix gives, a test pins below snax_alu's L1 and L2 bases and follows the fix | done |
| F3 | The design point named once, by its path from snax-forge's root, in the manifest and every generated file's header; one design point into two out folders gives byte-identical files; outside the root it is refused (`gen.point`) | done |
| F4 | The install check against round 2's real install: a `forge_` module planted in a copy is refused (`gen.install`), the real install passes with `snax_streamer`, `snax_shell`, `snax_unit` and `snax_alu` found in its `generators` | done |

## Open

- A start written in the run's last cycle E: `SnaxShell` holds it and
  sends it in E + 1; since GEN2b the case `start_in_last_cycle`
  (`tests/snax/shell/`) checks it on `SnaxShellRule` and on the Chisel shell
  wrapper, but no program runs it.
- `csrrw` with a destination register on a held start: the core's pending
  write path (`snax_csr_response`) was run only with rd = x0 (`csrw`).
- No kernel gives a fold with more than one sum per run (T < n):
  `forge/vsum/` is T = N, one sum. `make regress` runs it with the derived
  task list overridden by hand (`forge-reduce.vsum-r16`, len 16, four sums;
  round 4b F1), besides the unit cases and `AccumulatorRateSpec`.
- n not a multiple of T: `SnaxUnit` stops (fatal), the Chisel Accumulator
  ends the last sum at the n-th input; the BRM's rates make n a multiple of
  T (D25), so neither is run.
- The Accumulator's `in.ready` depends on `out.ready` combinationally, for
  GEN1 to keep in mind behind the streamer; `chisel_adder_tree` has no
  binding.
