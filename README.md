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
| `snax/` | SNAX targets and components: the `snax_alu` and `snax_alu_sparse` targets, their streamer, ALU and TCDM crossbar; `SnaxUnit` (a generic Chisel block's datapath) and `SnaxShell` (its CSR manager); the `snax_hjson` target, any cluster read from its hjson |
| `forge/` | Generated accelerators from snax-forge, one design point per folder, checked in as fixtures (`forge/README.md`) |
| `sw/` | snax_cluster's software, a pinned copy (`sw/README.md`), and the programs for the SNAX targets in `sw/apps/` |
| `tests/snax/` | The regression (`regress.py`), the phase script (`phases.py`), the arbiters' checks against the RTL and `SnaxUnit`'s rule against hand-worked cases (`unit/`) |
| `docs/plans/` | One checklist per task (`SG0.md` to `SG7.md`, `CI1.md`, `GEN3.md`, `LNK2a.md`) |
| `docs/notes/NOTES.md` | The log: what was run and what came out |
| `build/`, `install/` | GVSoC's build and run output, the programs (`build/sw/`), and what GVSoC installs; not tracked |

## Quick start

The tools come from SNAX-FORGE's development image
`ghcr.io/kuleuven-micas/snax-forge:main` (D118 in snax-forge): GVSoC's build
tools and Python packages, snax_cluster's RISC-V toolchain (clang 21.1.6,
bender 0.28.2), pixi and zsh. It is built from snax-forge's `container/`; its
README says how. The image holds tools only: this repo is mounted at its own
path and GVSoC is built there.

Run it from the folder that holds this repo (and `snax-forge`, and
`snax_cluster` when the RTL is run, next to it), then go into this one:

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

