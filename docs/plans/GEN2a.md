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
| 1 | snax-forge: docs only. D113 rewritten (integers first), PAPER §6.1's tier table, STATUS's M7, GEN2a, FLOW3 and M13 rows, open items 79 to 81 | |
| 2 | snax-forge: `gen/data.py` writes `data.h`: inputs from `make_inputs`, outputs zeroed with goldens from the reference executor, padded to whole beats and aligned to one | |
| 3 | snax-forge: the design check `memory.runtime`, an L1 layout kept below snRuntime's stacks (core count x 1 KiB plus a declared 256 B) | |
| 4 | snax-forge: the C backend `lower/c.py` (D135): task list, cluster file and CSR layout to `main.c` | |
| 5 | snax-forge: `gen-gvsoc` writes `main.c` and `data.h`; the manifest's `program` | |
| 6 | snax-forge: D135, ARCHITECTURE, C§9, STATUS | |
| 7 | This file | |
| 8 | The generic app `sw/apps/forge/`: `forge/$(DESIGN)/main.c` with the fixture's `include/` and `data.h` | |
| 9 | forge/'s fixtures refreshed; regress runs every folder with the generic app, the counter check per accelerator task; `forge-elementwise` removed, `forge-reduce` kept for `vsum-r16` | |
| 10 | vecadd's marks: every `forge_*` label in the ELF's symbols and its pc in GVSoC's instruction trace; `__cdata`, `__cbss`, `__tdata` against step 3's margin | |
| 11 | The notes, `forge/README.md`, the apps' READMEs, this file; full `make regress` | |
| 12 | snax-forge: its submodule at this branch's head; `test_fixture.py` reproduces every fixture, `main.c` and `data.h` included | snax-forge |
| 13 | snax-forge: STATUS (round 1 done); tag `gen2a-r1` in both repos | snax-forge |

Steps 12 and 13 land in snax-forge after this branch's last commit, which
its submodule points at; they are logged in snax-forge's STATUS.

## Findings

## Open
