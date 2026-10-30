# snax-gvsoc

SNAX-GVSoC is a GVSoC model of the SNAX cluster ([snax_cluster](https://github.com/KULeuven-MICAS/snax_cluster)) in which a Snitch core runs the real program. It is [SNAX-FORGE](https://github.com/KULeuven-MICAS/snax-forge)'s model (D116 there), checked against snax_cluster's RTL by one ELF on both (D123).

It is a detached copy of [GVSoC](https://github.com/gvsoc/gvsoc) at `93cedc4`; `UPSTREAM.md` lists the upstream commits, the license and every upstream file we changed. GVSoC's own documentation: [gvsoc.readthedocs.io](https://gvsoc.readthedocs.io/en/latest/) and [gvsoc-developer.readthedocs.io](https://gvsoc-developer.readthedocs.io/en/latest/).

## Layout

| Path | What |
|---|---|
| `core/`, `engine/`, `pulp/`, `gvrun/`, ... | GVSoC, folded in from its submodules |
| `snax/` | The `snax_hjson` target (any SNAX cluster read from its hjson, `snax_hjson.py`) and the SNAX components: the streamer, the TCDM crossbar, `SnaxGroup` (a group's datapaths under one control rule, `snax_group.hpp`) and `SnaxShell` (its CSRs) |
| `forge/` | snax-forge's generated accelerators, one design point per folder, checked in as fixtures (`forge/README.md`) |
| `sw/` | snax_cluster's software, a pinned copy (`sw/README.md`), and our programs in `sw/apps/`, each with a README |
| `tests/snax/` | The regression (`regress.py`), the testbenches (`unit/`, `shell/`, `datapath/`, `group/`, `sparse_arb/`) and the Python unit tests |
| `docs/` | `RUN.md` (how to run it), `EVENTS.md` (what the SNAX components write about a run), `notes/NOTES.md` (what was measured, and what holds) |

## Getting started

Everything runs in snax-forge's image `ghcr.io/kuleuven-micas/snax-forge:main` (GVSoC's build tools, snax_cluster's RISC-V toolchain), with this repository mounted at its own path; `CLAUDE.md` lists the commands, and `docs/RUN.md` walks through them with the lines to check: the build, a program on `snax_hjson`, a `forge/` fixture, the regression and the unit tests.

CI (`.github/workflows/ci.yml`, in the same image) builds GVSoC for the SNAX targets, runs the unit tests and `make regress` on every pull request and push to main.

## Comparing with the RTL

The regression checks that each program finishes; cycles are compared with snax_cluster's RTL by hand (D123). snax-forge's local check runs its bundles on the RTL and compares each with its SNAX-GVSoC run (snax-forge's `docs/RUN.md`, section 8); `docs/notes/NOTES.md` has what was measured.

## License

Apache 2.0, see `LICENSE` and `UPSTREAM.md`.
