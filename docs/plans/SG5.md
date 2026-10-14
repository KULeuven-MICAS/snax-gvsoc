# SG5 plan: the baseline

SG5 is the fifth task of M16 in snax-forge, after SG4. SNAX's `snax-alu`
app, one ELF per `DATA_LEN`, run on snax_cluster's RTL and on SNAX-GVSoC;
per-phase cycles cut from both sides' instruction traces, with the ALU's
counter; the deviation per phase against an error target fixed here, before
the first comparison (open item 3 in snax-forge); a regression test locking
SNAX-GVSoC's numbers. Acceptance: the deviation explained per phase and
inside the target; the regression fails when cycles drift.

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- One step at a time: rehearsed in Claude's sandbox first, then the commands
  and the output to expect, then run on the MICAS server.
- Files come as `.patch` files applied with `git apply` on the branch
  `ry/sg5-baseline`; commits and pushes are done by hand, and the branch
  reaches main by a squash merge. P2 also has a patch for snax_cluster,
  merged there.
- Programs are built in snax-gvsoc and run on SNAX-GVSoC first; the same
  ELFs then run on the RTL (D123 in snax-forge).
- Anything not verified is said so.

## The app on the RTL

From source at snax_cluster `b2672f8`, read, not run.

- The runtime (`target/snitch_cluster/sw/runtime/rtl/src/snitch_cluster_start.c`,
  which `rtl-generic` includes) builds `snrt_main` (`sw/snRuntime/src/start.c`)
  with TLS, BSS, CLS and allocator init done by the CPU (no DMA), a
  hardware barrier, `main`, a second hardware barrier, then the exit: an
  all-to-all reduction of the exit codes over `_reduction_result` (in
  `.data`, so in DRAM), a global barrier (two hardware barriers around the
  DMA core's atomics), and core 0's store to `tohost`.
- Hart 0 is the compute core and hart 1 the DMA core: `snrt_is_dm_core()`
  is the last core of the cluster (`team.h`).
- `snrt_cluster_hw_barrier()` is `csrr x0, 0x7C2` (`sync.h:65`). It waits
  for the cores only, not for the DMA.
- `snrt_dma_start_1d()` issues a transfer and returns (`dma.h:98`);
  `snrt_dma_wait_all()` polls `dmstati` for busy until the DMA is idle
  (`dma.h:209`).
- `snax-alu.c`: the DMA core issues A, then B, and goes to the barrier
  without waiting. The compute core leaves the barrier when the DMA core
  arrives, so the transfer runs during C2 to C4 and the readers do not wait
  for it.
- Estimated from SG2's DMA times (4 KiB 77 cycles busy, 8 KiB 141), not run:
  B's first word lands in L1 about `N / 8 + 25` cycles after A's transfer
  starts; reader B asks for it about 50 cycles after the barrier (the CSR
  setup's length). Safe at 4, 100 and 128; at 1024 and 4096 reader B reads
  B before the DMA writes it, on both sides, and the errors would depend on
  each side's initial L1 and on a few cycles of core timing.
- Where the data sits: `local_a` is `snrt_l1_next()`, the allocator's base,
  which is the TCDM start (`alloc.h:75`); B and O follow it, `3 * N * 8`
  bytes in all, 96 KiB at 4096. The stacks, TLS and CLS sit at the top of
  the TCDM. A, B and OUT are globals in DRAM (`data.h`); the check loop reads
  OUT from DRAM and O from L1.
- The run writes a raw trace per hart, `logs/trace_chip_<chip>_hart_<hart>.dasm`
  (`hw/snitch_cluster/src/snitch_cc.sv`); `make traces` turns it into
  `.txt` with `spike-dasm` (`target/common/common.mk`), which the image does
  not have. The phase script reads the `.dasm` directly (P4b).

## The DMA wait (P2)

`snrt_dma_wait_all()` goes into snax_cluster's `snax-alu.c`, after the two
starts and before `end_dma_load = snrt_mcycle()`, so the app's own mark
spans issue and transfer. The barrier stays: the wait tells the DMA core its
transfers are done, the barrier tells the compute core. Only the app changes,
not the RTL, so SG2 to SG4's RTL results stay valid under the new pin; the
copy in `tests/snax/snax-alu/` follows the new commit, unchanged.

## Phases and markers

A phase runs up to its marker: an instruction marked "retired" is the
phase's last, any other is the next phase's first. Cycles are counted from a
phase's first instruction to the next phase's first. Markers are found in the ELF's disassembly
by function symbol and instruction pattern, never by fixed PC, so a rebuild
or another size moves nothing. Beside the cycles: the instructions retired
and, for the poll phases, the polls.

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
from `_start` on hart 0 to the read of 982, C0 to C5; it leaves out C6 and
C7, which wait on the host (below). Beside the table: 982 as printed, and
977 from SNAX-GVSoC's streamer trace (the app does not read 977, so the RTL
has none).

C6 and C7 are the host's, not the cluster's. Each `printf` line ends in a
syscall: `_putchar` (`target/snitch_cluster/sw/runtime/rtl/src/putchar.c`)
writes `tohost` and spins on `fromhost` until the host answers, and the exit
is a write to `tohost`. On SNAX-GVSoC the three answers come on a grid of
about 1000 cycles (spins of about 100 cycles ending at 6009, 9006 and
11009 at `DATA_LEN` 100), so C6 is set by how often each side's host polls.

## The phase script (P3)

`tests/snax/phases.py ELF --gvsoc WORKDIR | --rtl LOGDIR [--json OUT]`:
reads GVSoC's `pe0.txt` and `pe1.txt` (written by `--trace=pe0/insn:pe0.txt`
and `pe1/insn:pe1.txt`; a trace file name is relative to the work
directory) or the RTL's `trace_chip_*_hart_*.txt`, finds the markers in the
ELF's words and symbols, and prints one phase table per hart and the two
totals. Plain Python and pyelftools, in the image's venv; unit tests in
`tests/snax/test_phases.py`. The comparison of two sides is P6's. It is the
first piece of FLOW3's converter in snax-forge (instruction events to
phases); it does not close open item 60 there.

