# CI1 plan: the programs build here, then CI

CI1 is a task of M16 in snax-forge, after SG6 and the housekeeping pass.
snax-gvsoc builds its programs from a pinned copy of snax_cluster's software
in `sw/`, so building or running them needs no snax_cluster checkout; a
GitHub workflow then builds GVSoC for `snitch;snax_alu` and runs
`make regress` on every push to main and on every pull request, in
snax-forge's image (D124, D126 in snax-forge). Acceptance below.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- In rounds, on the MICAS server: Claude Code runs the commands in
  snax-forge's image (`ghcr.io/kuleuven-micas/snax-forge:main`), started
  from the folder that holds this repo, as `README.md` says; git runs on the
  host. One commit per step on the branch `ry/ci1`, here and in snax-forge;
  pushes and pull requests are done by hand.
- Anything not verified is said so.

## The two rounds

1. Round 1, the copy: `sw/` holds the files of snax_cluster a build reads
   (runtime, math library, plain tests, the snax-alu app and library, the
   two cluster configurations), the headers generated from them, and the
   programs of `tests/snax/` moved to `sw/apps/`. `make sw` builds the
   runtime per cluster, the math library and the 17 plain tests;
   `make regress` builds the apps and runs everything.
   `make sync-snax-cluster SNAX_CLUSTER=<path>` refreshes the copy from a
   checkout and reports what moved.
2. Round 2, the workflow: on push to main and on pull requests, in the
   image, GVSoC built for `snitch;snax_alu`, then `make regress`. Only
   `snax/`, `sw/` and `tests/snax/` are built and tested; GVSoC's other
   components stay out. Planned when round 1 is merged.

## Round 1

- Step 0: on main, before any change, the reference ELFs built the old way
  (`make regress-plain`, then every program: `snax-alu` at `DATA_LEN` 4,
  100, 128, 1024, 4096 and without, `snax-stream`, `alu-timing`, the five
  `stream-timing` cases, `dma-timing`, `snax-csr`): 32 ELFs, 17 plain and
  15 SNAX, kept outside the repos. This plan.
- Step 1: `sw/` with the copied files (snax_cluster's `sw/` and
  `target/snitch_cluster/sw/` merged, so every relative include still
  works; no copied file edited), the generated headers made with
  upstream's own rules, `sw/sync.py` and `make sync-snax-cluster`,
  `sw/README.md` (pin, path map, licences, generated files, provenance).
  Check: sync at the pin, then sync again; `git status` shows no change.
- Step 2: `sw/Makefile` (`make sw`) and `sw/common.mk`; the programs moved
  from `tests/snax/` to `sw/apps/`, their output in `build/sw/`; the top
  Makefile loses `SNAX_CLUSTER` and `regress-plain`; `regress.py` builds
  with `make -C sw` first and fails on missing plain ELFs. Checks: every
  ELF of step 0, stripped, equals its new build; `make regress` passes (14
  SNAX runs, 17 plain); `test_phases.py` passes.
- Step 3: the READMEs and the notes. Check: a clone of the branch with no
  snax_cluster beside it builds GVSoC and passes `make regress`; only
  `sync-snax-cluster` names a snax_cluster path in the Makefiles.
- Step 4: snax-forge's docs: D126, CI1's row, M16's intro, open item 68,
  Next Up.

## Acceptance

- A fresh clone with no snax_cluster beside it passes `make regress`
  (round 1, step 3).
- Every ELF built from `sw/`, stripped with `llvm-objcopy --strip-all`,
  equals the one built from snax_cluster at the pin (round 1, step 2).
- A pull request that breaks a program fails the check (round 2).

## Steps

| # | Step | Status |
|---|---|---|
| 0 | Reference ELFs from main; this plan | |
| 1 | `sw/`: the copy, the generated headers, `sync.py`, `sw/README.md` | |
| 2 | `make sw`, the apps in `sw/apps/`, `regress.py` | |
| 3 | READMEs, notes; the standalone check | |
| 4 | snax-forge's docs (D126, CI1, open item 68) | |
| 5 | Round 2: the workflow | |
