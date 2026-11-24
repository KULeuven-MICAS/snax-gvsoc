# SNAX-GVSoC commands

The commands for running this repository by hand, with the lines to check. The usual path is snax-forge's flow (`pixi run flow recipes/elementwise/vecadd_v1.json --platform platforms/snax_forge.json`), which generates, builds, runs and checks a design point.

## Setup

Everything runs in snax-forge's image from `snax-gvsoc/`, not in snax-forge's `pixi shell` (its `CC` and `CXX` are conda's gcc). From the folder holding this repository:

    podman run --rm -it -v "$PWD":"$PWD" -w "$PWD" ghcr.io/kuleuven-micas/snax-forge:main
    cd snax-gvsoc

## Build

    make build TARGETS='$(SNAX_TARGETS)'
    source sourceme.sh
    make sw

- `make build`: GVSoC for `snitch` and `snax_hjson` into `install/`; the single quotes let make expand `$(SNAX_TARGETS)`. `FAST=1` skips the asserts flavour, which only `gvrun --asserts` uses: about 15 % less build time.
- `source sourceme.sh` puts the install's `gvrun` on `PATH`, in every new shell.
- `make sw` builds snax_cluster's runtime, math library and 17 plain tests from `sw/` into `build/sw/`.

## Run a cluster test

`make -C sw/apps/<app>` builds one of our programs (`snax-csr`, `obs-csr`, `snax-shell`, `stream-timing`, `dma-timing`, `core-tcdm`, `dma-tcdm`, `forge`) into `build/sw/apps/<app>/`. They run on `snax_hjson` with `forge/vecadd_v1/`'s cluster file, roles by core index (the accelerator's core 0, the DMA's the last); each README has what it checks and its lines:

    make -C sw/apps/snax-csr
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd_v1/snax_forge.hjson \
        --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run

It prints four lines ending in `: 0 errors` and exits 0.

## Run a generated design point

The `forge` app builds a `forge/<design>/` folder's `main.c` (`forge/README.md`); `snax_hjson` puts the accelerator of the cluster file `--param hjson=` names in its slot.

    make -C sw/apps/forge DESIGN=vecadd_v1
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd_v1/snax_forge.hjson \
        --work-dir build/work/forge-vecadd_v1 --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd_v1/forge.elf run

    forge cycles: 214
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    ...  unit/summary  ] 2962 run index=0 firings=16 busy=16 stall_in=3 stall_out=0 flush=0

It exits 0. The cycle numbers move with the program or the model; the errors must stay 0.

- `forge cycles`: the window between the program's two `mcycle` reads, the flow's cycles.
- `forge data`: every output word against its golden value in `data.h`.
- `forge counter add_acc`: the group's BUSY_COUNTER, the run line's busy + stall_in + stall_out + flush (16 + 3 + 0 + 0 = 19).
- `forge errors`: the data errors plus one per counter below its beats; `main` returns it.
- A trace line on stdout can cut a program's line: trace to a file. Fixtures other than `vecadd_v1/` warn that the platform tree does not match, as expected.

## Traces and a VCD

The trace levels are trace names (`docs/EVENTS.md`), each a `--trace` pattern, here into one file:

    mkdir -p build/work/forge-vecadd_v1-stall
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd_v1/snax_forge.hjson \
        --work-dir build/work/forge-vecadd_v1-stall \
        --trace="/beats\$:$PWD/build/work/forge-vecadd_v1-stall/events.log" \
        --trace="/stalls\$:$PWD/build/work/forge-vecadd_v1-stall/events.log" \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd_v1/forge.elf run

- The crossbar writes lines for the SNAX ports and the DMA unless `--param chip/soc/cluster_0/tcdm/snax_xbar/trace_inputs=...` names others.
- `--vcd --event-tags=snax` writes the SNAX signals for gtkwave (`build/work/<name>/view.gtkw`); the work directory must exist.
- snax-forge's flow does both from its `--trace LEVEL[:SOURCES]` and `--vcd`.

## The regression

    make regress K=forge

It runs the six g++ testbenches, builds `sw/` and the programs, runs the cluster tests, `snax-shell`, every `forge/` folder and its quiet build on `snax_hjson` (counters, classes and snapshots checked, `docs/EVENTS.md`'s Snapshots) and the plain tests on `snitch`, as `tests/snax/regress.py` says. It ends with `regression passed`.

- `K=SUBSTRING` runs only the programs whose name holds it (`-k` does not: make reads it); `J=N` runs N at a time (default the CPU count).
- Each run's output is in `build/regress/work/<name>/run.log`, its traces in `trace.log` beside it; a failure prints the file it read and its last 20 lines.

## Unit tests and testbenches

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

It ends with `OK`; 12 tests import GVSoC and are skipped until `make build` has run.

    tests/snax/unit/run.sh

Each testbench (`unit`, `group`, `shell`, `datapath`, `sparse_pick`, `port_mux`) needs g++ only, runs against the cases its README lists into `build/<name>/` and ends with `N passed, 0 failed` (`sparse_pick` and `port_mux` with `OK`). `sparse_arb` checks the sparse arbiter against the RTL module, by hand with Verilator (its README).

## Refreshing `sw/`

    make sync-snax-cluster SNAX_CLUSTER=<checkout>

It refreshes `sw/`'s copy of snax_cluster; the diff is the check.
