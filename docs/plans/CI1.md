# CI1 plan: the programs build here, then CI

CI1 is a task of M16 in snax-forge, after SG6 and the housekeeping pass.
snax-gvsoc builds its programs from a pinned copy of snax_cluster's software
in `sw/`, so building or running them needs no snax_cluster checkout; a
GitHub workflow then builds GVSoC for `snitch;snax_alu` (now the Makefile's
`SNAX_TARGETS`, `snitch;snax_hjson`) and runs `make regress` on every push
to main and on every pull request, in snax-forge's image (D124, D126 in
snax-forge). Closed 2026-10-15; the log, with the GitHub runs, is
`docs/notes/NOTES.md` (CI1 round 1, fix-up after review, round 2).

## Acceptance

- A fresh clone with no snax_cluster beside it passes `make regress`
  (round 1, step 3).
- Every ELF built from `sw/`, stripped with `llvm-objcopy --strip-all`,
  equals the one built from snax_cluster at the pin (round 1, step 2).
- A pull request that breaks a program fails the check (round 2).

All three met.

## Steps

All done 2026-10-15.

- 0: Reference ELFs from main, built the old way: 32 ELFs, 17 plain and 15
  SNAX, kept outside the repos; this plan.
- 1: `sw/`: snax_cluster's `sw/` and `target/snitch_cluster/sw/` merged, so
  every relative include still works, no copied file edited; the generated
  headers made with upstream's own rules; `sw/sync.py` and
  `make sync-snax-cluster SNAX_CLUSTER=<path>`; `sw/README.md`. A sync at
  the pin, then again, leaves `git status` clean.
- 2: `make sw` (`sw/Makefile`, `sw/common.mk`); the programs moved to
  `sw/apps/`, their output in `build/sw/`; the top Makefile loses
  `SNAX_CLUSTER` and `regress-plain`. Every ELF of step 0, stripped, equals
  its new build; `make regress` passes (14 SNAX runs, 17 plain).
- 3 and 4: READMEs and notes, the standalone check on a fresh clone;
  snax-forge's docs (D126, CI1, open item 68).
- 4a: Fix-up after review: one list of plain tests (`COPIED` in
  `sw/sync.py`), a dependency file beside each app's ELF, the unit tests
  run with `python3 -m unittest discover -s tests/snax -p 'test_*.py'`.
  Every ELF equals the one built before the fix, byte for byte.
- 5 and 6: Round 2: `.github/workflows/ci.yml`, one job `regress` in the
  image: ccache restored, `make build`, the unit tests, `make regress`, the
  `run.log` files as the `regress-logs` artifact on failure, ccache saved;
  `regress.py` prints an `::error` annotation per failed program. Docs here
  and in snax-forge (D124, CI1 done, SG7).
- 7 and 8: The failure check on GitHub: green, then red on `snax-csr` with
  its annotation and the `regress-logs` artifact (a throwaway pull request
  at the break commit, since the break and its revert went in one push),
  then green; the runs linked in the notes.
- 9: The actions on Node 24 (`actions/checkout@v7`,
  `actions/cache/restore@v6` and `save@v6`, `actions/upload-artifact@v7`)
  and the runner pinned to `ubuntu-24.04`.
