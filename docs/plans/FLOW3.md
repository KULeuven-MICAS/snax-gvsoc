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
| 1 | Tools: snax-forge's `gvsoc/Makefile` names Python, CMake and the host compilers and unexports what pixi sets; every `cmake` in this Makefile is `$(CMAKE)`; `gvrun` ends in `exec "${GVRUN_PYTHON:-python3}"`. Checked by hand: no rebuild from pixi after a plain-shell build, the same ELF and stdout from both | done |
| 2 | snax-forge `lower/c.py`: the marks out; each counter in `forge_counter[]`; `forge_check(t0)` prints `forge cycles:` then the self-check; forge/ refreshed; `make regress` | done |
| 3 | snax-forge: the flow's stages after design are lower, gen, build, sw, gvsoc, check; `run.json` | done |
| 4 | snax-forge CI: the `gvsoc` job, the flow on vecadd and vsum | todo |
| 5 | Acceptance in the container and in CI; tag `flow3-r1a` | todo |

## Findings

- **What pixi's environment changes (step 1).** `env` under `pixi run`
  against the image's plain shell: pixi puts its env's `bin/` first on
  `PATH` (its `python3`, `make` 4.4.1, `ninja`, and conda's binutils as
  plain `ld`, `as`, `ar`), and adds conda's compiler setup: `CC`, `CXX`,
  `CPP`, `GCC`, `GXX`, the `*_FOR_BUILD` compilers, `CFLAGS`, `CXXFLAGS`,
  `CPPFLAGS`, `LDFLAGS`, `LDFLAGS_LD`, the `DEBUG_*` flags, `AR`, `AS`,
  `LD`, `NM`, `RANLIB`, `STRIP`, `OBJCOPY`, `OBJDUMP`, `READELF` and the
  other binutils names, `CONDA_BUILD_SYSROOT`, `HOST`, `BUILD` and their
  aliases, `MESON_ARGS`; CMake-relevant, `CMAKE_ARGS` and
  `CMAKE_PREFIX_PATH` (pixi's env first). It also sets `CONDA_PREFIX`,
  `PIXI_*`, `JAVA_HOME`, `DACE_default_build_folder`, `SNAX_FORGE_HW_OUT`,
  `OMP_NUM_THREADS=1` and `GSETTINGS_SCHEMA_DIR`, which no build reads.
  `PYTHONPATH` and `LD_LIBRARY_PATH` are untouched. The host gcc finds `ld`
  and `as` through `PATH` (`gcc -print-prog-name=ld` is `ld`), so
  snax-forge's `gvsoc/Makefile` puts the host compilers' folder
  (`/usr/bin/`) right after the image's Python on its recipes' `PATH`, and
  unexports the compiler setup above; `CC` and `CXX` are its own unless
  given on make's command line.
- **The three checks hold (step 1).** With `out/snax-gvsoc/` wiped, `make
  -C gvsoc build` in the plain shell (this branch's checkout as
  `SNAX_GVSOC`), then `pixi run make -C gvsoc build`: the three
  `CMakeCache.txt` (GVSoC, gvrun, config_tree) byte-identical before and
  after, no object or library newer than before it, none of the build's
  `Building` or `Linking` lines; the cache names `/usr/bin/gcc`, `g++`,
  `ar` and `ld`. `make sw APPS=forge` on snax-forge's generated vecadd,
  with `build/sw/` and snax-forge's `out/snax-gvsoc/sw/` wiped before each:
  ELF sha256 `4fe8f544...4d28dd` from both. `make run` on `snax_hjson`:
  byte-identical stdout (`forge data: 0 errors (64 words)`, `forge counter
  add_acc: 19`, `forge errors: 0`), exit 0 from both.
- **The window and the counters without marks (step 2).** forge/ refreshed
  from snax-forge's generator (only the four `main.c` changed); full `make
  regress` on a fresh build passes (64 runs). The windows: vecadd 226,
  vecmul 226, vsum 255, vsum_tree 207 cycles; the counters are the marked
  programs' (19, 19, 67, 19). `forge-reduce` is hand-written and never used
  the marks: unchanged. With one accelerator task, clang keeps the static
  `forge_counter[1]` as one symbol, `forge_counter.0`.
- **The flow on SNAX-GVSoC (step 3).** `pixi run flow` on vecadd and vsum
  (`platforms/snax_alu.json`) gives the fixtures' windows and counters
  (226 and 19, 255 and 67), exit 0; its first run built GVSoC (the build's
  folder came from another checkout), the next ones found it up to date
  (about 3 s a flow). The build, `make sw` and `make run` leave this repo's
  tree clean (`git status --porcelain` empty), so a flow does not see its
  own build as a dirty tree.
- **The program's exit code is not its error count (step 3).** A vecadd
  program with two goldens changed by hand prints `forge errors: 2` and the
  run exits 1 (`make: *** [Makefile:110: run] Error 1`), so the flow reads
  the counts from the printed lines and only pass or fail from the exit.
