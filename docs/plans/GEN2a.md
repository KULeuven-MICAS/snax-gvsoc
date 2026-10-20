# GEN2a plan: the program from the task list

GEN2a is a task of M14 in snax-forge (D111, D127, D135 there): the program
of a design point, written by snax-forge from its task list as C on
snRuntime, with its data, so a generated accelerator checks itself on
SNAX-GVSoC with no hand-written program. Single accelerators only: one core
driving several accelerators is snax-forge's open item 79, and dot (mul and
accumulate on one core) is M13's composite (D112 there).

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- On the MICAS server, by Claude Code, in snax-forge's image
  (`ghcr.io/kuleuven-micas/snax-forge:main`), as LNK2a.
- One commit per step on `ry/gen2a` (round 2: `ry/gen2a-2`), here and in
  snax-forge; each round tagged (`gen2a-r1`, `gen2a-r1b`, `gen2a-r2`).
- Anything not verified is said so.

## Acceptance

`vecadd`, `vecmul`, `vsum`, and `vsum` on the adder tree at W = 4, check
themselves on SNAX-GVSoC: each generated `main.c` exits 0 on its fixture,
its data errors 0 and each counter what the unit's run line gives.

## The rounds

| Round | Content |
|---|---|
| 1 | snax-forge: `data.h` from a datagen, a design check for snRuntime's top of L1, the C backend (`lower/c.py`, D135), the generator writing `main.c` and `data.h`. Here: the generic app `sw/apps/forge/`, the fixtures refreshed, regress over every folder of `forge/`, the marks checked |
| 1b | Fix-ups (snax-forge `lower/c.py`): start marks before a start group's writes, DMA waits from dependences only (D135 amended), one function per core; forge/ refreshed |
| 2 | The adder tree: the Accumulator's `lanes`, a combinational W → 1 adder tree in front of its register (snax-forge D133 amended); `SnaxUnit`'s fold over W lanes; `chisel_adder_tree` bound to the Accumulator; `vsum` at W = 4 (`forge/vsum_tree/`) |

## The C backend's rules

snax-forge's D135 and `snax_forge/lower/c.py` hold them; in short:

- Each step runs on the core that owns its component in the cluster file
  (the DMA's core has `xdma`, the accelerator's holds the slot): one
  function per core, a straight line, which `main` calls by
  `snrt_cluster_core_idx()` through a table; a core with no task takes part
  in the barriers only.
- A streamer or accelerator task is `csrw_ss` on the fixture's header
  names; a DMA task is `snrt_dma_start_1d` (or `_2d`) at its start. One
  `STREAMER_START_CSR` for all of an accelerator's movers, then its start,
  back to back: a start step's marks all come first.
- The waits on SNAX components are the ones snax-forge's lowering places
  (D64): the accelerator's busy then the streamer's polled. The DMA queues
  its transfers, so `snrt_dma_wait_all()` comes only from an `after`
  dependence or a sync. A hardware barrier on every core where another core
  goes on.
- A mark per task event, `csrr zero, mcycle` at a global label
  `forge_<task>_<event>` (configure, start, wait), and `forge_main_entry`,
  `forge_main_exit`.
- The self-check after the last sync, on the accelerator's core: every
  output against its golden from `data.h`, one counter line per
  accelerator task, the error count returned.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | snax-forge: docs only. D113 rewritten (integers first), PAPER §6.1's tier table, STATUS's M7, GEN2a, FLOW3 and M13 rows, open items 79 to 81 | done |
