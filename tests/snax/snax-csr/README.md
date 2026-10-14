# snax-csr

Checks the compute core's SNAX CSRs on the `snax_alu` target
(`snax/snax_alu_acc.py`: the streamer model and the ALU's stub): every
read-write CSR reads back what was written, and the read-only CSRs read 0, as
nothing is started. Only the compute core runs it; it returns the number of
errors.

The streamer's start CSR (975) is left out since SG3 P3: every pattern has
bit 0 set, which starts the streamer model. The ALU's start CSR (980) is
still checked; it has to leave too when the ALU is modelled (SG4).

| Part | Instructions | Path in the core (`src/snitch/snitch.cpp`) |
|---|---|---|
| 1 | `csrw` to the 18 read-write CSRs, then `csrr` of all 18 | `SnaxCsr::handle()` with no read, then the callback |
| 2 | `csrrw` with `rd` not `x0`, then `csrr` | `handle()` with a read |
| 3 | `csrrs`, `csrrc`, `csrrwi` on CSR 960 | the callback (read, then write); `handle()` |
| 4 | `csrr` of the 4 read-only CSRs | the callback |

The streamer and the ALU's stub see 103 accesses: 63 reads and 40 writes
(108 before SG3 P3, with 975).

## Build and run

In the container, from the folder that holds this repo and snax_cluster,
after snax_cluster's runtime is built for the cluster (see
`../snax-alu/README.md`):

    make -C snax-gvsoc/tests/snax/snax-csr
    cd snax-gvsoc && source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/sa_csr \
        --param chip/soc/binary=$PWD/tests/snax/snax-csr/build/snax-csr.elf run

Adding `--trace=snax_acc0` prints every access the streamer and the ALU's
stub receive.
