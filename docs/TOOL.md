# SNAX-GVSoC commands

This file lists the commands for running this repository by hand, each with the lines to check. The usual path is snax-forge's flow instead: with this repository as its submodule, `pixi run flow recipes/elementwise/vecadd.json --platform platforms/snax_forge.json` generates a design point, builds GVSoC and the program, runs it on `snax_hjson` and checks it.

## Setup

Everything runs in snax-forge's image. From the folder that holds this repository:

    podman run --rm -it -v "$PWD":"$PWD" -w "$PWD" ghcr.io/kuleuven-micas/snax-forge:main
    cd snax-gvsoc

- Run the commands below in that shell, from `snax-gvsoc/`.
- Not in snax-forge's `pixi shell`: it sets `CC` and `CXX` to conda's gcc.

## Commands at a glance

| Command | What it does | Output |
|---|---|---|
| `make build TARGETS='$(SNAX_TARGETS)'` | builds GVSoC for `snitch` and `snax_hjson` | `install/` |
| `source sourceme.sh` | puts the install's `gvrun` on `PATH` (every new shell) | — |
| `make sw` | builds snax_cluster's runtime, math library and 17 plain tests from `sw/` | `build/sw/` |
| `make -C sw/apps/<app>` | builds one of our programs | `build/sw/apps/<app>/` |
| `gvrun --target snax_hjson ... run` | runs a program on a cluster file | `build/work/<name>/` |
| `make regress` | testbenches, every program, every `forge/` fixture | `build/regress/` |
| `python3 -m unittest discover -s tests/snax -p 'test_*.py'` | the Python unit tests | — |
| `tests/snax/<name>/run.sh` | one testbench against its cases | `build/<name>/` |
| `make sync-snax-cluster SNAX_CLUSTER=<checkout>` | refreshes `sw/`'s copy of snax_cluster | the diff is the check |

## Build

    make build TARGETS='$(SNAX_TARGETS)'
    source sourceme.sh
    make sw

- The single quotes matter: make expands `$(SNAX_TARGETS)` (`snitch;snax_hjson`) itself.
- A first build takes a few minutes; a second one with nothing changed compiles nothing.
- `FAST=1` skips the models' asserts flavour, which only `gvrun --asserts` uses: about 15 % less build time.

## Run a cluster test

The programs in `sw/apps/` run on `snax_hjson` with `forge/vecadd/`'s cluster file. It has one core, which drives both the accelerator and the DMA; each test takes its roles by core index (the accelerator's core 0, the DMA's the last), so it also runs on a cluster of more cores.

| App | What it checks |
|---|---|
| `snax-csr` | core 0's SNAX CSRs: every R/W CSR reads back what was written by each kind of CSR instruction; the R/O ones read 0 and the forms that do not write leave them alone |
| `obs-csr` | each core's observability CSR `0x7C5` against snax_cluster's `CsrObsRegister` |
| `snax-shell` | `SnaxShell` and a one-unit `SnaxGroup`, driven by hand with the DMA and the streamer |
| `stream-timing` | the streamer's timing alone: its busy CSR and counter |
| `dma-timing` | the DMA's busy, read and write cycles against the RTL's |
| `core-tcdm` | core 0's TCDM accesses (sub-word, AMO, LR/SC) and its loads against the streamer's readers |
| `dma-tcdm` | the DMA against the streamer on the same banks |
| `forge` | the generic app for a `forge/` design point (next section) |

Each app's README has its own lines. For example, `snax-csr`:

    make -C sw/apps/snax-csr
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run

    csrw/csrr: 0 errors
    csrrw: 0 errors
    set/clear/imm: 0 errors
    read-only: 0 errors

It exits 0.

## Run a generated design point

`forge/<design>/` is a design point snax-forge generated (`forge/README.md`). The `forge` app builds its `main.c`; `snax_hjson` puts the accelerator of the cluster file given by `--param hjson=` in its slot.

    make -C sw/apps/forge DESIGN=vecadd
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    forge cycles: 214
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    ...  unit/summary  ] 2962 run index=0 firings=16 busy=16 stall_in=3 stall_out=0 flush=0

