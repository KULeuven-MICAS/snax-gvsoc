# Running SNAX-GVSoC

The main path to a run of a generated design point is snax-forge's flow
(snax-forge D136): with this repo as its submodule, it generates the design
point, builds GVSoC when needed and the program, runs it on `snax_hjson`
and takes the program's own check. From snax-forge, in the container:

    pixi run flow recipes/vecadd.json --platform platforms/snax_forge.json

    ...
      gvsoc     snax_hjson, exit 0 -> run/
      check     passed: 226 cycles (main to forge_check); data 0 errors (64 words); counters add_acc 19 (16 beats)
      report    none in FLOW3 round 1a; the reports come back in FLOW3 round 1b

snax-forge's `docs/RUN.md` walks it. This file runs this repo by hand, from
a clone to a checked run: the container, the build, a program on a
hand-written target, a generated accelerator, what it prints, the
regression and the unit tests. Each block is the command as typed, then
what it printed in a fresh clone (long outputs cut to their last lines,
marked `...`). README.md says what each part is.

## 1. The container

The tools (GVSoC's build tools, snax_cluster's RISC-V toolchain) are in
snax-forge's image. From the folder that holds this repo, `$ROOT` below
(the outputs' absolute paths start there; yours will be your own):

    podman run --rm -it -v "$PWD":"$PWD" -w "$PWD" ghcr.io/kuleuven-micas/snax-forge:main
    cd snax-gvsoc

Every command below runs in that shell (the image's zsh), from
`snax-gvsoc/`. Build here, not in snax-forge's `pixi shell`, whose
environment sets `CC` and `CXX` to conda's gcc.

## 2. Build GVSoC and the software

GVSoC for the targets the programs run on, the Makefile's `SNAX_TARGETS`
(`snitch;snax_hjson`). The single quotes matter:
make expands `$(SNAX_TARGETS)`, the shell must not. The first build takes a
few minutes; a second one with nothing changed compiles nothing.

    make build TARGETS='$(SNAX_TARGETS)'

    ...
    -- Up-to-date: $ROOT/snax-gvsoc/install/python/./pyproject.toml
    -- Up-to-date: $ROOT/snax-gvsoc/install/python/./requirements.txt
    -- Up-to-date: $ROOT/snax-gvsoc/install/python/./.gitignore

`source sourceme.sh` puts the install's `gvrun` on `PATH`; every new
container needs it again. It prints nothing.

    source sourceme.sh

`make sw` builds snax_cluster's runtime, the math library and the 17 plain
tests from the copy in `sw/` into `build/sw/`:

    make sw

    ...
    1 warning generated.
    make[1]: Leaving directory '$ROOT/snax-gvsoc/sw'

## 3. A cluster test: snax-csr on snax_hjson

The cluster tests in `sw/apps/` (`snax-csr`, `dma-timing`, `stream-timing`,
`core-tcdm`, `dma-tcdm`) run on `snax_hjson` with `forge/vecadd/`'s cluster
file, whose streamer and shell they drive. `snax-csr` checks the compute
core's SNAX CSRs:

    make -C sw/apps/snax-csr

    ...
    llvm-objdump -D $ROOT/snax-gvsoc/build/sw/apps/snax-csr/snax-csr.elf > $ROOT/snax-gvsoc/build/sw/apps/snax-csr/snax-csr.dump
    make: Leaving directory '$ROOT/snax-gvsoc/sw/apps/snax-csr'

    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run

    csrw/csrr: 0 errors
    csrrw: 0 errors
    set/clear/imm: 0 errors
    read-only: 0 errors

    echo "exit $?"

    exit 0

## 4. A generated accelerator: forge/vecadd on snax_hjson

`forge/vecadd/` is a design point snax-forge generated (`forge/README.md`):
a cluster file, its streamer and datapath files, the headers, `main.c` and
`data.h`. The generic app builds its `main.c`:

    make -C sw/apps/forge DESIGN=vecadd

    ...
    llvm-objdump -D $ROOT/snax-gvsoc/build/sw/apps/forge/vecadd/forge.elf > $ROOT/snax-gvsoc/build/sw/apps/forge/vecadd/forge.dump
    make: Leaving directory '$ROOT/snax-gvsoc/sw/apps/forge'

`snax_hjson` reads the cluster file given with `--param hjson=` and puts the
standard composite (streamer, `SnaxShell`, `SnaxUnit`) in its accelerator
slot; `--trace=snax_acc0/unit` turns on the unit's traces (its debug
`trace`, and its `events` and `summary`, `docs/EVENTS.md`):

    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    forge cycles: 226
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    ...
    293200000: 2932: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] Start at cycle 2932: count 16
    293200000: 2932: [/chip/soc/cluster_0/snax_acc0/unit/events                                ] 2932 start count=16 rate=1
    295100000: 2951: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] run index=0 firings=16 busy=16 stall_in=3 stall_out=0 flush=0
    295100000: 2951: [/chip/soc/cluster_0/snax_acc0/unit/events                                ] 2951 done firings=16 first=2936 last=2951
    295100000: 2951: [/chip/soc/cluster_0/snax_acc0/unit/summary                               ] 2951 run index=0 firings=16 busy=16 stall_in=3 stall_out=0 flush=0

    echo "exit $?"

    exit 0

