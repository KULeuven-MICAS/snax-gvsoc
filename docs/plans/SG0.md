# SG0 plan: the repository, the images and the probe

SG0 is the first task of M16 in snax-forge (SNAX-GVSoC aligned with
snax_cluster, D116). Acceptance: the probe result and the chosen GVSoC commit
are logged, and both images build and run on the MICAS server.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply`; commits and pushes
  are done by hand.
- Anything not verified is said so.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | Detached copy of GVSoC `93cedc4`, submodules folded in, pushed | done 2026-10-12 |
| 2 | P1: `UPSTREAM.md`, short README, upstream CI and CODEOWNERS removed, container imported from the experiment, this plan and the notes | done 2026-10-12 |
| 3 | Image `snax-gvsoc:sg0` built from `container/` and run on micaseb19: GVSoC builds, the bundled ELF runs | todo |
| 4 | P2: snax_cluster's toolchain in the image (clang, lld, llvm-tools 21.1.6, bender 0.28); rv64 GCC and Snitch LLVM 12 dropped | todo |
| 5 | Probe: snax_cluster `8ebd4229` tests built with its own flow (`cfg/snitch_cluster.hjson`, generic LLVM, `rtl-generic`) and run on `gvrun --target snitch` | todo |
| 6 | P3, if the probe fails on CSRs 0xBC1 to 0xBC3: the Snitch core patch; probe run again, commit chosen | todo |
| 7 | P4: snax-forge's image FROM `snax-gvsoc:sg0`, pixi last | todo |
| 8 | P5: SG0 closed here, and the STATUS.md update for snax-forge | todo |

## Decided

- Probe result: not yet.
- Chosen GVSoC commit: not yet.