It exits 0. What the lines mean:

- `forge cycles`: the program's window, between its two `mcycle` reads; snax-forge's flow takes it as the run's cycles.
- `forge data`: every output word against its golden value in `data.h`.
- `forge counter add_acc`: the group's BUSY_COUNTER after the task. It equals the run line's busy + stall_in + stall_out + flush (16 + 3 + 0 + 0 = 19).
- `forge errors`: the data errors plus one per counter below its beats; `main` returns it.

Things to know:

- GVSoC buffers its stdout, so a trace line can cut a program's line in two; trace to a file to keep them apart.
- `vecadd/` runs on the build's platform tree (it is `snax_hjson`'s default file). Another fixture runs on its JSON config, with gvrun's warning that the platform tree does not match; that warning is expected.
- The cycle numbers above change with any change to the program or the model; the errors must stay 0.

## Traces and a VCD

The trace levels are trace names (`docs/EVENTS.md`), each a `--trace` pattern, here into one file:

    mkdir -p build/work/forge-vecadd-stall
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd-stall \
        --trace="/beats\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --trace="/stalls\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run
    grep -m1 ' fire ' build/work/forge-vecadd-stall/events.log | sed 's/.*\] //'

    2947 fire n=0 b=0,0 value=0x2bd,0x111,0x16,0xfffffffffffffe33,0x2ee,0xfffffffffffffd26,0x9d,0x1ba

- The crossbar writes lines for the SNAX ports and the DMA, unless `--param chip/soc/cluster_0/tcdm/snax_xbar/trace_inputs=...` names others.
- `--vcd --event-tags=snax` writes the SNAX components' signals for gtkwave (`build/work/<name>/view.gtkw`); the work directory must exist.
- snax-forge's flow does both from its `--trace LEVEL[:SOURCES]` and `--vcd`.

## The regression

`make regress` runs the six g++ testbenches, builds `sw/` and every program, then runs the cluster tests, `snax-shell` and every `forge/` folder on `snax_hjson` (their counters checked against their units' run lines) and the plain tests on `snitch`. `tests/snax/regress.py` says what each checks. It ends:

    forge/'s accelerators: forge.dot_1, forge.dot_2, ...
      29 run
    plain tests on snitch (build/sw/tests)
      17 run
    regression passed

- `K=SUBSTRING` runs only the programs whose name holds it (`make regress K=forge`). `make regress -k` does not: make reads `-k` itself.
- `J=N` runs N programs at a time (default the CPU count; `J=1` one after another).
- Each run's output is in `build/regress/work/<name>/run.log`, a `forge/` run's traces in `trace.log` beside it. A failure prints the file it read and its last 20 lines.

## Unit tests and testbenches

The Python unit tests cover `snax_cfg.py`'s reader, the class lines, the group rule's Python twin and the composite's CSR check:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

- 12 of them import GVSoC and are skipped until `make build` has run.
- It ends with `OK`.

The testbenches need g++ only; each runs against the cases in its folder (its README):

| Testbench | What it checks | How |
|---|---|---|
| `unit` | `SnaxGroupRule` with one unit, cycle by cycle | `tests/snax/unit/run.sh` |
| `group` | `SnaxGroupRule` over linked units (the dot variants) | `tests/snax/group/run.sh` |
| `shell` | `SnaxShell` with a one-unit group | `tests/snax/shell/run.sh` |
| `datapath` | every datapath class against its vectors | `tests/snax/datapath/run.sh` |
| `sparse_pick` | the crossbar's winner pick, 1 to 128 inputs | `tests/snax/sparse_pick/run.sh` |
| `port_mux` | `SnaxPortMuxRule` against hand-worked cases | `tests/snax/port_mux/run.sh` |
| `sparse_arb` | the sparse arbiter against the RTL module | by hand, with Verilator (its README) |

Each case-based testbench ends with `N passed, 0 failed`; `sparse_pick` and `port_mux` end with `OK`.
