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
  `flow3-r1a` in both.
- Acceptance is pass/fail; anything not verified is said so.

## Acceptance

Round 1a: `pixi run flow recipes/vecadd.json --platform
platforms/snax_alu.json`, and the same for `recipes/vsum.json`, end in a
checked SNAX-GVSoC run (passed, exit 0), in the container and in snax-forge
CI's `gvsoc` job.

## The rounds

| Round | Content |
|---|---|
| 1a | The flow on SNAX-GVSoC: snax-forge's `gvsoc/Makefile` names the image's tools, so the flow calls make from pixi; `gvrun` runs on `GVRUN_PYTHON`; the program's window and `forge_check()` in place of the marks; the flow's stages lower, gen, build, sw, gvsoc, check; snax-forge CI's `gvsoc` job |
| 1b | The events (snax-forge D137): an `events` `vp::Trace` per SNAX component here, in this repo's own grammar (component path, port, address, cycle; class runs; counters at the end of the run), enabled per path; snax-forge's converter into its C§7; levels `task` and `beat`; the reports again |
| 1c | RET1: SNAX-MODEL removed from snax-forge, in round 1's PR |
| 2 | Data values on beat events and the accelerator's push event (snax-forge open items 23, 25); the level `finegrained`; VCD as a gtkwave dump only |
| 3 | The schedule inside the program's window, with a lane per core and folded stretches (snax-forge D57) |

## Round 1a steps

| # | Step | Status |
|---|---|---|
| 0 | Docs in both: snax-forge D136, D137, D135, D128, D127 and D57 amended, C§7 and C§16, STATUS (FLOW3, RET1 folded in, open items 56, 57, 60 closed, 82 opened), ARCHITECTURE; this file | done |
| 1 | Tools: snax-forge's `gvsoc/Makefile` names Python, CMake and the host compilers and unexports what pixi sets; every `cmake` in this Makefile is `$(CMAKE)`; `gvrun` ends in `exec "${GVRUN_PYTHON:-python3}"`. Checked by hand: no rebuild from pixi after a plain-shell build, the same ELF and stdout from both | todo |
| 2 | snax-forge `lower/c.py`: the marks out; each counter in `forge_counter[]`; `forge_check(t0)` prints `forge cycles:` then the self-check; forge/ refreshed; `make regress` | todo |
| 3 | snax-forge: the flow's stages after design are lower, gen, build, sw, gvsoc, check; `run.json` | todo |
| 4 | snax-forge CI: the `gvsoc` job, the flow on vecadd and vsum | todo |
| 5 | Acceptance in the container and in CI; tag `flow3-r1a` | todo |

## Findings
