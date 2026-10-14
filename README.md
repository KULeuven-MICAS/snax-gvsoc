# snax-gvsoc

SNAX-GVSoC is a GVSoC model of the SNAX cluster
([snax_cluster](https://github.com/KULeuven-MICAS/snax_cluster)) in which a
Snitch core runs the real program. It is part of
[SNAX-FORGE](https://github.com/KULeuven-MICAS/snax-forge) (M16).

It starts as a detached copy of [GVSoC](https://github.com/gvsoc/gvsoc) at
`93cedc4`. `UPSTREAM.md` lists the upstream commits, the license and every
file we changed. This file replaces GVSoC's README; GVSoC's own documentation
is at [gvsoc.readthedocs.io](https://gvsoc.readthedocs.io/en/latest/) and
[gvsoc-developer.readthedocs.io](https://gvsoc-developer.readthedocs.io/en/latest/).

## Layout

| Path | What |
|---|---|
| `core/`, `engine/`, `pulp/`, `gvrun/`, ... | GVSoC, folded in from its submodules |
| `snax/` | SNAX targets and components: the `snax_alu` target, the CSR stub |
| `tests/snax/` | Programs for the SNAX targets, built against snax_cluster's runtime |
| `docs/plans/` | One checklist per task (`SG0.md`, `SG1.md`) |
| `docs/notes/NOTES.md` | The log: what was run and what came out |
| `build/`, `install/` | GVSoC's build and run output, and what it installs; not tracked |

## Quick start

The tools come from SNAX-FORGE's development image
`ghcr.io/kuleuven-micas/snax-forge:main` (D118 in snax-forge): GVSoC's build
tools and Python packages, snax_cluster's RISC-V toolchain (clang 21.1.6,
bender 0.28.2), pixi and zsh. It is built from snax-forge's `container/`; its
README says how. The image holds tools only: this repo is mounted at its own
path and GVSoC is built there.

Run it from the folder that holds this repo (and `snax-forge`,
`snax_cluster` next to it), then go into this one:

    podman run --rm -it -v "$PWD":"$PWD" -w "$PWD" ghcr.io/kuleuven-micas/snax-forge:main
    cd snax-gvsoc

Build GVSoC in the plain container shell, not in snax-forge's `pixi shell`,
whose environment sets `CC` and `CXX` to conda's gcc. Build it for the Snitch
target (a few minutes the first time) and run the bundled program, which
exits with 0 and prints nothing:

    make build TARGETS=snitch
    source sourceme.sh
    gvrun --target snitch --work-dir build/work/snitch \
        --param chip/soc/binary=$PWD/pulp/examples/snitch/fp32_computation_vector.elf run

Every new container needs `source sourceme.sh` again. Adding
`--trace=pe0/insn` before `run` prints core 0's instructions: 484 lines, from
cycle 7909 to 23862.

## Running snax_cluster's tests

Programs are built with snax_cluster's own flow, in a snax_cluster checkout
beside this repo; only the ELF files are run here. Clone it next to this
repo, at the commit in `docs/notes/NOTES.md`, with its submodules:

    git clone https://github.com/KULeuven-MICAS/snax_cluster.git ../snax_cluster
    git -C ../snax_cluster checkout d7dd78967b86dae5c7d149f420dd69681714dac9
    git -C ../snax_cluster submodule update --init --recursive

In the container, started from the parent folder as above, build
snax_cluster's plain tests (the first build needs internet: bender fetches a
dependency) and run them all; each prints `exit 0`, and `printf_simple`
prints `Hello, World!` once per core:

    make -C ../snax_cluster/target/snitch_cluster sw CFG_OVERRIDE=cfg/snitch_cluster.hjson
    source sourceme.sh
    mkdir -p build/work
    T=../snax_cluster/target/snitch_cluster/sw/tests/build
    for e in $T/*.elf; do
      n=$(basename $e .elf)
      gvrun --target snitch --work-dir build/work/$n --param chip/soc/binary=$PWD/$e run > build/work/$n.log 2>&1
      echo "$n exit $?"
    done
    cat build/work/printf_simple.log

## The snax_alu target

`snax_alu` is snax_cluster's `cfg/snax_alu_cluster_old.hjson`: a compute
core and a DMA core, the compute core's accelerator (`snax/snax_alu_acc.py`)
with its streamer and the ALU, its TCDM ports through a crossbar into the
banks. Build snax_cluster's runtime for that cluster (this also rebuilds its
plain tests for 2 cores), then GVSoC and the programs in `tests/snax/`:

    make -C ../snax_cluster/target/snitch_cluster sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson
    make build TARGETS="snitch;snax_alu"
    make -C tests/snax/snax-csr
    make -C tests/snax/snax-alu
    source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/tests/snax/snax-csr/build/snax-csr.elf run
    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/tests/snax/snax-alu/build/snax-alu.elf run

`snax-csr` prints four lines of `0 errors` and exits 0. `snax-alu` prints
`Accelerator Done!`, `Accelerator Cycles: 25` and `Number of errors: 0` and
exits 0, as on the RTL. Adding `--trace=snax_acc0` before `run` prints every
CSR access the streamer and the ALU get. Each program in `tests/snax/` has a
README with its own expected output.

## Regression

`make regress` builds the programs of `tests/snax/`, runs each on
`snax_alu` and compares its output exactly with its `expected/` folder:
`snax-alu` at five sizes (printed lines, the streamer's counter, the phase
table), `snax-stream`, `alu-timing`, the five `stream-timing` cases,
`dma-timing` and `snax-csr`. It also checks `snax-alu` against the RTL run in
`tests/snax/snax-alu/rtl/` with SG5's error target (`docs/plans/SG5.md`). It
needs GVSoC built for `snitch;snax_alu` and snax_cluster's runtime built for
the ALU cluster, as above, and takes about a minute.

snax_cluster's 17 plain tests run on `snitch` too once their ELFs are in
`build/regress/plain/`. `make regress-plain` puts them there: it builds them
for snax_cluster's 9-core cluster and then rebuilds the runtime for the ALU
cluster (run it again after moving the snax_cluster pin).

    make regress-plain
    make regress

It ends with `regression passed` and exit 0, or lists each check that
failed and exits 1. When a change is meant to move the numbers,
`make regress REGRESS_FLAGS=--update` rewrites the `expected/` files (never
`rtl/`); add a notes entry saying why. The expected files come from the
development image, so a regression run elsewhere (another LLVM build) can
differ by a few cycles.

## License

Apache 2.0, see `LICENSE` and `UPSTREAM.md`.
