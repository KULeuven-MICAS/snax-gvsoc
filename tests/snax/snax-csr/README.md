# snax-csr

Checks the compute core's SNAX CSRs on the `snax_alu` target's stub
(`snax/snax_csr_stub.py`): every read-write CSR reads back what was written,
and the read-only CSRs read 0. Only the compute core runs it; it returns the
number of errors.

| Part | Instructions | Path in the core (`src/snitch/snitch.cpp`) |
|---|---|---|
| 1 | `csrw` to the 19 read-write CSRs, then `csrr` of all 19 | `SnaxCsr::handle()` with no read, then the callback |
| 2 | `csrrw` with `rd` not `x0`, then `csrr` | `handle()` with a read |
| 3 | `csrrs`, `csrrc`, `csrrwi` on CSR 960 | the callback (read, then write); `handle()` |
| 4 | `csrr` of the 4 read-only CSRs | the callback |

The stub sees 108 accesses: 66 reads and 42 writes.

## Build and run

In the container, from the folder that holds this repo and snax_cluster,
after snax_cluster's runtime is built for the cluster (see
`../snax-alu/README.md`):

    make -C snax-gvsoc/tests/snax/snax-csr
    cd snax-gvsoc && source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/sa_csr \
        --param chip/soc/binary=$PWD/tests/snax/snax-csr/build/snax-csr.elf run

Adding `--trace=snax_acc0` prints every access the stub receives.
