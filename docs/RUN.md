# Running SNAX-GVSoC

The usual way to a run of a generated design point is snax-forge's flow (snax-forge D136, its `docs/RUN.md`): with this repository as its submodule, `pixi run flow recipes/vecadd.json --platform platforms/snax_forge.json` generates the design point, builds GVSoC and the program, runs it on `snax_hjson` and takes the program's check. This file runs this repository by hand: each command, then the lines to check.

## 1. The container

The tools are in snax-forge's image. From the folder that holds this repository:

    podman run --rm -it -v "$PWD":"$PWD" -w "$PWD" ghcr.io/kuleuven-micas/snax-forge:main
    cd snax-gvsoc

Every command below runs in that shell, from `snax-gvsoc/`, not in snax-forge's `pixi shell` (whose environment sets `CC` and `CXX` to conda's gcc).

## 2. Build GVSoC and the software

GVSoC for the Makefile's `SNAX_TARGETS` (`snitch;snax_hjson`); the single quotes matter, as make expands the variable. A first build takes a few minutes; a second one with nothing changed compiles nothing.

    make build TARGETS='$(SNAX_TARGETS)'

`FAST=1` skips the models' asserts flavour, which only `gvrun --asserts` uses: about 15% less build time. Then the install's `gvrun` on `PATH` (in every new shell), and snax_cluster's runtime, math library and 17 plain tests from the copy in `sw/` into `build/sw/`:

    source sourceme.sh
    make sw

## 3. A cluster test: snax-csr

The cluster tests in `sw/apps/` (`snax-csr`, `dma-timing`, `stream-timing`, `core-tcdm`, `dma-tcdm`) run on `snax_hjson` with `forge/vecadd/`'s cluster file. `snax-csr` checks the compute core's SNAX CSRs:

    make -C sw/apps/snax-csr
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run

    csrw/csrr: 0 errors
    csrrw: 0 errors
    set/clear/imm: 0 errors
    read-only: 0 errors

It exits 0. Each program's README has its own lines.

## 4. A generated accelerator: forge/vecadd

`forge/vecadd/` is a design point snax-forge generated (`forge/README.md`). The generic app builds its `main.c`; `snax_hjson` puts the accelerator of the cluster file given with `--param hjson=` in its slot; `--trace=snax_acc0/unit` turns on the unit's traces (`docs/EVENTS.md`):

    make -C sw/apps/forge DESIGN=vecadd
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    forge cycles: 214
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    ...  unit/summary  ] 2962 run index=0 firings=16 busy=16 stall_in=3 stall_out=0 flush=0

It exits 0. The lines:

- `forge cycles`: the program's window, between its two `mcycle` reads (snax-forge D135), which snax-forge's flow takes as the run's cycles;
- `forge data`: every output word against its golden in `data.h`;
- `forge counter add_acc`: the group's COUNTER after the task, which is the unit's run line's busy + stall_in + stall_out + flush (16 + 3 + 0 + 0), the firings the task's beats in `manifest.json`;
- `forge errors`: the data errors plus one per counter below its beats; `main` returns it.

GVSoC buffers its stdout, so a trace line can cut a program's line in two; trace to a file to keep them apart. `vecadd/` runs on the build's platform tree (it is `snax_hjson`'s default file); another fixture's cluster file runs on the JSON config, with gvrun's warning that the platform tree does not match. Nothing is compiled for a design point.

## 5. Beats, stalls and a VCD

The trace levels above `task` are more trace names (`docs/EVENTS.md`), each a `--trace` pattern into one file:

    mkdir -p build/work/forge-vecadd-stall
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd-stall \
        --trace="/beats\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --trace="/stalls\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run
    grep -m1 ' fire ' build/work/forge-vecadd-stall/events.log | sed 's/.*\] //'

    2947 fire n=0 b=0,0 value=0x2bd,0x111,0x16,0xfffffffffffffe33,0x2ee,0xfffffffffffffd26,0x9d,0x1ba

The crossbar writes its lines for the SNAX ports and the DMA unless `--param chip/soc/cluster_0/tcdm/snax_xbar/trace_inputs=...` names others. `--vcd --event-tags=snax` writes the SNAX components' signals for gtkwave (`build/work/<name>/view.gtkw`), into a work directory that exists. snax-forge's flow does both from `--trace LEVEL[:SOURCES]` and `--vcd`.

## 6. The regression

`make regress` runs the testbenches (`unit`, `shell`, `datapath`, `group`), builds `sw/` and every program, and runs the cluster tests, `snax-shell` and every `forge/` folder on `snax_hjson` (their counters checked against their units' run lines) and the plain tests on `snitch`; `tests/snax/regress.py` says what each checks. It ends:

    forge/'s accelerators: forge.dot_1, forge.dot_2, ...
      28 run
    plain tests on snitch (build/sw/tests)
      17 run
    regression passed

- `K=SUBSTRING` runs only the programs whose name holds it (`make regress K=forge`); `make regress -k` does not, as make reads `-k` itself.
- `J=N` runs N programs at a time (default the CPU count; `J=1` one after another).

Each run's output is in `build/regress/work/<name>/run.log`, a `forge/` run's traces in `trace.log` beside it; a failure prints the file it read and its last 20 lines.

## 7. The unit tests and the testbenches

`snax_cfg.py`'s reader, the class lines, the group rule's Python twin and the composite's CSR check, with the image's Python (after `make build`, which the composite's test imports GVSoC from):

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

    Ran 67 tests in 0.644s

    OK

The testbenches, with g++ only (the regression's `unit`, `shell`, `datapath` and `group`), each against its cases (its README):

    tests/snax/unit/run.sh

    12 passed, 0 failed

`tests/snax/shell/run.sh` gives `10 passed, 0 failed`; `datapath/run.sh` and `group/run.sh` likewise end with their counts. `tests/snax/sparse_arb/` is run by hand, with Verilator (its README).
