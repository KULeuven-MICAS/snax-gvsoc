# SNAX-GVSoC

A detached copy of upstream [GVSoC](https://github.com/gvsoc/gvsoc) (at `93cedc4`) with the SNAX models added: SNAX-FORGE's model of the SNAX cluster, in which a Snitch core runs the real program. `UPSTREAM.md` lists the upstream commits, the license and every upstream file we changed. snax-forge holds the decisions (D-numbers here are snax-forge's `docs/DECISIONS.md`).

## The SNAX parts

- `snax/`: the C++ components (streamer, TCDM crossbar, `SnaxGroup`, `SnaxShell`, the datapath classes) and their Python configs, among them `snax_cfg.py`, the reader of a cluster's hjson; the `snax_hjson` target.
- `tests/snax/`: the testbenches (`unit/`, `group/`, `shell/`, `datapath/`, `sparse_arb/`), the Python unit tests (`test_*.py`) and the regression, `regress.py`.
- `sw/apps/`: our programs for the SNAX targets.
- `forge/`: one folder per snax-forge design point, the generator's output checked in as fixtures (D134). Never edited by hand: snax-forge writes them again (`forge/README.md`, the only hand-written file there).
- `docs/`: `RUN.md` (how to run it), `EVENTS.md` (what the SNAX components write about a run), `notes/NOTES.md` (the log).

## What is not ours

- `sw/` is a pinned copy of snax_cluster's software (D126 in snax-forge) but for our own files: `apps/`, `README.md`, `sync.py`, `Makefile` and `common.mk`. The copy (`COPIED` and `MATH` in `sync.py`) and `generated/` are refreshed only by `make sync-snax-cluster SNAX_CLUSTER=<checkout>`, whose diff is the check, and never edited by hand.
- Upstream GVSoC's code and docs (`core/`, `engine/`, `pulp/`, `gvrun/`, `DRAMSys.md`, ...) stay as they are. A change to an upstream file is the exception: it gets a `Modified for SNAX-GVSoC` line and a row in `UPSTREAM.md`, in the same commit.

## Commands

Everything runs in the image `ghcr.io/kuleuven-micas/snax-forge:main` (GVSoC's build tools, snax_cluster's toolchain), as CI does.

- `make build TARGETS='$(SNAX_TARGETS)'`: GVSoC for the SNAX targets (single quotes, so make expands the variable).
- `python3 -m unittest discover -s tests/snax -p 'test_*.py'`: the Python unit tests.
- `tests/snax/<name>/run.sh` for `unit`, `group`, `shell`, `datapath` and `sparse_arb`: each testbench against its cases, g++ only.
- `make regress` (`K=SUBSTRING` for some programs): builds `sw/` and the programs, then each must exit 0 on the built GVSoC.

## Conventions

- Markdown prose is one line per paragraph, list item and table row, never hard-wrapped; headings, code blocks, tables, display maths and HTML stay as they are (snax-forge D117, its `util/md_reflow.py --check`). Code comments and docstrings keep the formatter's line length.
- A commit message is one short line, with no co-author trailer. A pushed commit is never amended or force-pushed; a fix goes into the next commit.
- Pull requests are opened, never merged here; the maintainer merges.