- The cycle of an instruction is the one on its trace line. A phase that
  ends at a marker marked "retired" starts the next phase at the line after
  it, so a stall of that instruction counts in its own phase whether the
  trace stamps it before or after the stall. GVSoC stamps a barrier at its
  release; the RTL's stamp is read from `gen_trace.py` only (a stalled
  cycle has no pc, so the line with the pc comes when the instruction
  leaves the stall).
- On the RTL the script reads the raw `.dasm` (P4b): time, cycle,
  privilege, pc, `DASM(<word>)` and a dict of extras, as `snitch_cc.sv`
  writes them. An instruction is a line from the integer core (`source` 0),
  not stalled and not offloaded to the FPU, the lines `gen_trace.py` gives
  a pc; the RTL writes a line when the instruction leaves its stall. The
  `.txt` of `make traces` is read when there is no `.dasm` (time and cycle
  blank when equal to the line before, no pc on stall and write-back lines,
  the metrics after `## Performance metrics`). Both formats are read from
  source, not from a run, until step 5.
- Markers are matched on the instruction word and the CSR number, not on a
  disassembler's names: `llvm-objdump` shows `dmstati` as `<unknown>` and
  982 as `pmpaddr38`.

## The sizes

`DATA_LEN` 4, 100, 128, 1024, 4096: 100 is the app's default and SG4's
reference. `data.h` per size from `datagen.py` with NumPy seed 0 and mode 0,
written into the size's build folder; the checked-in `data.h` (100) stays,
and the generated one at 100 equals it (P4: `make DATA_LEN=N` into
`build/N/`). One ELF per size. The fit of 4096 in L1 is checked from the
run, not the linker map, since L1 is allocated at run time: A, B and O at
0x10000000, 0x10008000 and 0x10010000 (the DMA's `dmdst` operands), 96 KiB
up to 0x10018000; the stacks at the top, 1 KiB per core
(`SNRT_LOG2_STACK_SIZE` 10), hart 1's `sp` starting at 0x1001fbd8. About
30 KiB stay free; the largest size that fits is about 5300.

## The target

The model is a model: it serves to compare design points, so an exact match
is not required. Three tiers:

| Tier | What | Target |
|---|---|---|
| 1 | 982 in `snax-alu`; the error count | Equal on both sides, 0 errors, every size |
| 2 | The phases that grow with N: C1, D2, C3, C5, and the total up to 982 | Within 10% of the RTL, at 128, 1024 and 4096 |
| 3 | The fixed-cost phases (C0, C2a, C2b, C4, D0, D1, D3, D4); C6, C7 and the full total, which wait on the host; every phase at 4 and 100 | No number; each gap explained |

C4 is in tier 3: the streamer ends 2 to 4 cycles after the ALU at any N.

## Gaps outside the target

Findings first (step 6), then a fix step, skipped if empty:

- In a SNAX block model (DMA, streamer, crossbar, ALU): fixed in SG5.
- In a latency or width the target sets (e.g. the core's path to DRAM):
  set from the RTL run, as SG2 did.
- In the core's own ISS timing (CSR issue, polling, I-cache, barrier):
  explained, accepted, and recorded as an open item in snax-forge.

## Tests

| Test | Where | Checks |
|---|---|---|
| `snax-alu` at five sizes | RTL and SNAX-GVSoC | The printed lines, the phase table, the target's tiers |
| Regression (`tests/snax/regress.py`, `make regress`) | SNAX-GVSoC | Exactly: `snax-alu` at five sizes with its phase table, `snax-stream`, `alu-timing`, `stream-timing`, `dma-timing`, `snax-csr` with its two warnings; the 17 plain tests on `snitch` exit 0 |

- Expected files per program under `tests/snax/<program>/expected/`; the
  author's RTL lines and phase tables under `tests/snax/<program>/rtl/`.
  For `snax-alu` the regression also checks tiers 1 and 2 against `rtl/`.
- `--update` rewrites `expected/`, with a notes entry saying why.
- Expected files come from the author's container build, not Claude's
  sandbox: its LLVM build already moves `dma-timing`'s `done` by 1 to 3
  cycles (SG4 step 2).
- Where `make regress` lives (the top `Makefile`, an upstream file with a
  row in `UPSTREAM.md`, or `tests/snax/Makefile`) is P6's choice.

## Not verified

- The RTL trace format as the script reads it, until step 5's traces.
- Whether either trace shows instructions before `_start` (a boot ROM); the
  phases start at `_start`, so it does not change them.
- The race at 1024 and 4096 without the wait: estimated, not run.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | P1: this plan; the reading in the notes; the SG5 row in snax-forge's STATUS | done 2026-10-14 |
| 2 | P2: the DMA wait in snax_cluster's `snax-alu.c` (a patch merged there) and the copy here synced, its README and the snax_cluster pin moved to that commit. `snax-alu` at 100 prints `Accelerator Cycles: 25` and `Number of errors: 0` on SNAX-GVSoC | done 2026-10-14 |
| 3 | P3: `tests/snax/phases.py` with unit tests on short trace excerpts; the phase table of `snax-alu` at 100 on SNAX-GVSoC | done 2026-10-14 |
| 4 | P4: `snax-alu` at the five sizes, the L1 fit check; errors, 982, 977 and the phase tables on SNAX-GVSoC | done 2026-10-14 |
| 5 | The same five ELFs on the RTL (author's run): the printed lines and the raw `.dasm` traces; phase tables from the script | todo |
| 6 | Per phase on both sides against the target, each gap classed. Findings only | todo |
| 7 | P5: the gaps of step 6 in a block model or a target parameter; skipped if there are none | todo |
| 8 | P6: the regression, `make regress` | todo |
| 9 | Expected files written in the author's container (`--update`); `make regress` passes there | todo |
| 10 | P7: SG5 closed here, and the STATUS.md and DECISIONS.md update for snax-forge (the target, the core's open items) | todo |

## Decided

- The phases come from each side's per-instruction trace of the same ELF
  (D123), at markers found by symbol and pattern; one script reads both
  trace formats.
- The DMA wait goes into snax_cluster's app (P2), before the barrier, which
  stays; the copy here follows that commit unchanged. Fixed in snax_cluster
  rather than in a variant program, so `snax-alu` stays snax_cluster's app.
- Five sizes: 4, 100, 128, 1024, 4096; seed 0, one ELF each.
- The three-tier target above, and the gap rule. Tier 2's total stops at
  the read of 982: C6 and C7 wait on the host's polling (P3).
- The regression locks SNAX-GVSoC's numbers exactly; its expected files come
  from the author's container.
- When snax-gvsoc gets CI, it builds and tests only the SNAX parts (the
  `snax_alu` target, `snax/`, `tests/snax/`, the SNAX-related upstream
  files), not GVSoC's other components.
- BASE1 (the timed flow log) is out of SG5: after the SG series, when the
  snax-forge flow runs end to end again. It stays under the paper's tasks in
  snax-forge.
- After SG5: SG6 (Zicsr on SNAX CSRs on both sides, SG4's warnings removed),
  then the housekeeping pass over snax-gvsoc's code, which includes the ALU
  sleeping until a beat moves (SG4).