snax_cluster's runtime and plain tests are built from the copy in `sw/`
("Where sw/ comes from"); no snax_cluster checkout is needed. In the
container, started from the parent folder as above, build them and run them
all; each prints `exit 0`, and `printf_simple` prints `Hello, World!` once
per core:

    make sw
    source sourceme.sh
    mkdir -p build/work
    for e in build/sw/tests/*.elf; do
      n=$(basename $e .elf)
      gvrun --target snitch --work-dir build/work/$n --param chip/soc/binary=$PWD/$e run > build/work/$n.log 2>&1
      echo "$n exit $?"
    done
    cat build/work/printf_simple.log

## The snax_alu targets

`snax_alu` is snax_cluster's `cfg/snax_alu_cluster_old.hjson`: a compute
core and a DMA core, the compute core's accelerator (`snax/snax_alu_acc.py`)
with its streamer and the ALU; its TCDM ports, the cores' and the narrow
AXI port's go through a crossbar into the banks, arbitrated as the plain
interconnect does. `snax_alu_sparse`
(`snax/snax_alu_sparse.py`) is `cfg/snax_alu_cluster.hjson`, the same
cluster with the sparse interconnect: the crossbar takes the streamer's
priority bit first, then round robin from the last pick (SG7,
`docs/plans/SG7.md`); the cores and AXI ask with priority 0. On both, a
DMA beat takes the whole superbank (8 banks) it writes or reads in its cycle,
and a narrow request there is refused and keeps its turn. The two clusters
build the same ELF (`sw/README.md`).
`snax_hjson` (`snax/snax_hjson.py`, LNK2a) is any such cluster read from
its hjson (`snax/snax_cfg.py`), the file given with `--param hjson=<path>`
(`sw/cfg/snax_alu_cluster.hjson` by default); on either `sw/cfg/` file it
gives the logs and `gvsoc_config.json` of the matching hand-written target.
Build `sw/` (the runtime for both clusters), GVSoC and the programs in
`sw/apps/`, each into `build/sw/apps/<name>/`:

    make sw
    make build TARGETS="snitch;snax_alu;snax_alu_sparse;snax_hjson"
    make -C sw/apps/snax-csr
    make -C sw/apps/snax-alu
    source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/snax-csr \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run
    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-alu/100/snax-alu.elf run

`snax-csr` prints four lines of `0 errors` and exits 0. `snax-alu` prints
`Accelerator Done!`, `Accelerator Cycles: 25` and `Number of errors: 0` and
exits 0, as on the RTL. Adding `--trace=snax_acc0` before `run` prints every
CSR access the streamer and the ALU get. Each program in `sw/apps/` has a
README with its own expected output. The same commands with
`--target snax_alu_sparse` run them on the sparse interconnect;
`--trace=snax_xbar` prints each bank's grants, marking with `!` a request
with priority 1.

## snax-shell

`sw/apps/snax-shell/` drives `SnaxShell` (GeMMX's shell contract: a start
waits while busy, busy and a cycle counter) and `SnaxUnit` (a lockstep add,
4 lanes of 64 bit) behind `snax_alu`'s streamer by hand. It runs on
`snax_hjson` with `forge/vecadd/snax_alu.hjson`, whose datapath block and
CSRs (`forge/vecadd/include/`) are that accelerator's:

    make -C sw/apps/snax-shell
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecadd/snax_alu.hjson --work-dir build/work/snax-shell \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-shell/snax-shell.elf run

It prints its checks and `snax-shell errors: 0`, and exits 0;
`--trace=snax_acc0/unit` adds the unit's line per run.

## Generated accelerators (forge/)

`forge/<design>/` holds one design point as SNAX-GVSoC reads it (LNK2a):
snax-forge's generator's three hjson files, the cluster file
`snax_alu.hjson` (`sw/cfg/snax_alu_cluster.hjson` with the accelerator slot
set for the design), the streamer file `snax_alu_streamer.hjson` (the slot's
streamer template) and the accelerator file `snax_alu_acc.hjson` (its
datapath block), the headers a program drives it with, the program itself,
`main.c` with its `data.h` (GEN2a), and `manifest.json` (`forge/README.md`).
No model is built: `snax_hjson` reads the cluster file and puts the
standard composite (`snax/snax_unit_acc.py`: the streamer, `SnaxShell` and
`SnaxUnit`) in the slot, on the installed components (gvrun warns that the
platform tree does not match). The generic app `sw/apps/forge/` builds the
fixture's `main.c`:

    make -C sw/apps/forge DESIGN=vecmul
    gvrun --target snax_hjson --param hjson=$PWD/forge/vecmul/snax_alu.hjson --work-dir build/work/forge-vecmul \
        --param chip/soc/binary=$PWD/build/sw/apps/forge/vecmul/forge.elf run

It prints `forge data: 0 errors (64 words)`, one `forge counter <task>:`
line per accelerator task and `forge errors: 0`, and exits 0.
`sw/apps/forge-reduce/` stays for `vsum` with its len overridden by hand
(`RATE_OVERRIDE=16`, four sums per run).

## Regression

`make regress` first runs `SnaxUnit`'s rule on its cases (`unit`,
`tests/snax/unit/README.md`), then builds `sw/` and the programs of `sw/apps/`, runs each ELF
on `snax_alu` and on `snax_alu_sparse`, named `<program>.<target>`:
`snax-alu` at five sizes, `snax-stream`, `alu-timing`, the `stream-timing`
cases, `dma-timing`, `snax-csr`, the `core-tcdm` cases and the `dma-tcdm`
case, then `snax-shell` on `snax_hjson` with `forge/vecadd/`'s cluster file and the unit's trace on, then
every folder of `forge/` with the generic app (`forge.<design>`) and
`forge-reduce.vsum-r16` (vsum with its len overridden to 16, four sums;
`FORGE_REDUCE` in `tests/snax/regress.py`), then
snax_cluster's 17 plain tests on `snitch`. A program passes when it exits 0
within its timeout: each SNAX program returns its error count,
`stream-timing` and the `core-tcdm` cases but `subword` return 0, and a
plain test missing from `build/sw/tests/` fails. No output or cycle count is
compared (SG6), but `dma-timing` holds the RTL's DMA counters `busy`, `r`
and `w` and fails when they move (SG7), and `snax-shell`'s printed counter
must equal its unit's first run line, busy + stall_in + stall_out + flush,
that run firing its beats (`check_counter` in `tests/snax/regress.py`,
GEN3); so must `forge-reduce`'s, and a generated program's
`forge counter <task>:` line per accelerator task, matched to the unit's
run line for that run (`check_counters`). A `forge/` entry is read from its
`manifest.json` with plain json: its cluster file, run on `snax_hjson`
with `--param hjson=` (gvrun warns that the platform tree does not match),
the unit's trace path and each accelerator task's beats; the program is
built with `DESIGN=<design>`. It needs GVSoC built for
`snitch;snax_alu;snax_alu_sparse;snax_hjson`, as above, and takes about
two minutes.

    make regress

It ends with `regression passed` and exit 0, or names each program that
failed or did not finish and exits 1. Each run's output goes to
`build/regress/work/<name>/run.log`; a failure prints that path and the
log's last 20 lines. `python3 tests/snax/regress.py -k SUBSTRING` runs only
the programs whose name holds it, as `-k stream-timing`, `-k sparse`,
`-k forge` or `-k plain`; `make regress K=forge` passes `-k forge` (a bare
`make regress -k forge` does not: make reads `-k` as its own flag).

## Continuous integration

`.github/workflows/ci.yml` runs on every push to main, on every pull
request, and by hand (`workflow_dispatch`), in snax-forge's image
`ghcr.io/kuleuven-micas/snax-forge:main`. One job builds GVSoC for
`snitch;snax_alu;snax_alu_sparse;snax_hjson` (with ccache, kept between runs), runs the unit tests
(`python3 -m unittest discover -s tests/snax -p 'test_*.py'`), then
`make regress`. Only `snax/`, `sw/` and `tests/snax/` are built and
tested (and `forge/` run); GVSoC's other targets stay out.

When a program fails, the job log holds the last 20 lines of its
`run.log`, the run's summary shows one annotation per failed program, and
the `regress-logs` artifact holds every `run.log`. Actions must be enabled
in the repository's settings for the workflow to run.

## Where sw/ comes from

`sw/` holds the files of snax_cluster a build reads, at one pinned commit,
with the headers generated from them, so the programs build without a
snax_cluster checkout. `sw/README.md` gives the pin, the path map, the
licences and how each generated file is made; `make sync-snax-cluster
SNAX_CLUSTER=<checkout>` refreshes the copy from a checkout and reports what
moved, to be reviewed and committed with the new pin.

## Comparing with the RTL (by hand)

Cycles are compared with the RTL by hand, on demand, from fresh runs of one
ELF on both sides (only `dma-timing` checks its DMA counters itself), against SG5's target (`docs/plans/SG5.md`, "The target";
D124 in snax-forge). Only the RTL needs a snax_cluster checkout: clone it
next to this repo at the pin in `sw/README.md`, with its submodules:

    PIN=$(sed -n 's/^| `snax_cluster` | `\([0-9a-f]*\)`.*/\1/p' sw/README.md)
    git clone https://github.com/KULeuven-MICAS/snax_cluster.git ../snax_cluster
    git -C ../snax_cluster checkout $PIN
    git -C ../snax_cluster submodule update --init --recursive

