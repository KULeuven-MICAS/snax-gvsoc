# Running SNAX-GVSoC

The main path to a run of a generated design point is snax-forge's flow
(snax-forge D136): with this repo as its submodule, it generates the design
point, builds GVSoC when needed and the program, runs it on `snax_hjson`
and takes the program's own check. From snax-forge, in the container:

    pixi run flow recipes/vecadd.json --platform platforms/snax_alu.json

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
(`snitch;snax_alu;snax_alu_sparse;snax_hjson`). The single quotes matter:
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

## 3. A program on a hand-written target: snax-alu on snax_alu

`snax-alu` is snax_cluster's own app, built into
`build/sw/apps/snax-alu/100/` (`DATA_LEN` 100):

    make -C sw/apps/snax-alu

    ...
    llvm-objdump -D $ROOT/snax-gvsoc/build/sw/apps/snax-alu/100/snax-alu.elf > $ROOT/snax-gvsoc/build/sw/apps/snax-alu/100/snax-alu.dump
    make: Leaving directory '$ROOT/snax-gvsoc/sw/apps/snax-alu'

    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-alu/100/snax-alu.elf run

    Accelerator Done! 
    Accelerator Cycles: 25 
    Number of errors: 0 

    echo "exit $?"

    exit 0

These are the RTL's three lines; the run exits 0.

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
slot; `--trace=snax_acc0/unit` turns on the unit's trace:

    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    Warning: installed platform tree $ROOT/snax-gvsoc/install/lib/libplatform_tree_snax_hjson.so does not match the live system tree, falling back to the JSON config path (rebuild the target to regenerate the tree).
    forge cycles: 226
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    ...
    293200000: 2932: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] Start at cycle 2932: count 16
    295100000: 2951: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] run 0: firings 16 busy 16 stall_in 3 stall_out 0 flush 0

    echo "exit $?"

    exit 0

It exits 0. The first line is expected: `make build` made `snax_hjson`'s
platform tree from its default file (`sw/cfg/snax_alu_cluster.hjson`, with
snax_cluster's ALU in the slot). This file puts another accelerator there,
so the tree does not match and gvrun builds the system from its JSON
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
- The unit's run line, `run 0: firings 16 busy 16 stall_in 3 stall_out 0
  flush 0`: the counter is busy + stall_in + stall_out + flush (16 + 3 +
  0 + 0 = 19), and the firings are the task's beats in the manifest:

      grep '"tasks"' forge/vecadd/manifest.json

       "tasks": [{"name": "add_acc", "beats": 16, "csrs": {"loopCount": 16}}]

- `forge errors: 0`: the data errors plus one per counter below its beats;
  `main` returns it, so the run's exit code is 0.

The trace lines cut at `...` are the unit's ports being created and bound
at start-up; the last but one is its start (`Start at cycle 2932: count
16`).

## 6. The regression

`make regress` runs `SnaxUnit`'s rule on its cases, builds `sw/` and every
program, and runs them all: the SNAX programs on `snax_alu` and
`snax_alu_sparse`, snax-shell and every `forge/` folder on `snax_hjson`
(their counters checked as in section 5), and the plain tests on `snitch`.
About two minutes:

    make regress

    python3 tests/snax/regress.py 
    SnaxUnit's rule (tests/snax/unit)
      1 run
    SNAX programs on snax_alu, snax_alu_sparse
      40 run
    snax-shell on snax_hjson, forge/vecadd/'s cluster file
      1 run
    forge/'s accelerators: forge.vecadd, forge.vecmul, forge.vsum, forge.vsum_tree, forge-reduce.vsum-r16
      5 run
    plain tests on snitch (build/sw/tests)
      17 run
    regression passed

Each run's output is in `build/regress/work/<name>/run.log`, beside its
`gvsoc_config.json`; a failure prints that path and the log's last 20
lines. `K=` runs only the programs whose name holds it (`make regress -k`
does not: make reads `-k` itself):

    make regress K=forge

    python3 tests/snax/regress.py -k forge
    SnaxUnit's rule (tests/snax/unit)
      0 run
    SNAX programs on snax_alu, snax_alu_sparse
      0 run
    snax-shell on snax_hjson, forge/vecadd/'s cluster file
      0 run
    forge/'s accelerators: forge.vecadd, forge.vecmul, forge.vsum, forge.vsum_tree, forge-reduce.vsum-r16
      5 run
    plain tests on snitch (build/sw/tests)
      0 run
    regression passed

    ls build/regress/work/forge.vecadd

    gvsoc_config.json
    gvsoc_runtime_config.txt
    run.log
    trace_file.txt

## 7. The unit tests

`snax_cfg.py`'s reader and `phases.py`, with the image's Python:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

    ...................................
    ----------------------------------------------------------------------
    Ran 35 tests in 0.149s

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
