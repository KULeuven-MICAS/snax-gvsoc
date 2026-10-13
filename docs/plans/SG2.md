# SG2 plan: the DMA matched to the RTL

SG2 is the second task of M16 in snax-forge, after SG1. The iDMA model of
SNAX-GVSoC is adapted to the iDMA RTL of snax_cluster. Acceptance: a DMA
timing program at a few sizes runs on both sides, its cycles per size are
logged, and the gap is explained.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply`; commits and pushes
  are done by hand.
- Anything not verified is said so.

## The DMA path

From source at snax_cluster `b2672f8` and the iDMA fork's `master`
(`e859ffc`, upstream v0.6.5), the commit the RTL build took (step 3).
Measured on the RTL in step 4: a copy's engine time is
`busy = L_rd + N_beats + 2`, with `L_rd` the cycles from read request to
first beat (11 from DRAM, 5 from L1) and `N_beats` the 64 B beats it
touches.

- Program: `snrt_dma_start_1d` is `dmsrc`, `dmdst` and `dmcpyi` (1D, R-AW
  coupled, channel 0) through the DMA core's offload port;
  `snrt_dma_wait_all` polls `dmstati 2`, the iDMA's `busy_o`.
- iDMA (`idma_inst64_top`, `idma_backend_rw_axi`): a 3-deep request FIFO,
  then the midend and the backend. 512-bit AXI. A burst ends at the nearer
  4 KiB boundary of source and destination. At most 3 bursts in flight per
  direction (`NumAxInFlight`); a 3-beat buffer between reads and writes; the
  write burst waits for the first read beat; a transfer is done on the write
  response of its last burst. `busy_o` is the midend or the backend busy.
- Around it: the cluster's wide crossbar (cut on all ports) and a cut on the
  external wide port; into L1 one 64 B beat per cycle. The testbench DRAM
  (`tb_memory_axi`) takes 2 reads and 2 writes in flight (atomics filter),
  then a cut and `axi_to_reg`; the memory itself answers in the same cycle.
- GVSoC (`SnitchDma` in `snitch_cluster.py`, `pulp/idma/`): 8 transfers
  queued, 24 bursts in flight, `tcdm_width` 4096 B (a whole burst is one L1
  write), bursts split on the AXI side only, a read burst's data arrives at
  once after its latency, done when the last L1 write is acknowledged. The
  DRAM is 100 cycles behind the chip's wide router (`hbm_latency` in `Soc`)
  and 4 B per cycle (`width_log2=2` in `snax_alu.py`).

## Measuring

Per case, on the DMA core: reset counters 0 to 5 and enable `DMA_BUSY`,
`DMA_AR_STALL`, `DMA_R_DONE`, `DMA_W_DONE`, `DMA_W_STALL` and `DMA_R_STALL`
(`perf_cnt.h`); read the enable register back, so the posted store has
landed before the DMA turns busy; `mcycle` before the first start, after the
last start and after `snrt_dma_wait_all`; then read the counters.

- `DMA_BUSY` counts the cycles `busy_o` is high: the engine alone, without
  the issue cost, the request FIFO or the polling.
- `DMA_W_STALL` counts cycles the memory takes writes but no read data is
  there, and `DMA_R_STALL` read data waiting on a full buffer: the
  "buffer" lines of `idma_inst64_events.sv` overwrite the AXI-side meanings.
  `DMA_BUF_W_STALL` and `DMA_BUF_R_STALL` are never set.
- On GVSoC the cluster registers hold these counters but nothing counts, so
  they read 0 until P3.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | P1: this plan; SG1.md and snax-forge's STATUS say the housekeeping pass moves after SG5 | done 2026-10-13 |
| 2 | P2: the timing program in `tests/snax/dma-timing/`: L2 to L1 at 64 B, 256 B, 800 B, 4 KiB and 8 KiB, 2 x and 4 x 800 B back to back, L1 to L2 at 800 B; each case run twice, the second kept; one line per case and the error count. On `snax_alu`: `mcycle` only, 0 errors | done 2026-10-13 |
| 3 | The same ELF on the RTL (author's run): the printed lines, the iDMA commit, `dma_trace_00001_00000.log` | done 2026-10-13 |
| 4 | From the RTL numbers: issue cost, startup, first-beat latency, beat rate, effect of the 2-read limit, done delay. Findings only | done 2026-10-13 |
| 5 | P3: counting in GVSoC's cluster registers (`CYCLES`, `DMA_BUSY`, read and write beats) and a busy signal out of the iDMA model; the program prints counters on both sides | done 2026-10-13 |
| 6 | P4: parameters from step 4, through arch values: the DRAM's 6 of the 11 cycles to a first beat (`hbm_latency`), DRAM 64 B per cycle, `tcdm_width` 64 B, request queue 3, bursts in flight 3. `hbm_latency` also moves the cores' DRAM fetches and loads, which are not measured (SG5). `busy` ends 5 cycles under the RTL in every case | done 2026-10-13 |
| 7 | P5: the 5-cycle read path common to L1 and DRAM (the wide crossbar's cuts and the AXI-to-memory conversion) as one read latency in the iDMA model, paid once per burst, the beats after it one per cycle; the L1 read side, which keeps one line request open, pipelined so it is not paid per line. Target: `busy` equal to the RTL in all eight copy cases. Gap per case logged | |
| 8 | P6: SG2 closed here, and the STATUS.md and DECISIONS.md update for snax-forge | |

## Decided

- The DMA target is the engine time within a few cycles per transfer, with
  the cause of each remaining gap named, not an exact match: GVSoC hands a
  burst over as one block and has no AXI handshakes, and the DRAM is the
  testbench's memory. Core costs around the DMA (issue, polling) are SG5's.
- The DRAM's share of a DMA read's latency (6 cycles) is a target value
  (`hbm_latency`); the share common to L1 and DRAM (5 cycles) belongs to
  the DMA model (P5).
