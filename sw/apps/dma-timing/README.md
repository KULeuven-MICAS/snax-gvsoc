# dma-timing

The SG2 DMA timing program (`docs/plans/SG2.md`). The same ELF runs on
snax_cluster's RTL, cluster `cfg/snax_alu_cluster_old.hjson` at
snax_cluster `b2672f8`, and on SNAX-GVSoC on `snax_hjson` with
`forge/vecadd/snax_forge.hjson` (until CLN1 on the `snax_alu` target).

The DMA core copies between DRAM (L2) and L1. For each case it clears the
destination, resets and enables the cluster's perf counters 0 to 5, reads one
enable back (so the posted stores have landed before the DMA turns busy), then
takes `mcycle` before the first `snrt_dma_start_1d`, after the last one and
after `snrt_dma_wait_all`. It then stops the counters, reads them and checks
the copy. Each case runs twice and the second run is kept, so instruction
cache refills stay out of the numbers. After the barrier the compute core
prints one line per case.

| Case | Copies |
|---|---|
| `idle` | none: the cost of the marks and of a wait on an idle DMA |
| `l2l1 1x64` to `1x8192` | one L2 to L1 copy of 64 B, 256 B, 800 B, 4 KiB, 8 KiB |
| `l2l1 2x800` | two copies back to back, at +0 and +800 B, as `snax-alu` does |
| `l2l1 4x800` | four copies back to back, at +0, +800, +1600, +2400 B |
| `l1l2 1x800` | one L1 to L2 copy |

| Field | Meaning |
|---|---|
| `issue` | `mcycle` from before the first start to after the last start |
| `done` | `mcycle` from before the first start to after `snrt_dma_wait_all` |
| `busy` | `DMA_BUSY`: cycles the iDMA's `busy_o` is high |
| `r`, `w` | `DMA_R_DONE`, `DMA_W_DONE`: read and write beats of 64 B |
| `ar_stall` | `DMA_AR_STALL`: cycles a read request waits for the memory |
| `w_stall` | `DMA_W_STALL`: cycles the memory takes writes but no data is there |
| `r_stall` | `DMA_R_STALL`: cycles read data waits on a full buffer |
| `err` | words of the copy that differ from the source |

`w_stall` and `r_stall` have the meanings of the "buffer" lines of
`idma_inst64_events.sv`, which overwrite the AXI-side ones. On SNAX-GVSoC the
stall counters read 0 (not counted).

## Checked against the RTL

`busy`, `r` and `w` do not depend on the cores' timing (D123), and SNAX-GVSoC
gives the RTL's on every line. The program holds the RTL's values per case
(SG2 step 3 at `b2672f8`, the same at the pin `9fbf35d` in SG7 round 4) and
prints a line for each case off them, so `make regress` and CI fail when the
DMA's own timing moves. `issue` and `done` include the core's issue and
polling (SG5, open item 67 in snax-forge): printed, not compared.

The program returns the copy errors plus the cases off the RTL's values; the
RTL itself returns 0.

## Build

In the container, from snax-gvsoc (the Makefile builds the runtime from
`sw/` first when needed):

    make -C sw/apps/dma-timing

The ELF is `build/sw/apps/dma-timing/dma-timing.elf`. `data/data.h` is
generated, from this folder:

    python3 data/datagen.py > data/data.h

## Run

On SNAX-GVSoC, from snax-gvsoc, after `make build TARGETS=snax_hjson` and
`source sourceme.sh`:

    gvrun --target snax_hjson --work-dir build/work/dma-timing \
        --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/dma-timing/dma-timing.elf run

On the RTL built from the same hjson (Verilator here; `.vsim` and `.vcs`
take the same argument):

    cd snax_cluster/target/snitch_cluster
    bin/snitch_cluster.vlt <snax-gvsoc>/build/sw/apps/dma-timing/dma-timing.elf

Keep from the RTL run: the printed lines, `dma_trace_00001_00000.log` from
that folder (the iDMA's own trace, hart 1), and the iDMA commit Bender
checked out (`Bender.lock` in snax_cluster, or the folder name under
`.bender/git/checkouts/`).

## Expected output

Eleven lines: nine cases, `Number of errors: 0` and `Cases off the RTL's
busy, r, w: 0`; exit code 0.
