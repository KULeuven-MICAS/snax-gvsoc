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
| `docs/plans/` | One checklist per task (`SG0.md`) |
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
    git -C ../snax_cluster checkout 8ebd42299c1db2ab26006f68f76896097b64b278
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

## License

Apache 2.0, see `LICENSE` and `UPSTREAM.md`.