It exits 0. `make build` made `snax_hjson`'s platform tree from its default
file, `sw/cfg/snax_forge/snax_forge.hjson`, the cluster of `forge/vecadd/`,
so this run uses that tree. Another fixture's cluster file (`vecmul`,
`vsum`) puts another accelerator in the slot: gvrun then warns that the
installed platform tree does not match and builds the system from its JSON
configuration instead, on the same installed components. Nothing is
compiled for a design point.

## 5. Reading the output

- `forge cycles: 226`: the program's window, `mcycle` at `forge_check()`'s
  entry minus `mcycle` at main's entry (snax-forge D135), which snax-forge's
  flow takes as the run's total cycles.
- `forge data: 0 errors (64 words)`: every output word against its golden
  in `data.h` (the reference executor's result); 64 words is vecadd's `O`.
- `forge counter add_acc: 19`: the shell's cycle counter, read after the
  accelerator task `add_acc` finished.
- The unit's run line, `run index=0 firings=16 busy=16 stall_in=3
  stall_out=0 flush=0`: the counter is busy + stall_in + stall_out + flush (16 + 3 +
  0 + 0 = 19), and the firings are the task's beats in the manifest:

      grep '"tasks"' forge/vecadd/manifest.json

       "tasks": [{"name": "add_acc", "beats": 16, "csrs": {"loopCount": 16}}]

- `forge errors: 0`: the data errors plus one per counter below its beats;
  `main` returns it, so the run's exit code is 0.

The trace lines cut at `...` are the unit's ports being created and bound
at start-up; the last but one is its start (`Start at cycle 2932: count
16`).

### Beats, stalls and a VCD

The levels above `task` are more trace names (`docs/EVENTS.md`): `beats`
for every grant, DMA beat and burst, firing and push and every change of a
unit's or mover's cycle class (`class`), `stalls` for every refused request
and queue count, each a `--trace` regex into one file. The
crossbar writes them for its SNAX ports and the DMA unless `--param
chip/soc/cluster_0/tcdm/snax_xbar/trace_inputs=...` names others:

    mkdir -p build/work/forge-vecadd-stall
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd-stall \
        --trace="/beats\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --trace="/stalls\$:$PWD/build/work/forge-vecadd-stall/events.log" \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    forge cycles: 226
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0

The first firing names the beat it took from each reader, the first stall
the input that won its bank, the first queue count its cycle:

    grep -m1 ' fire ' build/work/forge-vecadd-stall/events.log | sed 's/.*\] //'
    grep -m1 ' stall in' build/work/forge-vecadd-stall/events.log | sed 's/.*\] //'
    grep -m1 ' fifo ' build/work/forge-vecadd-stall/events.log | sed 's/.*\] //'

    2936 fire n=0 b=0,0 value=0x2bd,0x111,0x16,0xfffffffffffffe33,0x2ee,0xfffffffffffffd26,0x9d,0x1ba
    2933 stall in=4 addr=0x200 bank=0 row=2 by=0 by_addr=0x0 b=0
    2935 fifo mover=reader0 lane=0 count=1

`--vcd --event-tags=snax` dumps the SNAX components' signals (busy, firings,
queue counts, the crossbar's handshakes; `docs/EVENTS.md`) for gtkwave, into
a work directory that exists:

    mkdir -p build/work/forge-vecadd-vcd
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --work-dir build/work/forge-vecadd-vcd --vcd --event-tags=snax \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    ...
    A Gtkwave script has been generated and can be opened with the following command:
    gtkwave build/work/forge-vecadd-vcd/view.gtkw

snax-forge's flow does both from `--trace LEVEL[:SOURCES]` and `--vcd`
(its `docs/RUN.md`).

## 6. The regression

`make regress` runs `SnaxUnit`'s and `SnaxShell`'s rules on their cases, builds `sw/` and every
program, and runs them all: the cluster tests, snax-shell and every
`forge/` folder on `snax_hjson`
(their counters checked as in section 5), and the plain tests on `snitch`.
About two minutes:

    make regress

    python3 tests/snax/regress.py 
    SnaxUnit's rule (tests/snax/unit)
      1 run
    SnaxShell's rule (tests/snax/shell)
      1 run
    cluster tests on snax_hjson, forge/vecadd/'s cluster file
      13 run
    snax-shell on snax_hjson, forge/vecadd/'s cluster file
      1 run
    forge/'s accelerators: forge.matadd, forge.rowsum, forge.rowsum_serial, forge.vecadd, forge.vecmul, forge.vsum, forge.vsum_tree
      7 run
    plain tests on snitch (build/sw/tests)
      17 run
    regression passed

Each run's output is in `build/regress/work/<name>/run.log`, beside its
`gvsoc_config.json`, and a forge/ run's traces in `trace.log` beside it
(GVSoC buffers its stdout, so the program's output there can cut a trace
line in two); a failure prints the file it read and its last 20 lines. `K=` runs only the programs whose name holds it (`make regress -k`
does not: make reads `-k` itself):

    make regress K=forge

    python3 tests/snax/regress.py -k forge
    SnaxUnit's rule (tests/snax/unit)
      0 run
    SnaxShell's rule (tests/snax/shell)
      0 run
    cluster tests on snax_hjson, forge/vecadd/'s cluster file
      0 run
    snax-shell on snax_hjson, forge/vecadd/'s cluster file
      0 run
    forge/'s accelerators: forge.matadd, forge.rowsum, forge.rowsum_serial, forge.vecadd, forge.vecmul, forge.vsum, forge.vsum_tree
      7 run
    plain tests on snitch (build/sw/tests)
      0 run
    regression passed

    ls build/regress/work/forge.vecadd

    gvsoc_config.json
    gvsoc_runtime_config.txt
    run.log
    trace.log
    trace_file.txt

## 7. The unit tests

`snax_cfg.py`'s reader, the class lines, and the composite's
CSR check (`snax_unit_acc.py`, which imports GVSoC from `install/`, so after
`make build`; skipped without it), with the image's Python:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

    ............................................
    ----------------------------------------------------------------------
    Ran 44 tests in 0.305s

    OK

`SnaxUnit`'s cycle rule against its hand-worked cases, with g++ (the
regression's `unit`):

    tests/snax/unit/run.sh

    PASS ops: 16 vectors
    PASS tree: 8 vectors
    PASS lockstep_count_zero: 6 cycles, 1 run(s)
    PASS lockstep_input_missing: 8 cycles, 1 run(s)
    PASS lockstep_no_stalls: 9 cycles, 2 run(s)
    PASS lockstep_out_not_ready: 9 cycles, 1 run(s)
    PASS pipelined_ii2: 10 cycles, 1 run(s)
    PASS pipelined_l0(lockstep_no_stalls): 9 cycles, 2 run(s)
    PASS pipelined_l0(lockstep_input_missing): 8 cycles, 1 run(s)
    PASS pipelined_l0(lockstep_out_not_ready): 9 cycles, 1 run(s)
    PASS pipelined_l0(lockstep_count_zero): 6 cycles, 1 run(s)
    PASS pipelined_l2_backpressure: 12 cycles, 1 run(s)
    PASS pipelined_rate_backpressure: 15 cycles, 1 run(s)
    PASS pipelined_rate_count_zero: 9 cycles, 1 run(s)
    PASS pipelined_rate_one: 7 cycles, 1 run(s)
    PASS pipelined_rate_t4: 17 cycles, 2 run(s)
    PASS pipelined_rate_zero: 7 cycles, 1 run(s)
    PASS pipelined_tree_t4: 18 cycles, 2 run(s)
    PASS pipelined_tree_tn: 13 cycles, 1 run(s)
    19 passed, 0 failed

`SnaxShell`'s rule (`snax/snax_shell.hpp`) stepped with the unit's against
its hand-worked cases, with g++ (the regression's `shell`,
`tests/snax/shell/README.md`):

    tests/snax/shell/run.sh

    PASS counter_after_start: 14 cycles
    PASS counter: 14 cycles
    PASS count_zero: 9 cycles
    PASS field_read_back: 4 cycles
    PASS read_busy: 8 cycles
    PASS start_bit0_clear: 7 cycles
    PASS start_held: 11 cycles
    PASS start_in_last_cycle: 8 cycles
    8 passed, 0 failed
