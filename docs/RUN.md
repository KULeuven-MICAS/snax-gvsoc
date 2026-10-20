# Running SNAX-GVSoC

From a clone to a checked run: the container, the build, a program on a
hand-written target, a generated accelerator, what it prints, the
regression and the unit tests. Each block is the command as typed, then
what it printed in a fresh clone (long outputs cut to their last lines,
marked `...`). README.md says what each part is.

## 1. The container

The tools (GVSoC's build tools, snax_cluster's RISC-V toolchain) are in
snax-forge's image. From the folder that holds this repo:

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
    -- Up-to-date: /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/install/python/./pyproject.toml
    -- Up-to-date: /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/install/python/./requirements.txt
    -- Up-to-date: /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/install/python/./.gitignore

`source sourceme.sh` puts the install's `gvrun` on `PATH`; every new
container needs it again. It prints nothing.

    source sourceme.sh

`make sw` builds snax_cluster's runtime, the math library and the 17 plain
tests from the copy in `sw/` into `build/sw/`:

    make sw

    ...
    1 warning generated.
    make[1]: Leaving directory '/users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/sw'

## 3. A program on a hand-written target: snax-alu on snax_alu

`snax-alu` is snax_cluster's own app, built into
`build/sw/apps/snax-alu/100/` (`DATA_LEN` 100):

    make -C sw/apps/snax-alu

    ...
    llvm-objdump -D /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/build/sw/apps/snax-alu/100/snax-alu.elf > /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/build/sw/apps/snax-alu/100/snax-alu.dump
    make: Leaving directory '/users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/sw/apps/snax-alu'

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
    llvm-objdump -D /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/build/sw/apps/forge/vecadd/forge.elf > /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/build/sw/apps/forge/vecadd/forge.dump
    make: Leaving directory '/users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/sw/apps/forge'

`snax_hjson` reads the cluster file given with `--param hjson=` and puts the
standard composite (streamer, `SnaxShell`, `SnaxUnit`) in its accelerator
slot; `--trace=snax_acc0/unit` turns on the unit's trace:

    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson \
        --work-dir build/work/forge-vecadd --trace=snax_acc0/unit \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecadd/forge.elf run

    Warning: installed platform tree /users/micas/rantonio/no_backup/kul_main/_rundoc/snax-gvsoc/install/lib/libplatform_tree_snax_hjson.so does not match the live system tree, falling back to the JSON config path (rebuild the target to regenerate the tree).
    forge data: 0 errors (64 words)
    forge counter add_acc: 19
    forge errors: 0
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] New slave port (name: clock, port: 0x555e9a869f18)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] New slave port (name: reset, port: 0x555e9a869d20)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New slave port (name: power_supply, port: 0x555e9a869dc8)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New slave port (name: voltage, port: 0x555e9a869e70)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New master port (name: a, port: 0x555e9a86d920)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New master port (name: b, port: 0x555e9a86d9f8)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New master port (name: out, port: 0x555e9a86a258)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New slave port (name: ctrl, port: 0x555e9a86a0a0)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] New master port (name: busy, port: 0x555e9a86a158)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] add, 4 lanes of 64 bits, lockstep, latency 0, ii 1
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Creating final bindings
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Creating final binding (/chip/soc/cluster_0/snax_acc0/unit:busy -> /chip/soc/cluster_0/snax_acc0/shell:busy)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Creating final binding (/chip/soc/cluster_0/snax_acc0/unit:out -> /chip/soc/cluster_0/snax_acc0/streamer:writer_0)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Creating final binding (/chip/soc/cluster_0/snax_acc0/unit:b -> /chip/soc/cluster_0/snax_acc0/streamer:reader_1)
    0: -1: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Creating final binding (/chip/soc/cluster_0/snax_acc0/unit:a -> /chip/soc/cluster_0/snax_acc0/streamer:reader_0)
    0: 0: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Reset (active: 1)
    0: 0: [/chip/soc/cluster_0/snax_acc0/unit/comp                                  ] Reset (active: 0)
    292200000: 2922: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] Start at cycle 2922: count 16
    294100000: 2941: [/chip/soc/cluster_0/snax_acc0/unit/trace                                 ] run 0: firings 16 busy 16 stall_in 3 stall_out 0 flush 0

    echo "exit $?"

    exit 0

It exits 0. The first line is expected: `make build` made `snax_hjson`'s
platform tree from its default file (`sw/cfg/snax_alu_cluster.hjson`, with
snax_cluster's ALU in the slot). This file puts another accelerator there,
so the tree does not match and gvrun builds the system from its JSON
configuration instead, on the same installed components. Nothing is
compiled for a design point.

## 5. Reading the output

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

The other trace lines are the unit's ports being created and bound at
start-up, and its start (`Start at cycle 2922: count 16`).

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
