# snax-alu

snax_cluster's `snax-alu` app, copied into `sw/` so SNAX-GVSoC is developed
against a fixed program: `src/snax-alu.c` and `data/datagen.py` here, its
library in `sw/snax/snax-alu/`, the streamer's CSR map in
`sw/generated/snax_alu_cluster_old/`, cluster `cfg/snax_alu_cluster_old.hjson`.
Where each file comes from: `sw/README.md`, "Provenance of snax-alu".

## Build

In the container, from snax-gvsoc:

    make -C sw/apps/snax-alu

The ELF is `build/sw/apps/snax-alu/100/snax-alu.elf`; the Makefile builds
the runtime and the library from `sw/` first when needed. `DATA_LEN=N` (100
when unset, N a multiple of 4) builds into `build/sw/apps/snax-alu/N/`
(below). At each size the ELF is byte-identical to the one built with
snax_cluster's flow in a checkout at the pin (CI1).

## data.h

`make` writes `data.h` into the build folder with `datagen.py`, NumPy seed
0, mode 0, `DATA_LEN` elements; from snax-gvsoc, at 100:

    PYTHONPATH=sw/util python3 -c "
    import sys, runpy, numpy as np
    np.random.seed(0)
    sys.argv = ['datagen.py', '--mode=0', '--length=100']
    runpy.run_path('sw/apps/snax-alu/data/datagen.py', run_name='__main__')
    " > data.h

## Run

From snax-gvsoc, after `make build TARGETS=snax_alu` and `source sourceme.sh`:

    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-alu/100/snax-alu.elf run

## Expected output

On snax_cluster's RTL:

    Accelerator Done!
    Accelerator Cycles: 25
    Number of errors: 0

On SNAX-GVSoC, with the ALU model (`snax/snax_alu_shell.py`), exit code 0:
the same three lines.

## Phases

`../phases.py` cuts a run into phases from both cores' instruction traces
(SG5, `docs/plans/SG5.md`). On SNAX-GVSoC, trace both cores into the work
directory; a trace file name is taken relative to the work directory, so
give the name only:

    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-alu/100/snax-alu.elf \
        --trace=pe0/insn:pe0.txt --trace=pe1/insn:pe1.txt run
    python3 tests/snax/phases.py build/sw/apps/snax-alu/100/snax-alu.elf \
        --gvsoc build/work/snax-alu --json build/work/snax-alu/phases.json

On the RTL, after the run in snax_cluster's `target/snitch_cluster`, with
the same ELF. The script reads the raw `logs/trace_chip_*_hart_*.dasm` the
run writes, so `make traces` (and its `spike-dasm`) is not needed:

    python3 tests/snax/phases.py build/sw/apps/snax-alu/100/snax-alu.elf \
        --rtl ../snax_cluster/target/snitch_cluster/logs

It prints one table per core and the totals. At `DATA_LEN` 100 on
SNAX-GVSoC (SG5 step 3), hart 0's phases are C0 boot 644 cycles, C1
barrier 132, C2a 114, C2b 14, C3 33 (5 polls), C4 6 (1 poll), C5 check loop
2040, C6 printf 6445, C7 exit 76; hart 1's D0 653, D1 91, D2 30 (15
`dmstati` polls), D3 2, D4 8728; the total is 9504 cycles, 2983 up to the
read of 982. The unit tests of the script:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

## Sizes

SG5 runs the app at five `DATA_LEN` values. `make DATA_LEN=N` writes
`build/sw/apps/snax-alu/N/data.h` and `snax-alu.elf` there. From
snax-gvsoc, after `source sourceme.sh`:

    for n in 4 100 128 1024 4096; do
      make -C sw/apps/snax-alu DATA_LEN=$n
      gvrun --target snax_alu --work-dir build/work/sg5-$n \
          --param chip/soc/binary=$PWD/build/sw/apps/snax-alu/$n/snax-alu.elf \
          --trace=pe0/insn:pe0.txt --trace=pe1/insn:pe1.txt \
          --trace=streamer:streamer.txt run > build/work/sg5-$n.log 2>&1
      echo "$n exit $?"
      grep -a 'Cycles\|errors' build/work/sg5-$n.log
      grep -a 'Done' build/work/sg5-$n/streamer.txt | sed 's/.*Done/Done/'
      python3 tests/snax/phases.py build/sw/apps/snax-alu/$n/snax-alu.elf \
          --gvsoc build/work/sg5-$n --json build/work/sg5-$n/phases.json
    done

Each size exits 0 with `Number of errors: 0` and `Accelerator Cycles:`
N / 4: 1, 25, 32, 256, 1024. The streamer's `Done` line ends with its
counter (977), which the app does not read: 16, 42, 48, 272, 1040 in SG5
step 4, where the per-size phase tables are logged. 977 depends on the gap
between the two start writes, so it can move with the core's timing.

All three vectors fit in L1 at 4096: A, B and O take 96 KiB from the TCDM
start (0x10000000 to 0x10018000) and the stacks sit at the top, about 2 KiB
(`SNRT_LOG2_STACK_SIZE` 10, one per core); the largest `DATA_LEN` that fits
is about 5300.