Each target has its RTL: `snax_alu` is snax_cluster built with
`CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson`, `snax_alu_sparse` with
`cfg/snax_alu_cluster.hjson`. Keep one checkout per configuration (e.g.
`../snax_cluster_plain` and `../snax_cluster`), so neither build's
`make clean` removes the other's. In a checkout, `rtl-gen` and
`vsim_preparation` run in snax_cluster's image, the Questa binary on the
host, as its `target/snitch_cluster/README.md` says; for the sparse one:

    podman run --rm -v "$(dirname $PWD)":"$(dirname $PWD)" -w "$PWD" ghcr.io/kuleuven-micas/snax:main \
        bash -lc 'make -C target/snitch_cluster rtl-gen CFG_OVERRIDE=cfg/snax_alu_cluster.hjson'
    podman run --rm -v "$(dirname $PWD)":"$(dirname $PWD)" -w "$PWD" ghcr.io/kuleuven-micas/snax:main \
        bash -lc 'make -C target/snitch_cluster vsim_preparation CFG_OVERRIDE=cfg/snax_alu_cluster.hjson'
    make -C target/snitch_cluster bin/snitch_cluster.vsim CFG_OVERRIDE=cfg/snax_alu_cluster.hjson

For `snax-alu` at size `n` (`make -C sw/apps/snax-alu DATA_LEN=$n`), run the
ELF on that RTL from `target/snitch_cluster`:

    rm -rf logs
    bin/snitch_cluster.vsim ../../../snax-gvsoc/build/sw/apps/snax-alu/$n/snax-alu.elf
    rm -rf logs-$n && mv logs logs-$n

then here, on the target of the same configuration (`snax_alu_sparse` for
the build above, `snax_alu` for the plain one) with both cores' instruction
traces, and cut both runs into phases:

    E=build/sw/apps/snax-alu/$n/snax-alu.elf
    gvrun --target snax_alu_sparse --work-dir build/work/cmp-$n --trace=pe0/insn:pe0.txt \
        --trace=pe1/insn:pe1.txt --param chip/soc/binary=$PWD/$E run
    python3 tests/snax/phases.py $E --rtl ../snax_cluster/target/snitch_cluster/logs-$n
    python3 tests/snax/phases.py $E --gvsoc build/work/cmp-$n

`--show PHASE` lists one phase's instructions on either side.

## License

Apache 2.0, see `LICENSE` and `UPSTREAM.md`.
