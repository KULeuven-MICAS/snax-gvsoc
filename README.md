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
| `container/` | The development image; `toolchain/` pins its RISC-V toolchain |
| `docs/plans/` | One checklist per task (`SG0.md`) |
| `docs/notes/NOTES.md` | The log: what was run and what came out |
| `build/` | Build, install and run output; not tracked |

## Quick start

The image holds the tools only: GVSoC's build tools and Python packages,
snax_cluster's RISC-V toolchain (clang 21.1.6, bender 0.28.2) and zsh. This
repo is mounted at `/work` and GVSoC is built there. Build the image and push
it (Docker):

    docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:main container
    docker push ghcr.io/kuleuven-micas/snax-gvsoc:main

Run it from the repo root (Podman); it opens zsh in `/work`:

    podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:main

Inside, build GVSoC for the Snitch target (about 9 minutes on 2 cores the
first time) and run the bundled program, which exits with 0 and prints
nothing:

    make build TARGETS=snitch
    source sourceme.sh
    gvrun --target snitch --work-dir build/work/snitch \
        --param chip/soc/binary=$PWD/pulp/examples/snitch/fp32_computation_vector.elf run

Every new container needs `source sourceme.sh` again. Adding
`--trace=pe0/insn` before `run` prints core 0's instructions: 484 lines, from
cycle 7909 to 23862.

## License

Apache 2.0, see `LICENSE` and `UPSTREAM.md`.
