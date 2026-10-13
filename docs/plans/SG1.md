# SG1 plan: the snax_alu target and the CSR port

SG1 is the first task of M16 in snax-forge after SG0 (SNAX-GVSoC aligned
with snax_cluster, D116). Acceptance: a CSR test program reads back what it
wrote; snax_cluster's `snax-alu` app runs to exit on a stub register block;
the 17 plain tests still pass on the `snitch` target.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply`; commits and pushes
  are done by hand.
- Anything not verified is said so.

## The cluster

snax_cluster's `cfg/snax_alu_cluster_old.hjson` at `b2672f8`: one `rv32ima`
compute core with the ALU, one `rv32ima` DMA core, 128 KiB TCDM in 32 banks,
and the plain interconnect (`sparse_interconnect: false`). The target is
written by hand with these values; reading the hjson comes later.

## The M16 tasks after this plan

| ID | Scope |
|---|---|
| SG1 | `snax_alu` target, the CSR port (0x3C0 to 0x5FF out of the core, a read waits for its response), a stub register block, the `snax-alu` app copied in |
| SG2 | DMA matched to the RTL: a timing program at a few sizes on both sides; GVSoC's iDMA parameters and a DRAM with the testbench's latency and two transfers in flight; a new model only if tuning misses |
| SG3 | Streamer model, parameters named as in the hjson's streamer template, simple timing with hooks, standalone tests |
| SG4 | ALU model with `snax_alu_csr.sv`'s rules; `snax-alu` prints `Accelerator Cycles: 25` and `Number of errors: 0` |
| SG5 | Cycles per phase against RTL, the error target fixed first, a regression test |

## Steps

| # | Step | Status |
|---|---|---|
| 1 | P1: this plan; the snax_cluster pin moved to `b2672f8` | done 2026-10-13 |
| 2 | P2: the `snax-alu` app copied into `tests/snax/snax-alu/` (app, library, seeded `data.h`, `streamer_csr_addr_map.h`), linked against the runtime of `../snax_cluster` built with the old hjson; on `snitch` it stops at the first SNAX CSR | done 2026-10-13 |
| 3 | P3: the `snax_alu` target in `snax/`: 2 cores, `misa` of `rv32ima`; `simple` and `printf_simple` exit 0, `Hello, World!` twice | done 2026-10-13 |
| 4 | Read how a CSR instruction can send an IO request and stall until the response; findings only | done 2026-10-13 |
| 5 | P4: the core patch for the CSR port; the 17 plain tests still pass on `snitch` | |
| 6 | P5: the stub register block (registers over 960 to 982, busy reads 0) and a CSR test program; every written value reads back | |
| 7 | `snax-alu` on the stub runs to exit with no CSR warnings | |
| 8 | P6: SG1 closed here, and the STATUS.md and DECISIONS.md update for snax-forge | |

## Decided

## SG2 starts from
