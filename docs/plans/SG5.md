# SG5 plan: the baseline

SG5 is the fifth task of M16 in snax-forge, after SG4. SNAX's `snax-alu`
app, one ELF per `DATA_LEN`, run on snax_cluster's RTL and on SNAX-GVSoC;
per-phase cycles cut from both sides' instruction traces, with the ALU's
counter; the deviation per phase against an error target fixed before the
first comparison (open item 3 in snax-forge); a regression test (changed in
SG6: pass/finish only, the RTL compared by hand). Acceptance: the deviation
explained per phase and inside the target; the regression fails when cycles
drift. Closed 2026-10-14; the log is `docs/notes/NOTES.md` (SG5 steps 1 to
10).

## The app on the RTL

From source at snax_cluster `b2672f8`.

- Hart 0 is the compute core and hart 1 the DMA core. The hardware
  barrier (`csrr x0, 0x7C2`) waits for the cores only, not for the DMA.
- Each `printf` line and the exit are syscalls through `tohost` /
  `fromhost`, so C6 and C7 are set by how often each side's host polls.
- P2 put `snrt_dma_wait_all()` into snax_cluster's `snax-alu.c` after the
  two starts, before the barrier, which stays, so `snax-alu` stays
  snax_cluster's app. Without it, at 1024 and 4096 reader B would read B
  before the DMA writes it (estimated, not run).
- Sizes: `DATA_LEN` 4, 100, 128, 1024, 4096, `data.h` from NumPy seed 0. At
  4096, A, B and O take 96 KiB of L1 from 0x10000000; about 30 KiB stay
  free; the largest size that fits is about 5300.

## Phases and markers

A phase runs up to its marker: an instruction marked "retired" is the
phase's last, any other is the next phase's first. Markers are found by
function symbol and instruction pattern, never by fixed PC.

Compute core (hart 0):

| Phase | Up to | Counted |
|---|---|---|
| C0 boot | `main`'s first instruction (from `_start`; the runtime's init and its first barrier inside) | |
| C1 barrier | `main`'s `csrr x0, 0x7c2` retired; holds the DMA transfer | |
| C2a CSR setup | the write to 975 retired (`start_streamer`) | CSR writes |
| C2b CSR setup | the write to 980 retired (`start_alu`) | CSR writes |
| C3 ALU poll | the first call of `read_busy_streamer` | calls of `read_busy_alu` |
| C4 streamer poll | `main`'s first instruction after the last `read_busy_streamer` | calls of `read_busy_streamer` |
| C5 check loop | `main`'s read of 982 retired | |
| C6 printf | `main`'s `ret` | |
| C7 exit | hart 0's store to `tohost` | |

DMA core (hart 1):

| Phase | Up to | Counted |
|---|---|---|
| D0 boot | `main`'s first instruction | |
| D1 DMA issue | the first `dmstati` of the wait | |
| D2 DMA wait | the first instruction after the `dmstati` loop; holds the transfer | `dmstati` polls |
| D3 barrier | `main`'s `csrr x0, 0x7c2` retired | |
| D4 post-main and exit | the run's end, hart 0's store to `tohost`; holds the compute core's C2 to C7 | |

Total: from `_start` on hart 0 to its store to `tohost`. Total up to 982:
C0 to C5; it leaves out C6 and C7, which wait on the host.

The phase script `tests/snax/phases.py` (since removed, CLN1 R2b, #28) read
GVSoC's instruction traces and the RTL's raw `.dasm`, matching markers on
the instruction word and the CSR number (`llvm-objdump` shows `dmstati` as
`<unknown>` and 982 as `pmpaddr38`).

## The target

The model is a model: it serves to compare design points, so an exact match
is not required. Three tiers:

| Tier | What | Target |
|---|---|---|
| 1 | 982 in `snax-alu`; the error count | Equal on both sides, 0 errors, every size |
| 2 | The phases that grow with N: C1, D2, C3, C5, and the total up to 982 | Within 10% of the RTL, at 128, 1024 and 4096 |
| 3 | The fixed-cost phases (C0, C2a, C2b, C4, D0, D1, D3, D4); C6, C7 and the full total, which wait on the host; every phase at 4 and 100 | No number; each gap explained |

C4 is in tier 3: the streamer ends 2 to 4 cycles after the ALU at any N.

Gap rule: a gap in a SNAX block model is fixed; one in a latency or width
the target sets is set from the RTL run; one in the core's own ISS timing
is explained, accepted, and recorded as an open item in snax-forge.

## Steps

All done 2026-10-14: P1, this plan; P2, the DMA wait (merged in snax_cluster),
the pin moved; P3, the phase script; P4, the five sizes on SNAX-GVSoC; step 5,
the same ELFs on the RTL (author's run); step 6, the phases against the
target; P5, the core's loads; P6, `make regress`; step 9, its expected files
(`expected/` and `--update` since removed, 3cab3fa1); P7, SG5 closed in
snax-forge.

## Result

The author's run of the same five ELFs on both sides, RTL / SNAX-GVSoC:

| Phase | 128 | 1024 | 4096 |
|---|---|---|---|
| C1 barrier | 147 / 154 (+5%) | 373 / 381 (+2%) | 1153 / 1169 (+1%) |
| D2 DMA wait | 45 / 36 (-20%, accepted) | 270 / 262 (-3%) | 1050 / 1050 (0%) |
| C3 ALU poll | 37 / 39 (+5%) | 262 / 261 (0%) | 1032 / 1029 (0%) |
| C5 check loop | 5795 / 5698 (-2%) | 46115 / 45244 (-2%) | 184355 / 180754 (-2%) |
| Total up to 982 | 6713 / 6698 (0%) | 47495 / 46696 (-2%) | 187285 / 183755 (-2%) |

- Tier 1 met: 982 equal and 0 errors on both sides at every size.
- Tier 2 met at 128, 1024 and 4096, but for D2 at 128: the RTL core polls
  `dmstati` every 5 cycles, SNAX-GVSoC's every 2 (accepted).
- Tier 3, explained: C2a and D1 (the RTL's L0 prefetches, GVSoC's I-cache
  does not), C7 (atomics in DRAM through the RTL testbench's
  `axi_riscv_atomics_wrap`), C6 (the host's polling), C0 and D0 (the same
  fetch and host effects in boot), D3 (14 against 2 at 1024 and 4096, not
  looked into). Each is the core's or the testbench's own timing, recorded
  in snax-forge as open items 65 to 67.
- One gap was a target parameter and is fixed (P5): the core's loads. The
  RTL core has one integer load in flight (`num_int_outstanding_loads: 1`),
  a load issuing only once the previous load's data is back, 4 cycles later
  from L1 and 14 from DRAM; GVSoC issued loads back to back and took about 2
  and 9.
- Not looked into: the RTL's 2 more cycles before the check loop's `xor` on
  the second L1 load (44 cycles per element against 45).

## Decided

- The phases come from each side's per-instruction trace of the same ELF
  (D123), at markers found by symbol and pattern.
- The three-tier target and the gap rule (D124 in snax-forge, closing open
  item 3).
- The core's loads are a target parameter (D125): one integer load in
  flight in GVSoC's LSU behind a core property (0, no limit, for every other
  target), and the load-to-load cycles of the RTL run on the core's data
  path (`SNAX_CORE` since removed; `CORE_LATENCY` since moved to
  `snax/snax_hjson.py`); fetches keep their own path.
