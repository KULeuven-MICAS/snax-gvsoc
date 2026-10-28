# snax-csr

Checks the compute core's SNAX CSRs on `snax_hjson` with
`forge/vecadd/snax_forge.hjson` (the streamer and the shell, named by
`forge/vecadd/include/`'s headers): every
read-write CSR reads back what was written, through each kind of CSR
instruction, the forms that must not write leave a read-only CSR alone, and
the read-only CSRs read 0, as nothing is started. Only the compute core runs
it; it returns the number of errors.

The two start CSRs, the streamer's (975) and the group's START (978), are left out:
every pattern has bit 0 set, which starts the block behind it.

| Part | Instructions | Path in the core (`src/snitch/snitch.cpp`) |
|---|---|---|
| 1 | `csrw` to the 16 read-write CSRs, then `csrr` of all 16 | `SnaxCsr::handle()` with no read, then the callback |
| 2 | `csrrw` with `rd` not `x0`, then `csrr` | `handle()` with a read |
| 3 | `csrrs`, `csrrc`, `csrwi` on CSR 960 | the callback (read, then write); `handle()` |
| | `csrrwi`, `csrrsi`, `csrrci` with `rd` not `x0` on CSR 960: each returns the old value, then `csrr` | `handle()` with a read; the callback (read, then write) |
| | `csrrc` with `x0`, `csrrsi` and `csrrci` with 0 on CSR 981: each returns 0 | the callback, read only (`priv.hpp`) |
| 4 | `csrr` of the 4 read-only CSRs | the callback |

Part 3's no-write forms run on 981, the group's read-only COUNTER
(0, as nothing ran): a write to a read-only SNAX CSR is refused and stops the
run here (the RTL's manager asserts on it), so they pass only if nothing is
written. Before SG6, `priv.hpp` wrote the value read back for these three
forms, and the run stopped at the first one.

The streamer and the shell see 105 accesses: 66 reads and 39 writes.

Every form follows Zicsr (D120 in snax-forge) on both sides: `csrrw` and
`csrrwi` with `rd` not `x0` read before they write, `csrrs`, `csrrc`,
`csrrsi` and `csrrci` write unless `rs1` is `x0` or `uimm` is 0. The RTL does
so since snax_cluster `9fbf35d` (#657): there the program as it was
before SG6 prints four lines of `0 errors`. SG6's checks in part 3 run on
SNAX-GVSoC only.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/snax-csr
    source sourceme.sh
    gvrun --target snax_hjson --work-dir build/work/sa_csr \
        --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/snax-csr/snax-csr.elf run

Adding `--trace=snax_acc0` prints every access the streamer and the shell
receive.

## Expected output

On SNAX-GVSoC since SG6, exit code 0 and nothing else printed:

    csrw/csrr: 0 errors
    csrrw: 0 errors
    set/clear/imm: 0 errors
    read-only: 0 errors
