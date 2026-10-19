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
- One commit per step on `ry/gen2a`, here and in snax-forge; each round
  tagged (`gen2a-r1`).
- Anything not verified is said so.

## Acceptance

`vecadd`, `vecmul`, `vsum`, and `vsum` on the adder tree at W = 4, check
themselves on SNAX-GVSoC: each generated `main.c` exits 0 on its fixture,
its data errors 0 and each counter what the unit's run line gives.

## The rounds

| Round | Content |
|---|---|
| 1 | snax-forge: `data.h` from a datagen, a design check for snRuntime's top of L1, the C backend (`lower/c.py`, D135), the generator writing `main.c` and `data.h`. Here: the generic app `sw/apps/forge/`, the fixtures refreshed, regress over every folder of `forge/`, the marks checked |
| 2 | The adder tree: `vsum` at W = 4 |

## The C backend's rules

snax-forge's D135 and `snax_forge/lower/c.py` hold them; in short:

- Each step runs on the core that owns its component in the cluster file
  (the DMA's core has `xdma`, the accelerator's holds the slot), branching
  on `snrt_cluster_core_idx()`.
- A streamer or accelerator task is `csrw_ss` on the fixture's header
  names; a DMA task is `snrt_dma_start_1d` (or `_2d`) at its start. One
  `STREAMER_START_CSR` for all of an accelerator's movers, then its start.
- The waits are the ones snax-forge's lowering places (D64): the
  accelerator's busy then the streamer's polled, or `snrt_dma_wait_all()`;
  a hardware barrier on every core where another core goes on.
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

## Findings

- **The marks are where the program runs them (step 10).** vecadd's ELF
  has 23 global text symbols `forge_*` (7 tasks x configure, start and
  wait, and main's entry and exit), each once; the pc of each is in
  GVSoC's instruction trace of the run (`--trace=pe0/insn`, `pe1/insn`):
  the DMA's tasks on core 1, the accelerator's and its streamer's on core
  0, each once, and `forge_main_entry` / `forge_main_exit` on both cores.
  FLOW3 reads their cycles; nothing reads them yet.
- **The runtime's top of L1 fits snax-forge's margin (step 10).** In
  vecadd's ELF, `.cdata` is 0 B, `.cbss` 16 B (`_cls`), `.tdata` 0 B and
  `.tbss` 8 B. Below the two 1 KiB stacks, `start.S` keeps CLS (16 B), main's
  return word (8 B) and the stacks' misalignment (8 B per hart, 16 B): 40 B
  of the declared 256 B (`memory.runtime`, snax-forge C§14). The TLS (8 B
  per hart) sits inside each hart's stack.

- **The image has clang, not GCC (step 4).** snax-forge's compile test
  uses the image's clang (snax_cluster's toolchain, clang 21.1.6) with
  `sw/toolchain.mk`'s flags against `sw/`'s headers, vecadd's and vsum's
  `main.c` with `-Werror`; it skips without that clang or the submodule.
- **A constant core index copies shared code (step 8).** With
  `const uint32_t core`, clang threads the `if (core == k)` blocks into one
  path per core and copies the code every core passes onto each: vsum's
  `forge_main_exit` was defined twice and did not assemble (vecadd did).
  `main.c` keeps the index in a `volatile`, read at each branch; snax-forge's
  compile test covers vsum since.
- **The waits are the lowering's, not the hardware's (step 4).** snax-forge's
  lowering puts a `wait dma` before `load_B`'s start (SNAX-MODEL's rule: no
  start while busy, D36 there); snRuntime's DMA queues transfers, as the
  hand-written apps used. So the generated program loads A, then B, where
  `forge-elementwise` started both and waited once. The accelerator's
  counter does not see it; the cycles before the start do.
- **The start mark moves each counter by one cycle (step 9).** The
  generated counters are one below the hand-written apps': vecadd 18
  against 19, vecmul 18 against 19, vsum 66 against 67 (`vsum-r16` stays
  67, still hand-written). The L1 addresses are the same: the memory plan
  puts A, B and O at `0x1000_0000`, `+0x200`, `+0x400`, where the
  `snrt_l1_next()` chain put them, and the readers hit the same banks with
  the same single conflict (readers 0 and 1 on banks 0 to 3 in the first
  cycle, reader 0 granted). The difference is `forge_<acc>_start` between
  the two start CSRs: the streamer starts two cycles before the accelerator
  instead of one (vecadd: cycles 2922 and 2924 against 2419 and 2420;
  vsum: 2336 and 2338 against 2244 and 2245), so its first beats arrive a
  cycle earlier against the start the counter counts from, and the unit
  sees one stall_in cycle fewer. Nothing was tuned.

## Open

- The DMA wait between the loads: from snax-forge's lowering, which keeps
  SNAX-MODEL's rule until RET1 (D45 there); whether the task list should
  let the DMA queue is decided with FLOW3, which reads the cycles.
- The marks cost a cycle each and the start mark shifts the counter by one
  (above); FLOW3 decides whether the start marks go before the streamer's
  start CSR.
- One accelerator per program, two or more cores: one core driving the DMA
  and the accelerator (snax-forge open item 80) and several accelerators on
  one core (open item 79) were never run; a read step, a `signal` wait and
  a 2-D DMA are refused or never made.
- Round 2: the adder tree, `vsum` at W = 4.
