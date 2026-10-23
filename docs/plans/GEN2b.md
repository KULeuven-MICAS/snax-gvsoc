# GEN2b plan: snax-forge's ELF on snax_cluster's RTL

GEN2b is a task of M14 in snax-forge (D123 and D140 there): the program
snax-forge generates for a design point runs on SNAX-GVSoC and on
snax_cluster's RTL, the one ELF on both, and the printed lines are compared
by hand. Acceptance below.

This file is the checklist; `docs/notes/NOTES.md` is the log.

## How the steps are run

- On the MICAS server, by Claude Code: snax-forge's flows, bundles, ELFs and
  SNAX-GVSoC in snax-forge's image (`ghcr.io/kuleuven-micas/snax-forge:main`);
  snax_cluster's `rtl-gen` and `vsim_preparation` in its development image
  (`c5db84ad7bce`), its Verilator builds in its pixi environment, Questa
  2022.4 on the host (snax-forge `docs/RUN.md` section 8).
- One commit per step on `ry/gen2b` in snax_cluster, snax-gvsoc and
  snax-forge; no pull request until the round ends.

## The bar

For each design and N, read from the printed lines (`forge cycles`, `forge
data`, `forge counter`, `forge errors`):

- Verilator and Questa print the same lines;
- `forge errors: 0` and `forge data: 0 errors` everywhere;
- `forge counter` equal to SNAX-GVSoC's;
- the window within 10% of the RTL's: |w_gvsoc − w_rtl| / w_rtl ≤ 0.10.

## Where things live

