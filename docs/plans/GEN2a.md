# GEN2a plan: the program from the task list

GEN2a is a task of M14 in snax-forge (D111, D127, D135 there): the program
of a design point, written by snax-forge from its task list as C on
snRuntime, with its data, so a generated accelerator checks itself on
SNAX-GVSoC with no hand-written program. Single accelerators only (several
on one core: snax-forge open item 79; dot: M13's composite, D112). Tags
`gen2a-r1`, `gen2a-r1b`, `gen2a-r2`.

## Acceptance

`vecadd`, `vecmul`, `vsum`, and `vsum` on the adder tree at W = 4, check
themselves on SNAX-GVSoC: each generated `main.c` exits 0 on its fixture,
its data errors 0 and each counter what the unit's run line gives. Met in
round 2.

## The rounds

- 1: snax-forge's `gen/data.py`, the check `memory.runtime`, the C backend
  `lower/c.py` (D135), `gen-gvsoc` writing `main.c` and `data.h`; here the
  generic app `sw/apps/forge/` (`forge-elementwise` removed) and regress over
  every folder of `forge/`. 1b: fix-ups F1 to F6.
- 2: the Accumulator's `lanes`, a W → 1 adder tree before its register (D133
  amended); `SnaxUnit`'s fold over W lanes; `forge/vsum_tree/`.

## The C backend's rules

snax-forge's D135 and `snax_forge/lower/c.py` hold them; in short: each
step runs on the core that owns its component, one `noinline` function per
core that `main` calls through a table (F3); streamer and accelerator tasks
are `csrw_ss`, one `STREAMER_START_CSR` then the accelerator's start, back
to back; the waits are the lowering's (D64), `snrt_dma_wait_all()` only from
a dependence or a sync (F2); the self-check after the last sync on the
accelerator's core. The marks (`forge_<task>_<event>`, `forge_main_entry`,
`forge_main_exit`) are since removed (FLOW3 round 1a).

## Steps

All done: round 1 steps 1 to 13 (snax-forge's `test_fixture.py` reproduces
every fixture, `main.c` and `data.h` included); round 1b F1 to F6; round 2
steps 1 to 7.

## Findings

- **The runtime's top of L1 fits snax-forge's margin (step 10).** vecadd:
  `.cdata` 0 B, `.cbss` 16 B, `.tdata` 0 B, `.tbss` 8 B; below the two 1 KiB
  stacks 40 B of the declared 256 B (`memory.runtime`, C§14).
- **The image has clang, not GCC (step 4).** snax-forge's compile test uses
  its clang 21.1.6 with `sw/toolchain.mk`'s flags and `-Werror`.
- **Branches per core let clang copy code (step 8, fixed in F3).** An `if
  (core == k)` block per step was threaded into one path per core, a label
  defined twice; since F3 each core runs a straight-line function.
- **The DMA waited for itself (step 4, fixed in F2).** Round 1 took
  SNAX-MODEL's no-start-while-busy wait (D36 there); since F2 both loads are
  queued and end in one wait.
- **A mark between the start writes cost a stall cycle (step 9, fixed in
  F1).** The streamer started two cycles ahead: counters 18, 18, 66; with
  the start writes back to back 19, 19, 67, the hand-written apps'.
- **A forge counter depends on the core's timing (F2, round 2).** An L0 line
  beginning at `STREAMER_START_CSR` gave 16 instead of 19 (`stall_in 0`);
  the RTL's L0 prefetches the next line (open item 65), so GEN2b compares
  that counter with care (D123).
- **Where the accelerator starts (F2, F3).** vecadd's main starts at 2767
  (F3) against the hand-written app's 2284: about 470 cycles of snRuntime
  zeroing `.bss` (`data.h`'s output C zero-initialised in L2). From main to
  the start: 155 cycles against 136.

## Open

- One accelerator per program, two or more cores: one core driving the DMA
  and the accelerator (open item 80) and several accelerators on one core
  (open item 79) were never run; a read step, a `signal` wait and a 2-D DMA
  are refused or never made.
