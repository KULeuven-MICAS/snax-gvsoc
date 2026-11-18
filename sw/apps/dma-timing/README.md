# dma-timing

The DMA timing program, on SNAX-GVSoC on `snax_hjson` with `forge/vecadd/snax_forge.hjson`. The same ELF ran on snax_cluster's RTL; the DMA's values do not depend on the cluster's accelerator.

The DMA core copies between DRAM (L2) and L1, and transposes a 64 × 64 matrix A into T in L1 by 2-D transfers of one element per burst: for each column k of A, `snrt_dma_start_2d(T + p·k, A + b·k, b, b, p_A, 64)`, b the element's bytes, p the row pitch. For a transpose, A is first loaded into L1 at the pitch (not measured). For each case it:

1. clears the destination;
2. resets and enables the cluster's perf counters 0 to 5, and reads one enable back, so the posted stores have landed before the DMA turns busy;
3. takes `mcycle` before the first `snrt_dma_start_1d` or `_2d`, after the last one and after `snrt_dma_wait_all`;
4. stops the counters, reads them and checks the copy (a transpose: T against A's columns, both in L1).

Each case runs twice and the second run is kept, so instruction cache refills stay out of the numbers. After the barrier, core 0 prints one line per case. A case whose RTL values are not measured yet holds `UNPINNED` and is printed but not compared.

| Case | Copies |
|---|---|
| `idle` | none: the cost of the marks and of a wait on an idle DMA |
| `l2l1 1x64` to `1x8192` | one L2 to L1 copy of 64 B, 256 B, 800 B, 4 KiB, 8 KiB |
| `l2l1 2x800` | two copies back to back, at +0 and +800 B |
| `l2l1 4x800` | four copies back to back, at +0, +800, +1600, +2400 B |
| `l1l2 1x800` | one L1 to L2 copy |
| `t-l1l1 1x1 B p64` | one column of an int8 A in L1 (64 B rows): 64 bursts |
| `t-l1l1 64x1 B p64`, `p72` | the whole int8 A in L1, rows of 64 B, or of 72 B (9 words, as snax-forge's `padded_rows`): 4096 bursts |
| `t-l1l1 64x8 B p512` | an int64 A in L1: 4096 bursts of 8 B |
| `t-l2l1 64x1 B p64` | the int8 A read from DRAM, T in L1 |
| `l1l1 1x4096` | one 4 KiB copy inside L1 |
| `s-l1l1 64x64 B p128`, `64x8 B p64` | one 2-D copy inside L1 of 64 rows of one beat (stride 128 B) or of one word (stride 64 B) |
| `s-l1l2 64x1 B p64` | one 2-D copy of 64 one-byte rows from L1 (stride 64 B) into DRAM, back to back |

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

`w_stall` and `r_stall` have the meanings of the "buffer" lines of `idma_inst64_events.sv`, which overwrite the AXI-side ones. On SNAX-GVSoC the stall counters read 0 (not counted).

## Checked against the RTL

`busy`, `r` and `w` do not depend on the cores' timing, and SNAX-GVSoC gives the RTL's on every line. The program holds the RTL's values per case and prints a line for each case off them, so `make regress` and CI fail when the DMA's own timing moves. `issue` and `done` include the core's issue and polling: printed, not compared.

The program returns the copy errors plus the cases off the RTL's values; the RTL itself returns 0.

## Build

In the container, from snax-gvsoc (the Makefile builds the runtime from `sw/` first when needed):

    make -C sw/apps/dma-timing

The ELF is `build/sw/apps/dma-timing/dma-timing.elf`. `data/data.h` is generated, from this folder:

    python3 data/datagen.py > data/data.h

## Run

On SNAX-GVSoC, from snax-gvsoc, after `make build TARGETS=snax_hjson` and `source sourceme.sh`:

    gvrun --target snax_hjson --work-dir build/work/dma-timing \
        --param hjson=$PWD/forge/vecadd/snax_forge.hjson \
        --param chip/soc/binary=$PWD/build/sw/apps/dma-timing/dma-timing.elf run

On the RTL built from snax-forge's vecadd bundle (README, "Comparing with the RTL"), from snax_cluster:

    make -C target/snitch_cluster snax-forge-run SIM=vlt CFG_OVERRIDE=<bundle>/snax_forge.hjson \
        ELF=<snax-gvsoc>/build/sw/apps/dma-timing/dma-timing.elf

Keep from the RTL run: the printed lines, `dma_trace_00001_00000.log` from that folder (the iDMA's own trace, hart 1), and the iDMA commit Bender checked out (`Bender.lock` in snax_cluster, or the folder name under `.bender/git/checkouts/`).

## Expected output

Twenty-one lines: eighteen cases, `Number of errors: 0`, `Cases off the RTL's busy, r, w: 0` and `Cases not pinned yet: 0`; exit code 0.
