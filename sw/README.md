# sw

The software snax-gvsoc's programs are built from: a pinned copy of the
files of [snax_cluster](https://github.com/KULeuven-MICAS/snax_cluster)
a build reads (the Snitch runtime, the math library, the 17 plain tests,
the `snax-alu` app and library, two cluster configurations), the headers
generated from them, and our own programs in `apps/` (CI1, D126 in
snax-forge). No snax_cluster checkout is needed to build or run them; one
is needed only for the RTL and to refresh this copy.

No copied file is edited. The list of copied files is `COPIED` and `MATH`
in `sync.py`, and nowhere else.

## Building

`make sw` at the top (`make -C sw`, `Makefile` here) builds into
`build/sw/`: `libmath.a`; per cluster, `<cluster>/libsnRuntime.a`, and for
`snax_alu_cluster_old` `snax-alu-lib.o`; every plain test in `tests/`
(the 17 of `COPIED`) for `snitch_cluster` into `tests/`; the regression
runs the same set. Flags come from `toolchain.mk`, include
order and link flags from upstream's Makefiles (`MIRRORED` in `sync.py`).
Each program in `apps/` has a Makefile of its own on `common.mk` and builds
into `build/sw/apps/<name>/`, building the libraries first when needed:
`make -C sw/apps/<name>`.

## Pin

| What | Commit | |
|---|---|---|
| `snax_cluster` | `9fbf35de566cbfed6fd1b5d6bf51903fa5ce33d1` | 2026-10-14, Update SNAX CSR so to comply with Zicsr (#657) |
| `sw/deps/printf` | `d3b984684bb8a8bdc48cc7a1abecb93ce59bbe3e` | 2020-01-01, chore(readme): 2020 announcement |
| `sw/deps/riscv-opcodes` | `94caf0e0fefff1009ba144bccb6d8f7d425ea2f5` | 2023-10-03, Add custom HW barrier CSR (#9) |

`sync.py` writes these rows; the two submodules are snax_cluster's.

## Path map

snax_cluster's `sw/` and `target/snitch_cluster/sw/` are merged here, so
every relative include in the copied files (`../../deps/...`,
`../../rtl/src/...`) still works.

| snax_cluster | Here |
|---|---|
| `sw/X` | `sw/X` |
| `target/snitch_cluster/sw/X` | `sw/X` |
| `target/snitch_cluster/cfg/X` | `sw/cfg/X` |
| `util/sim/X` | `sw/util/X` |
| `LICENSE` | `sw/LICENSE` |

## Licences

- snax_cluster: Apache 2.0, `LICENSE` here; each file keeps its header.
- `math/`: musl, MIT, `math/COPYRIGHT` (snax_cluster's changes Apache 2.0,
  `math/README`).
- `deps/printf/`: MIT, `deps/printf/LICENSE`.
- `deps/riscv-opcodes/`: the Regents of the University of California's
  BSD-style licence, `deps/riscv-opcodes/LICENSE`.
- What we add (`sync.py`, the Makefiles, `apps/`, this file): Apache 2.0,
  the repository's `LICENSE`.

## Generated files

Checked in, so a build needs no generator. `sync.py` makes them with
upstream's own rules, in the checkout:

| File | Made by |
|---|---|
| `generated/<cluster>/snitch_cluster_cfg.h`, `snitch_cluster_addrmap.h` | `make -C target/snitch_cluster CFG_OVERRIDE=cfg/<cluster>.hjson` (clustergen and the `.h.tpl` templates), for `snitch_cluster` and `snax_alu_cluster_old` |
| `runtime/common/snitch_cluster_peripheral.h` | the same `make` (regtool from `snitch_cluster_peripheral_reg.hjson`, then clang-format); the same for both clusters, which `sync.py` checks |
| `math/include/bits/alltypes.h` | `sed -f math/tools/mkalltypes.sed` on the two `alltypes.h.in`, the rule of snax_cluster's `sw/math/Makefile` |
| `generated/snax_alu_cluster_old/streamer_csr_addr_map.h` | by hand: a copy of what the Chisel streamer writes in `rtl-gen` for `snax_alu_cluster_old.hjson` (`target/snitch_cluster/sw/snax/snax-alu/include/`); `sync.py` never writes it and only compares it with the checkout's when there is one |

## Sync and review

In snax-forge's image, from this repository, with a checkout at the new
commit, its submodules initialised and no tracked change in what sync reads
(`CHECKED` in `sync.py`):

    make sync-snax-cluster SNAX_CLUSTER=../snax_cluster

It removes the copied files and copies them again (a file deleted upstream
disappears), regenerates the generated files, writes the new pin above,
and reports:

- `git diff --stat` of `sw/` and its new files: what the new pin changes
  here;
- the checkout's `git diff --stat old..new` on the upstream build files our
  Makefiles mirror (`MIRRORED` in `sync.py`): when one moved, check
  `Makefile`, `common.mk` and `apps/*/Makefile` against it;
- whether the checkout's `streamer_csr_addr_map.h` equals ours.

A file a build now needs and the list lacks shows as a build error; add it
to `COPIED` and sync again. Then build and run the regression
(`README.md`, "Regression"), and commit `sw/` with the pin.

## Provenance of snax-alu

The `snax-alu` app is snax_cluster's, at the pin (the app as at `d7dd789`,
`b2672f8` with the DMA core waiting for its transfers before the barrier,
SG5 P2), cluster `cfg/snax_alu_cluster_old.hjson`.

| File | From snax_cluster |
|---|---|
| `apps/snax-alu/src/snax-alu.c` | `target/snitch_cluster/sw/apps/snax-alu/src/`, unchanged |
| `apps/snax-alu/data/datagen.py` | `target/snitch_cluster/sw/apps/snax-alu/data/`, unchanged |
| `snax/snax-alu/src/snax-alu-lib.c` | `target/snitch_cluster/sw/snax/snax-alu/src/`, unchanged |
| `snax/snax-alu/include/snax-alu-lib.h` | `target/snitch_cluster/sw/snax/snax-alu/include/`, unchanged |
| `generated/snax_alu_cluster_old/streamer_csr_addr_map.h` | written by the Chisel streamer in `rtl-gen` for that cluster |
