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
- snax-forge `hw/chisel/.../samples/Accumulator.scala`: `len`, no start or
  busy, `in.ready = !draining`, one output per `len` inputs.
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
 "args": {"lanes": "W", "dataWidth": "dtype_bits(a)", "supportedOps": ["op"]},
 "control": "counted", "csrs": ["loopCount: n"], "wait": "lockstep"}
```

- A fixed op gives no `opSel` CSR.
- `control`: `counted` (the block counts), `stream` (the shell counts;
  `Accumulator`).
- `wait`: `lockstep` (all inputs and room on `out` in one cycle),
  `pipelined` (an L-stage pipeline or output register; D35's rule),
  `buffered` later.

## Where things go

- C++ in `snax/`: `SnaxUnit` and `SnaxShell` (D128).
- The generator in one snax-forge package. Its output in snax-forge
  `out/gvsoc/<design>/`: the composite, a target putting it in
  `snax_alu`'s accelerator slot, two headers, `manifest.json`.
- gvrun reads it with `--target-dir`, the install's `targets` and
  `generators` passed too.
- One generated design point (vecadd, W = 4) checked in here as the
  fixture, refreshed by hand, its diff the check.

## Hooks for FLOW3

- `generate(design_point, out_dir) -> Manifest`, with a thin command; the
  manifest lists the target, the files and the `--target-dir`s.
- `snax_alu.py` takes its accelerator as an argument.
- `SnaxUnit` and `SnaxShell` print firings, busy, `stall_in` and
  `stall_out` at the end of a run, in a fixed format.
- Not in GEN3: the submodule, the runner, the converter.

## The rounds

To be confirmed.

| Round | Content |
|---|---|
| 1 | Steps 0 to 2, here |
| 2 | LNK1 in snax-forge, steps 3 and 4 |
| 3 | Steps 5 and 6 |

## Acceptance

As GEN3's row in snax-forge `docs/STATUS.md`.

## Steps

| # | Step | Status |
|---|---|---|
| 0 | Probe: a target from `--target-dir` that reuses built components starts without a rebuild (GVSoC names a component's `.so` by its sources and flags, `get_generated_component` in `engine/python/gvsoc/systree.py`) | todo |
| 1 | `SnaxUnit`: `lockstep` and `pipelined`, the op table; standalone tests | todo |
| 2 | `SnaxShell`: the CSR manager's behaviour, a start held while busy, busy, the counter; a CSR test | todo |
| 3 | In snax-forge, after LNK1: the binding in `elementwise_add`, the generator; `snax_alu.py`'s accelerator argument here | todo |
| 4 | The headers: the accelerator's CSRs and the streamer's map, equal to `sw/`'s copy for `snax_alu`'s template | todo |
| 5 | A hand-written vecadd program on the generated headers, the fixture, `make regress`; snax-forge reproduces the fixture | todo |
| 6 | `elementwise_mul`; `accumulate` with `control: stream`, `wait: pipelined` | todo |

## Open

- Whether the first vecadd program stays hand-written until GEN2a.
