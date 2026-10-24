# SG2 plan: the DMA matched to the RTL

SG2 is the second task of M16 in snax-forge, after SG1. The iDMA model of
SNAX-GVSoC is adapted to the iDMA RTL of snax_cluster. Acceptance: a DMA
timing program at a few sizes runs on both sides, its cycles per size are
logged, and the gap is explained. Closed 2026-10-13; the log, with each
case's numbers, is `docs/notes/NOTES.md` (SG2 steps 1 to 8).

## The DMA path

From source at snax_cluster `b2672f8` and the iDMA fork's `master`
(`e859ffc`, upstream v0.6.5), the commit the RTL build took. Measured on the
RTL: a copy's engine time is `busy = L_rd + N_beats + 2`, with `L_rd` the
cycles from read request to first beat (11 from DRAM, 5 from L1) and
`N_beats` the 64 B beats it touches.

- `snrt_dma_wait_all` polls `dmstati 2`, the iDMA's `busy_o`.
- iDMA: a 3-deep request FIFO, then the midend and the backend; 512-bit AXI;
  a burst ends at the nearer 4 KiB boundary of source and destination; at
  most 3 bursts in flight per direction; a 3-beat buffer between reads and
  writes; the write burst waits for the first read beat; a transfer is done
  on the write response of its last burst.
- The testbench DRAM (`tb_memory_axi`) takes 2 reads and 2 writes in flight;
  into L1 one 64 B beat per cycle.
- `DMA_W_STALL` counts cycles the memory takes writes but no read data is
  there, `DMA_R_STALL` read data waiting on a full buffer (the "buffer"
  lines of `idma_inst64_events.sv`); `DMA_BUF_W_STALL` and
  `DMA_BUF_R_STALL` are never set.

## Steps

All done 2026-10-13: P1, this plan; P2, `dma-timing`: L2 to L1 at 64 B,
256 B, 800 B, 4 KiB and 8 KiB, 2 x and 4 x 800 B back to back, L1 to L2 at
800 B; steps 3 and 4, the same ELF on the RTL (author's run) and its
findings; P3, counting in GVSoC's cluster registers and a busy signal out of
the iDMA model; P4, the DRAM's 6 of the 11 cycles to a first beat
(`hbm_latency`), DRAM 64 B per cycle, `tcdm_width` 64 B, request queue 3,
bursts in flight 3, after which `busy` ended 5 cycles under the RTL in every
case; P5, the 5-cycle read path common to L1 and DRAM as one read latency in
the iDMA model, paid once per burst; P6, closed in snax-forge.

## Decided

- The DMA target is the engine time within a few cycles per transfer, with
  the cause of each remaining gap named, not an exact match. Core costs
  around the DMA (issue, polling) are SG5's.
- The DRAM's share of a DMA read's latency (6 cycles) is a target value
  (`hbm_latency`); the share common to L1 and DRAM (5 cycles) belongs to
  the DMA model (`read_latency`, P5).
- GVSoC's iDMA model is kept and fitted to the RTL by measurement, not
  replaced: a target sets the DMA through `ClusterArch(dma=...)` and the
  DRAM through `hbm_latency`; other targets keep upstream's values (D121 in
  snax-forge).
- The cluster's perf counters count `CYCLE`, `DMA_BUSY`, `DMA_R_DONE` and
  `DMA_W_DONE`, so the same program reads the same counters on both sides.
- Result: the DMA's engine time (`busy`) equals the RTL in all eight copy
  cases of `dma-timing`; `done` is 2 to 6 cycles under the RTL, all of it
  issue and polling in the core.

## SG3 starts from

- `snax-alu` starts its two copies (2 x 800 B, `busy` 39 cycles) and goes
  to the barrier without `snrt_dma_wait_all`; the barrier does not wait for
  the DMA (the wait added in SG5 P2).
- The core costs around the DMA (`mcycle`, `dmstati`: 3 against 6 cycles;
  issue and polling 15 to 16 against 18 to 22) are SG5's.
