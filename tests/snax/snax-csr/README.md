# snax-csr

Checks the compute core's SNAX CSRs on the `snax_alu` target
(`snax/snax_alu_acc.py`: the streamer model and the ALU model): every
read-write CSR reads back what was written, through each kind of CSR
instruction, the forms that must not write leave a read-only CSR alone, and
the read-only CSRs read 0, as nothing is started. Only the compute core runs
it; it returns the number of errors.

The two start CSRs are left out: every pattern has bit 0 set, which starts
the block behind it. The streamer's (975) since SG3 P3, the ALU's (980) since
SG3 P5, when a test datapath took the ALU's place (the ALU since SG4 P2).

| Part | Instructions | Path in the core (`src/snitch/snitch.cpp`) |
|---|---|---|
| 1 | `csrw` to the 17 read-write CSRs, then `csrr` of all 17 | `SnaxCsr::handle()` with no read, then the callback |
| 2 | `csrrw` with `rd` not `x0`, then `csrr` | `handle()` with a read |
| 3 | `csrrs`, `csrrc`, `csrwi` on CSR 960 | the callback (read, then write); `handle()` |
| | `csrrwi`, `csrrsi`, `csrrci` with `rd` not `x0` on CSR 960: each returns the old value, then `csrr` | `handle()` with a read; the callback (read, then write) |
| | `csrrc` with `x0`, `csrrsi` and `csrrci` with 0 on CSR 982: each returns 0 | the callback, read only (`priv.hpp`) |
| 4 | `csrr` of the 4 read-only CSRs | the callback |

Part 3's no-write forms run on 982, the ALU's read-only performance counter
(0, as nothing ran): a write to a read-only SNAX CSR is refused and stops the
run here (the RTL's manager asserts on it), so they pass only if nothing is
written. Before SG6, `priv.hpp` wrote the value read back for these three
forms, and the run stopped at the first one.

The streamer and the ALU see 110 accesses: 69 reads and 41 writes (98 before
SG6, 108 before SG3 P3, 103 before SG3 P5).

Every form follows Zicsr (D120 in snax-forge) on both sides: `csrrw` and
`csrrwi` with `rd` not `x0` read before they write, `csrrs`, `csrrc`,
`csrrsi` and `csrrci` write unless `rs1` is `x0` or `uimm` is 0. The RTL does
so since snax_cluster's branch `ry/sg6-zicsr`: there the program as it was
before SG6 prints four lines of `0 errors`. SG6's checks in part 3 run on
SNAX-GVSoC only.

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

On SNAX-GVSoC since SG6, exit code 0 and nothing else printed:

    csrw/csrr: 0 errors
    csrrw: 0 errors
    set/clear/imm: 0 errors
    read-only: 0 errors