- snax-forge never runs RTL (D140): it makes the bundle and builds the
  comparison ELF from it (`gvsoc/Makefile`'s `make sw`), the one SNAX-GVSoC
  runs; this repo's `sw/` is pinned at snax_cluster `cf4b0002`, and the
  runtime it links (`snax_alu_cluster_old`) differs from a bundle's cluster
  file only in fields the runtime does not read.
- snax_cluster owns the RTL builds and runs: `target/snitch_cluster/snax_forge.mk`
  (`snax-forge-sim`, `snax-forge-sw`, `snax-forge-run`; `SIM=vlt|vsim`, the
  bundle's cluster file as `CFG_OVERRIDE`, `ELF=` the comparison ELF), and
  `sw/apps/snax-forge`, which builds a fixture's own copy of the program for
  CI's pass/fail only. `snax-forge-sw` checks the bundle's
  `include/streamer_csr_addr_map.h` against the one snaxgen wrote (their
  `#define` lines).
- snax_cluster keeps vecadd and vsum as fixtures
  (`target/snitch_cluster/cfg/snax_forge/<design>/`, the program files
  included); its `snax-forge-ci.yml` builds each with Verilator, runs its
  program and checks the counter line its README expects.

## The shell rule and its cases (snax-forge open item 84)

`SnaxShell`'s rule (start, a start held while busy and answered in E + 1,
busy, the counter) was written twice: in `snax_shell.cpp`, and by hand in
snax-forge's `ShellCasesSpec`. It is now `SnaxShellRule` in
`snax/snax_shell.hpp`, plain C++ as `snax_unit.hpp` (`snax_shell.cpp` keeps
the ports, the CSR block and the event that sends a held start), and
`tests/snax/shell/` checks it, stepped with `SnaxUnitRule` as GVSoC wires
them, against hand-worked cases (`tests/snax/shell/README.md`): `make
regress` runs it as `shell`. snax-forge's `ShellCasesSpec` drives vecadd's
Chisel shell wrapper (`CsrManager`, `CtrlAdapter`,
`ElementwiseTiledSpatial`) through the same files
(`SNAX_GVSOC_SHELL_CASES`), checking every access's result and the unit's
busy every cycle. The hardware is the reference; both sides agree on all
eight cases, so no rule changed and no `make regress` result moved.

| Case | What |
|---|---|
| `field_read_back` | a field read back as written; start with bit 0 clear too |
| `start_bit0_clear` | start with bit 0 clear: a plain write, no run |
| `start_held` | a start while busy, held, answered in E + 1 |
| `read_busy` | busy from the cycle after the start to E |
| `counter` | the counter reset by an accepted start, counting, holding |
| `count_zero` | a count-0 start: ignored by the unit, the counter still reset |
| `start_in_last_cycle` | a start offered exactly in E: answered in E + 1 |
| `counter_after_start` | the counter 0 in the first cycle after an accepted start, at once or held |

## Runs

ELFs from snax-forge's bundles; RTL runs on the bundle's cluster file by its
absolute path (and on the fixtures, the same RTL); window / counter.

| Design | N | SNAX-GVSoC | Verilator | Questa | Window difference |
|---|---:|---|---|---|---:|
| vecadd (W = 4) | 64 | 226 / 19 | 239 / 19 | 239 / 19 | 5.4% |
| vecadd (W = 4) | 512 | 486 / 131 | 500 / 131 | 500 / 131 | 2.8% |
| vsum (W = 1) | 64 | 255 / 67 | 259 / 67 | 259 / 67 | 1.5% |
| vsum (W = 1) | 512 | 755 / 515 | 739 / 515 | 739 / 515 | 2.2% |

`forge errors: 0` and `forge data: 0 errors` in every run; the fixtures' own
programs print the RTL's lines at the default N. N reaches the hardware only
as CSR values (the streamer's bounds and addresses, the accelerator's
`loopCount` and vsum's `len`), so a design's `N=512` bundle has the
default's RTL and one build runs both ELFs.

## The gaps

- The counters are equal everywhere, so the accelerator's busy span (from
  the accepted start to the run's end) is the same on both sides; the
  window's difference lies outside it, in the cores and the DMA.
- vecadd: RTL − SNAX-GVSoC is 13 at N = 64 and 14 at N = 512, a fixed cost
  of the cores' fetch and timing (open items 65 and 67 in snax-forge).
- vsum: RTL − SNAX-GVSoC is +4 at N = 64 and −16 at N = 512: SNAX-GVSoC
  grows 20 cycles more than the RTL over the 448 extra words, with the
  counter's growth (448) equal. Within the bar, so not cut into phases.

## Steps

| # | Step | Status |
|---|---|---|
| R1 | snax_cluster #660: `StreamerGen` reads its params from the JSON (snax-forge open item 87) | done |
| R2 | vecadd: `snax_forge.mk`, `sw/apps/snax-forge`, the fixture's program, CI's run; the bar at both N | done |
| A1 | `SnaxShellRule` in `snax/snax_shell.hpp`; `snax_shell.cpp` calls it; `make regress` as main's (every run and trace log equal) | done |
| A2 | `tests/snax/shell/`: `tb.cpp`, `run.sh`, eight cases; `shell` in `make regress` | done |
| A3 | snax-forge: `SnaxShellCases`, `ShellCasesSpec` on the case files, `SNAX_GVSOC_SHELL_CASES` in CI | done |
| A4 | Disagreements between the two sides: none | done |
| B1 | vsum's flows, bundles and ELFs (default N and `N=512`) | done |
| B2 | snax_cluster's vsum fixture; `snax-forge-ci.yml` a matrix over vecadd and vsum | done |
| B3 | vsum on Verilator and Questa: the bar at both N | done |
| B4 | vsum's expected counter (67) in its README and CI | done |

## Deferred

- vecmul, vsum_tree and W = 8 on the RTL.
- snax-forge open item 83 (control alignment: a zero-count start, a done
  CSR, the counter's place, blocks taking a Decoupled `ctrl`).
- snax-forge open item 89: snax_cluster's testharness leaves the cluster's
  top-level CSR port undriven (task-queue CSRs `0x5FE`, `0x5FF`).
- snax-forge open item 90: snax_cluster's generated SV is not reproducible
  (`ComplexQueue`'s random `_H` suffix, the streamer header's `Generated at`
  line).
