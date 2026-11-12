# obs-csr

Checks each core's observability CSR, `0x7C5`, against snax_cluster's `CsrObsRegister` (`hw/snitch/src/snitch.sv`): a 32-bit R/W register, 0 after reset, written by every CSR instruction on it; the RTL drives its low `ObsWidth` (8) bits on the core's `obs_o`, and the cluster's `obs_o` is core 0's. snax-forge's quiet build (`FORGE_QUIET`, D135) writes a section counter there. Every core checks its own register: 0 after reset, then `csrw`, `csrrw` (the old value returned), `csrrs` and `csrrc` (likewise), `csrwi`, and 0 again; it returns its errors, which the runtime adds up.

In SNAX-GVSoC the register is `csr_obs` of the Snitch core (`core/models/cpu/iss/src/snitch/snitch.cpp`); before it, a write to `0x7C5` only logged "Accessing unsupported CSR" and read back 0.

## Build and run

In the container, from snax-gvsoc (the Makefile builds the runtime from `sw/` first when needed):

    make -C sw/apps/obs-csr
    source sourceme.sh
    gvrun --target snax_hjson --work-dir build/work/obs-csr \
        --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/obs-csr/obs-csr.elf run

## Expected output

Exit code 0 and nothing printed; a failing check prints `obs-csr core <i>, <what>: read ..., expected ...`.
