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
2. Round 2, the workflow: on push to main, on pull requests and by hand,
   in the image, GVSoC built for `snitch;snax_alu`, then `make regress`. Only
   `snax/`, `sw/` and `tests/snax/` are built and tested; GVSoC's other
   components stay out; the unit tests of `tests/snax/` run with
   `python3 -m unittest discover -s tests/snax -p 'test_*.py'`, which needs
   nothing beyond the image. It lands in the same pull request as round 1
   and its fix-up.

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
  SNAX runs, 17 plain); `python3 -m unittest discover -s tests/snax -p
  'test_*.py'` passes in the image.
- Step 3: the READMEs and the notes. Check: a clone of the branch with no
  snax_cluster beside it builds GVSoC and passes `make regress`; only
  `sync-snax-cluster` names a snax_cluster path in the Makefiles.
- Step 4: snax-forge's docs: D126, CI1's row, M16's intro, open item 68,
  Next Up.
- Fix-up after review: one list of plain tests (`COPIED` in `sw/sync.py`;
  `sw/Makefile` and `regress.py` take the names from `sw/tests/*.c`); a
  dependency file beside each app's ELF, so an edited header relinks the
  programs that include it; the unit tests run with `unittest`. Checks:
  every ELF equals the one built before the fix, byte for byte; a touched
  header relinks only the programs that include it; `make regress` and the
  unit tests pass.

## Round 2

- Step 1: `.github/workflows/ci.yml`, one job `regress` in the image:
  checkout, the ccache environment, ccache restored, `make build
  TARGETS="snitch;snax_alu"`, the unit tests, `make regress`, the
  `run.log` files as the `regress-logs` artifact on failure, ccache saved
  after every run with a build. `regress.py` prints an `::error`
  annotation per failed program under Actions. Checks, in the image: the
  YAML parses; the commands of the workflow pass from the repository root
  with its environment, ccache filled in `.ccache`; with `snax-csr` made to
  fail, `regress.py` prints the annotation and exits 1.
- Step 2: the README's "Continuous integration", the notes, and
  snax-forge's docs (D124, CI1 done, SG7's row).
- Step 3: the failure check: a commit that makes `snax-csr` return one
  more than its error count, then its revert, pushed one at a time after
  the rest: green, then red on `snax-csr` with its annotation and the
  `regress-logs` artifact, then green. The runs are linked in the notes.
  As run: the break commit and its revert went in one push, so the red run
  is a throwaway pull request at the break commit.
- Step 4: from the runs' notices, the actions on Node 24
  (`actions/checkout@v7`, `actions/cache/restore@v6` and `save@v6`,
  `actions/upload-artifact@v7`, inputs unchanged) and the runner pinned to
  `ubuntu-24.04`; the GitHub runs in the notes. Check: the YAML parses.

## Acceptance

- A fresh clone with no snax_cluster beside it passes `make regress`
  (round 1, step 3).
- Every ELF built from `sw/`, stripped with `llvm-objcopy --strip-all`,
  equals the one built from snax_cluster at the pin (round 1, step 2).
- A pull request that breaks a program fails the check (round 2).

## Steps

| # | Step | Status |
|---|---|---|
| 0 | Reference ELFs from main; this plan | done 2026-10-15 |
| 1 | `sw/`: the copy, the generated headers, `sync.py`, `sw/README.md` | done 2026-10-15 |
| 2 | `make sw`, the apps in `sw/apps/`, `regress.py` | done 2026-10-15 |
| 3 | READMEs, notes; the standalone check | done 2026-10-15 |
| 4 | snax-forge's docs (D126, CI1, open item 68) | done 2026-10-15 (snax-forge `ry/ci1`) |
| 4a | Fix-up after review: one list of plain tests, header dependencies, `unittest` | done 2026-10-15 |
| 5 | Round 2: the workflow, `::error` lines in `regress.py`; local checks | done 2026-10-15 |
| 6 | Round 2: docs here and in snax-forge (D124, CI1 done, SG7) | done 2026-10-15 |
| 7 | Round 2: the failure check, red then green on GitHub | done 2026-10-15 |
| 8 | Round 2: the GitHub runs linked in the notes | done 2026-10-15 |
| 9 | Round 2: actions on Node 24, runner pinned to `ubuntu-24.04` | done 2026-10-15 |
