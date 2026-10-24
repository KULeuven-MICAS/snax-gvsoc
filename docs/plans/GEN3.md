# GEN3 plan: a generated accelerator on SNAX-GVSoC

GEN3 is a task of M14 in snax-forge (D127 to D130 there): a BRM's design
point gives a generated accelerator on SNAX-GVSoC, decoupled from the flow,
with hooks for FLOW3. Branch `ry/gen3`, here and in snax-forge.

## What it models

From source; snax_cluster at the pin of `sw/README.md` (`05615e4`).

- `ElementwiseTiledSpatial`: `lanes`, `opSel`, `loopCount` (0 refused);
  `a.ready = b.ready = busy && out.ready`. Latency 0, II 1.
- `Accumulator` (round 4, D133): `loopCount` (n), `len` (T); one register for
  the sum and the result, so no drain cycle. Latency 1, II 1.
- snax_cluster's shell wrapper: `ro_set[0]` busy, `ro_set[1]` the counter,
  `ctrl.ready` idle; a start is bit 0 written to the last read-write CSR.

## The binding

A BRM implementation's `binding` (D129): `block`, `args` and `csrs` as
`expr.py` expressions (`elementwise_add`: `lanes: W`, `loopCount: n`;
`chisel_accumulator`: `loopCount: n`, `len: T`), `control: counted`, `wait`
`lockstep`, `pipelined` (D35) or later `buffered`. The data width is the
ports' shared `dtype`; `SnaxUnit`'s `config` names each word's role, `count`
or `rate`.

## Where things go

- C++ in `snax/`: `SnaxUnit` and `SnaxShell` (D128), every property read
  with `get_js_config` (a platform tree holds no SNAX properties); gvrun runs
  a target without its platform tree on the JSON config path, with a warning
  (`runner_gvrun2.py`, round 1b F1).
- The generator's Python output (composite, target, install check, the
  `forge_` names, D132): replaced in LNK2a round 2 (D134).
- One fixture per design point in `forge/<design>/`, the generator's output
  untouched, its diff the check (D128); named by its path from snax-forge's
  root and byte-identical wherever written (round 2b F3), so
  `tests/gen/test_fixture.py` regenerates and compares it.

## Hooks for FLOW3

`generate(design_point, out_dir, install=None, root=None) -> Manifest`
(`pixi run gen-gvsoc`): the manifest lists `symbols`, the files, the unit's
trace path, the CSR layout and each task's beats. `SnaxUnit`'s run line:
busy + stall_in + stall_out + flush is the run's busy cycles, which
SnaxShell's counter counts (round 1b F2).

## The rounds

1: steps 0a to 2; 1b: F1 to F4; 2: LNK1 (D131), 3, 4; 2b: F1 to F4; 3: 5,
6a, 7; 4: 6b.

## Acceptance

As GEN3's row in snax-forge `docs/STATUS.md`; every round done.

## Steps

All done. 0a this repo a snax-forge submodule (D128); 0b a `--target-dir`
target reusing built components compiles nothing; 1 `SnaxUnit`; 2
`SnaxShell`; 3 the binding and the generator; 4 the headers (vecadd's
`ACC_RW_LOOP_COUNT` 978 to `ACC_RO_PERF_COUNT` 981); 5, 6a, 6b
`forge/vecadd/`, `forge/vecmul/`, `forge/vsum/` (`AccumulatorRateSpec`, five
rate cases); 7 snax-forge's `ElementwiseTiledSpatialLockstepSpec` on every
lockstep case of `tests/snax/unit/cases/`: the four agree, a flipped busy bit
fails. Round 1b: F1 the no-platform-tree path, F2 `flush` in the run line,
F3 `check_counter`, F4 docs. Round 2b: F1 `pixi.lock` with pixi 0.41.4, F2
the ci tests in full (1693 passed), F3 the design point named by its path
(`gen.point`), F4 the install check.

## Open

- A start in the run's last cycle E is held and sent in E + 1; the case
  `start_in_last_cycle` checks it (GEN2b), but no program runs it.
- `csrrw` with a destination register on a held start: the core's pending
  write path (`snax_csr_response`) was run only with rd = x0 (`csrw`).
- No kernel gives a fold with more than one sum per run (T < n); `make
  regress` runs `forge-reduce.vsum-r16` (len 16, four sums) by hand.
- n not a multiple of T: `SnaxUnit` stops (fatal), the Chisel Accumulator
  ends the last sum at the n-th input; the BRM's rates make n a multiple of
  T (D25), so neither is run.
- The Accumulator's `in.ready` depends on `out.ready` combinationally, for
  GEN1 to keep in mind behind the streamer.
