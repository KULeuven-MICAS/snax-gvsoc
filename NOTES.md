# SNAX-GVSoC notes

Working notes for the SNAX-GVSoC exploration (X1, D115 in snax-forge).
One entry per step: what was run, what came out, what was learned.

## Pins

| What | Commit | Date |
|---|---|---|
| `gvsoc/gvsoc` (submodule `gvsoc/`) | `93cedc4cb2970a28ff38aef4393d8d69eae503a4` | 2026-09-25 |
| `pulp-platform/snitch_cluster` (submodule `snitch_cluster/`) | `4652c6b05886757c5cbe3dfe77c196dcd71e08e7` | 2024-08-02 |

Toolchains, all prebuilt downloads (see `container/Dockerfile`):

| Tool | Version | Used for |
|---|---|---|
| RISC-V GCC | 14.2.0, riscv-gnu-toolchain release 2025.01.17 | GVSoC tutorial programs (rv64) |
| Snitch LLVM | 0.12.0 (clang 12.0.1), pulp-platform/llvm-project | snitch_cluster runtime and programs (rv32) |
| Bender | 0.27.1 | snitch_cluster header generation |

### Why this snitch_cluster commit

- GVSoC's `make snitch_cluster` clones a `gvsoc-ci` branch that no longer
  exists in pulp-platform/snitch_cluster, so there is no official pin.
- GVSoC's cluster peripheral register file
  (`pulp/pulp/snitch/snitch_cluster/snitch_cluster_peripheral_reg.hjson`) is
  byte-identical to snitch_cluster from `a5af779` (2023-09-15) up to, not
  including, `96e34a2` (2024-08-09). `4652c6b` is the last commit in that range.
- snitch_cluster `c7eb9c2` (2025-01-28, native bootrom) moves the peripherals
  up by 0x1000 and `CL_CLINT_SET` from 0x180 to 0x1a0. Programs built from
  that commit or later fail on GVSoC with
  `Accessing invalid register (offset: 0x11a0 ...)`. Reproduced with `c4861da`.

## Layout

```
snax-gvsoc/
  gvsoc/            submodule, pinned
  snitch_cluster/   submodule, pinned
  container/        Dockerfile and requirements.txt
  snax/             module root for the SNAX components (added when needed)
  tutorials/        working copies of the GVSoC tutorials (added in GVS1)
  sw/               C programs (GVS3)
  build/            GVSoC build, install and run output; not tracked
  NOTES.md
```

SNAX models stay outside the GVSoC tree. GVSoC picks up an external module
root with `make build MODULES=/abs/path` and finds its generators with
`gvrun --target-dir`.

## Container

- Image: `ghcr.io/kuleuven-micas/snax-gvsoc:gvs1`, built from `container/`.
- It holds compilers, Python packages and toolchains only. The repo is
  mounted at `/work`; `GVSOC_WORKDIR=/work/build` sends all GVSoC output to
  `build/`.

Build and push (local machine, Docker):

    docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:gvs1 container
    docker push ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

Run (MICAS server, Podman), from the repo root:

    podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

## Commands already tried

Run inside the container on a 2-core machine, from a clean image and a clean
repo, before step 1 was handed over. They are the starting point for GVS1
steps 2 to 4; times are for 2 cores.

Build GVSoC for the `snitch` target (8 min 21 s, first build):

    make -C gvsoc build TARGETS=snitch
    source gvsoc/sourceme.sh

Run the bundled program (exit code 0, prints nothing):

    gvrun --target snitch --work-dir build/work/snitch \
        --param chip/soc/binary=$PWD/gvsoc/pulp/examples/snitch/fp32_computation_vector.elf run

Build the snitch_cluster tests (47 ELFs, 4 s). `APPS=` skips the
applications, whose data generators need numpy and torch, which are not in
the image:

    cd snitch_cluster/target/snitch_cluster
    make DEBUG=ON APPS= tests

Run one (`printf_simple` prints `Hello, World!` nine times, exit code 0):

    gvrun --target snitch --work-dir /work/build/work/printf_simple \
        --param chip/soc/binary=$PWD/sw/tests/build/printf_simple.elf run

Tutorial 0 from a copy outside the GVSoC tree (build 2 min, prints `Hello`):

    mkdir -p tutorials && cd tutorials
    T=/work/gvsoc/engine/docs/developer_manual/tutorials
    cp -r $T/utils $T/0_how_to_build_a_system_from_scratch .
    cd 0_how_to_build_a_system_from_scratch
    export GVSOC_ROOT=/work/gvsoc
    make prepare gvsoc all run

The tutorial build shares `build/` with the `snitch` build; the `snitch`
target still ran afterwards.

Differences from the GVSoC website docs: the tutorials are in
`gvsoc/engine/docs/developer_manual/tutorials`, the launcher is `gvrun` with
`--parameter binary=<elf>`, and tutorials 13 and 18 have no directory.

## Log

### GVS1 step 1: repo and container

(fill in: date, machine, image digest, output of the version check)

## Findings for later tasks

### GVS2

- The GVSoC Snitch model matches snitch_cluster as of August 2024.
- The `perf_cnt` test runs but every counter reads 0.
- The `snitch` target has a `soc/nb_cluster` parameter.
- Changing the L1 bank count (16, 32, 64) left the `dma_simple` cycle count
  unchanged at 23460. One core and a plain DMA copy, so this does not yet
  say whether bank contention is modelled.
- GVSoC's docs say `pulp.snitch.snitch_cluster_single` and the default slow
  core are to be deprecated in favour of `snitch:core_type=fast`.

### GVS3

- Editing one C++ model and rebuilding takes 5 to 20 s; a run of a small
  test takes 1 to 3 s (2 cores).
- The bank count is hard-coded in the stock generator. For sweeps, our own
  target should expose such values as `gvrun` parameters so that a design
  point needs no rebuild. Not tried yet.