| 2 | snax-forge: `gen/data.py` writes `data.h`: inputs from `make_inputs`, outputs zeroed with goldens from the reference executor, padded to whole beats and aligned to one | done |
| 3 | snax-forge: the design check `memory.runtime`, an L1 layout kept below snRuntime's stacks (core count x 1 KiB plus a declared 256 B) | done |
| 4 | snax-forge: the C backend `lower/c.py` (D135): task list, cluster file and CSR layout to `main.c` | done |
| 5 | snax-forge: `gen-gvsoc` writes `main.c` and `data.h`; the manifest's `program` | done |
| 6 | snax-forge: D135, ARCHITECTURE, C§9, STATUS | done |
| 7 | This file | done |
| 8 | The generic app `sw/apps/forge/`: `forge/$(DESIGN)/main.c` with the fixture's `include/` and `data.h` | done |
| 9 | forge/'s fixtures refreshed; regress runs every folder with the generic app, the counter check per accelerator task; `forge-elementwise` removed, `forge-reduce` kept for `vsum-r16` | done |
| 10 | vecadd's marks: every `forge_*` label in the ELF's symbols and its pc in GVSoC's instruction trace; `__cdata`, `__cbss`, `__tdata` against step 3's margin | done |
| 11 | The notes, `forge/README.md`, the apps' READMEs, this file; full `make regress` | done |
| 12 | snax-forge: its submodule at this branch's head; `test_fixture.py` reproduces every fixture, `main.c` and `data.h` included | snax-forge |
| 13 | snax-forge: STATUS (round 1 done); tag `gen2a-r1` in both repos | snax-forge |

Steps 12 and 13 land in snax-forge after this branch's last commit, which
its submodule points at; they are logged in snax-forge's STATUS.

Round 1b, fix-ups on the same branches (tag `gen2a-r1b`):

| # | Step | Status |
|---|---|---|
| F1 | snax-forge: a start step's marks before its first write | done |
| F2 | snax-forge: DMA waits from dependences only; D135 amended | done |
| F3 | snax-forge: one `noinline` function per core, `main` through a table, no `volatile` index; the compile test over vecadd, vecmul and vsum, each label once | done |
| F4 | snax-forge: STATUS's RET1 row, ARCHITECTURE, C§16 | done |
| F5 | forge/ refreshed, full `make regress`, the marks check again, this file and the notes | done |
| F6 | snax-forge: submodule at this branch's head, fixtures reproduced | snax-forge |

Round 2, the adder tree (branches `ry/gen2a-2`, tag `gen2a-r2`); done, the
acceptance met:

| # | Step | Status |
|---|---|---|
| 1 | Here: `SnaxUnit`'s fold takes W lanes, the beat's lanes reduced by the op through a tree (`snax_unit_tree`), then folded as before; unit cases `pipelined_tree_tn` (T = n) and `pipelined_tree_t4` (T < n) at lanes 4 | done |
| 2 | snax-forge: the Accumulator's `lanes` (input a Vec, the tree in front of the register); `AccumulatorRateSpec` over the lanes-4 cases | done |
| 3 | snax-forge: `chisel_adder_tree` binds the Accumulator with `args: {"lanes": "W"}`, as `chisel_accumulator` now does | done |
| 4 | snax-forge: `recipes/vsum_tree.json` (vsum at N = 64, W = 4); its fixture generated | done |
| 5 | Here: `forge/vsum_tree/`, regress over it | done |
| 6 | snax-forge: submodule at step 5, `test_fixture.py` over the four fixtures | snax-forge |
| 7 | Docs in both, full `make regress` | done |

## Findings

- **The marks are where the program runs them (step 10, F5).** vecadd's ELF
  has 23 global text symbols for the marks (7 tasks x configure, start and
  wait, and main's entry and exit), each once; the pc of each is in
  GVSoC's instruction trace of the run (`--trace=pe0/insn`, `pe1/insn`):
  the DMA's tasks on core 1, the accelerator's and its streamer's on core
  0, each once, and `forge_main_entry` / `forge_main_exit` on both cores.
  Since F3 the ELF also has `forge_core_0`, `forge_core_1` (the functions)
  and `forge_cores` (their table), not marks. FLOW3 reads the marks'
  cycles; nothing reads them yet.
- **The runtime's top of L1 fits snax-forge's margin (step 10).** In
  vecadd's ELF, `.cdata` is 0 B, `.cbss` 16 B (`_cls`), `.tdata` 0 B and
  `.tbss` 8 B. Below the two 1 KiB stacks, `start.S` keeps CLS (16 B), main's
  return word (8 B) and the stacks' misalignment (8 B per hart, 16 B): 40 B
  of the declared 256 B (`memory.runtime`, snax-forge C§14). The TLS (8 B
  per hart) sits inside each hart's stack.

- **The image has clang, not GCC (step 4).** snax-forge's compile test
  uses the image's clang (snax_cluster's toolchain, clang 21.1.6) with
  `sw/toolchain.mk`'s flags against `sw/`'s headers, vecadd's, vecmul's
  and vsum's `main.c` with `-Werror`, and `llvm-nm` on the object for each
  label defined once; it skips without that clang or the submodule.
