# snax-alu

snax_cluster's `snax-alu` app, copied here so SNAX-GVSoC is developed against
a fixed program. Source: snax_cluster `b2672f8`, cluster
`cfg/snax_alu_cluster_old.hjson`.

| File | From snax_cluster |
|---|---|
| `src/snax-alu.c` | `target/snitch_cluster/sw/apps/snax-alu/src/`, unchanged |
| `lib/snax-alu-lib.c` | `target/snitch_cluster/sw/snax/snax-alu/src/`, unchanged |
| `include/snax-alu-lib.h` | `target/snitch_cluster/sw/snax/snax-alu/include/`, unchanged |
| `include/streamer_csr_addr_map.h` | written by the Chisel streamer in `rtl-gen` for that cluster |
| `data/datagen.py` | `target/snitch_cluster/sw/apps/snax-alu/data/`, unchanged |
| `data/data.h` | made once with NumPy seed 0, command below |

## Build

In the container, from the folder that holds this repo and snax_cluster,
build snax_cluster's runtime for the cluster once, then the app:

    make -C snax_cluster/target/snitch_cluster sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson
    make -C snax-gvsoc/tests/snax/snax-alu

The ELF is `build/snax-alu.elf`. `SNAX_CLUSTER=<path>` points the Makefile at
another checkout. Built with the same `data.h`, snax_cluster's own build of
the app gives a byte-identical ELF.

## data.h

From this folder, with the image's Python:

    PYTHONPATH=../../../../snax_cluster/util/sim python3 -c "
    import sys, runpy, numpy as np
    np.random.seed(0)
    sys.argv = ['datagen.py', '--mode=0', '--length=100']
    runpy.run_path('data/datagen.py', run_name='__main__')
    " > data/data.h

## Run

From snax-gvsoc, after `make build TARGETS=snax_alu` and `source sourceme.sh`:

    gvrun --target snax_alu --work-dir build/work/snax-alu \
        --param chip/soc/binary=$PWD/tests/snax/snax-alu/build/snax-alu.elf run

## Expected output

On snax_cluster's RTL:

    Accelerator Done!
    Accelerator Cycles: 25
    Number of errors: 0

On SNAX-GVSoC since SG3 P5, with the test datapath in the ALU's place (it
copies A where the ALU adds A and B; the 3 outputs that match are where B is
0), exit code 97:

    Accelerator Done!
    Accelerator Cycles: 25
    Number of errors: 97
