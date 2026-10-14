# snax-csr

Checks the compute core's SNAX CSRs on the `snax_alu` target
(`snax/snax_alu_acc.py`: the streamer model and the ALU model): every
read-write CSR reads back what was written, and the read-only CSRs read 0, as
nothing is started. Only the compute core runs it; it returns the number of
errors.

The two start CSRs are left out: every pattern has bit 0 set, which starts
the block behind it. The streamer's (975) since SG3 P3, the ALU's (980) since
SG3 P5, when a test datapath took the ALU's place (the ALU since SG4 P2).

| Part | Instructions | Path in the core (`src/snitch/snitch.cpp`) |
|---|---|---|
| 1 | `csrw` to the 17 read-write CSRs, then `csrr` of all 17 | `SnaxCsr::handle()` with no read, then the callback |
| 2 | `csrrw` with `rd` not `x0`, then `csrr` | `handle()` with a read |
| 3 | `csrrs`, `csrrc`, `csrrwi` on CSR 960 | the callback (read, then write); `handle()` |
| 4 | `csrr` of the 4 read-only CSRs | the callback |

The streamer and the ALU see 98 accesses: 60 reads and 38 writes (108
before SG3 P3, 103 before SG3 P5).

Parts 2 and 3 use the two forms where SNAX-GVSoC follows Zicsr (D120 in
snax-forge) and snax_cluster's RTL does not: `csrrw` with `rd` not `x0`
reads before it writes here, and `csrrs` / `csrrc` write here. The core
warns once per run on each (since SG4 P3), without stopping the run. So the
program checks D120's paths on SNAX-GVSoC only; on the RTL parts 2 and 3
fail.

## Build and run

In the container, from the folder that holds this repo and snax_cluster,
after snax_cluster's runtime is built for the cluster (see
`../snax-alu/README.md`):

    make -C snax-gvsoc/tests/snax/snax-csr
    cd snax-gvsoc && source sourceme.sh
    gvrun --target snax_alu --work-dir build/work/sa_csr \
        --param chip/soc/binary=$PWD/tests/snax/snax-csr/build/snax-csr.elf run

Adding `--trace=snax_acc0` prints every access the streamer and the ALU
receive.

## Expected output

On SNAX-GVSoC since SG4 P3, exit code 0. The core's two warnings go to
stderr, so they can print after the program's lines:

    csrw/csrr: 0 errors
    csrrw: 0 errors
    csrrs/csrrc/csrrwi: 0 errors
    read-only: 0 errors
    ... /chip/soc/cluster_0/pe0/csr ... csrrw or csrrwi with rd not x0 reads SNAX CSR 960 before writing it here (Zicsr, D120); snax_cluster's RTL does not read it and writes rd with rs1 or the immediate plus the CSR number (warned once)
    ... /chip/soc/cluster_0/pe0/csr ... csrrs, csrrc, csrrsi or csrrci writes SNAX CSR 960 here (Zicsr, D120); snax_cluster's RTL only reads it (warned once)