- **Branches per core let clang copy a mark (step 8, fixed in F3).** With
  `const uint32_t core` and an `if (core == k)` block per step, clang
  threaded the blocks into one path per core and copied the code every core
  passes onto each: vsum's `forge_main_exit` was defined twice and did not
  assemble (vecadd did). Round 1 kept the index in a `volatile`; since F3
  each core runs a straight-line function of its own and `main` has no
  branch, so there is nothing to copy.
- **The DMA waited for itself (step 4, fixed in F2).** Round 1 took every
  wait the lowering places, including SNAX-MODEL's no-start-while-busy
  wait on the DMA (D36 there): the program loaded A, waited, then loaded B,
  where the hand-written app queued both. Since F2 a DMA wait comes only
  from a dependence or a sync. vecadd's marks, round 1 against F3:
  `load_B_start` 1 cycle after `load_A_wait` (2863) against 21 cycles
  after `load_A_start` (2848), with no wait between; both loads end in one
  wait (2896, 2897).
- **A mark between the start writes cost a stall cycle (step 9, fixed in
  F1).** Round 1's counters were one below the hand-written apps': vecadd
  18, vecmul 18, vsum 66 against 19, 19, 67. The L1 addresses and the banks
  the readers hit are the same (A, B, O at `0x1000_0000`, `+0x200`,
  `+0x400`, as the `snrt_l1_next()` chain put them; one conflict, readers 0
  and 1 on banks 0 to 3 in the first cycle, reader 0 granted). The
  difference was `forge_<acc>_start` between `STREAMER_START_CSR` and the
  accelerator's start: the streamer started two cycles ahead instead of
  one (vecadd 2922 and 2924 against 2419 and 2420), so the unit saw one
  stall_in cycle fewer. Since F1 a start step's marks all come before its
  writes: 19, 19, 67, the hand-written apps' (`stall_in` 3, 3, 2).
- **An I-cache line can split the start writes (F2).** With F2's layout an
  L0 line began at the `STREAMER_START_CSR` instruction (`0x8000_0340`): the
  refill put the accelerator's start 10 cycles after it (2898, 2908), the
  streamer ran ahead and the unit saw no stall (vecadd and vecmul 16,
  `stall_in 0`). F3's layout does not split them (19). The RTL's L0
  prefetches the next line (snax-forge open item 65), so it would likely not
  miss there; nothing was tuned.
- **A forge counter depends on the core's timing (round 2).** A forge
  accelerator's counter depends on the core's timing between the streamer's
  and the accelerator's start writes (round 1b F2: an L0 line starting
  between them gave 16 instead of 19), so GEN2b compares that counter with
  care (snax-forge D123).
- **Where the accelerator starts (F2, F3).** vecadd's accelerator starts at
  cycle 2924 in round 1 and after F1, 2908 after F2, 2922 after F3; the
  hand-written app's at 2420. main starts at 2767 (F3) against 2284: about
  470 cycles go to snRuntime zeroing `.bss` before main, 544 B against 24 B,
  since `data.h`'s output C (512 B) is zero-initialised in L2 (139 stores by
  core 1, cycles 2173 to 2752 in F2's run); the hand-written app kept its
  output in L1. From main to the start: 155 cycles (F3) against 136.

## Open

- The marks cost a cycle each; between configures and around waits they
  move the core's timing, not the counters. FLOW3 reads them.
- The outputs' `.bss` zeroing before main (about 470 cycles for vecadd's
  512 B): FLOW3 decides whether the program's phases start at
  `forge_main_entry`, or the outputs move.
- One accelerator per program, two or more cores: one core driving the DMA
  and the accelerator (snax-forge open item 80) and several accelerators on
  one core (open item 79) were never run; a read step, a `signal` wait and
  a 2-D DMA are refused or never made.
