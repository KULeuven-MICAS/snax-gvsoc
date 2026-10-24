# GEN2b plan: snax-forge's ELF on snax_cluster's RTL

GEN2b is a task of M14 in snax-forge (D123 and D140 there): the program
snax-forge generates for a design point runs on SNAX-GVSoC and on
snax_cluster's RTL, the one ELF on both, and the printed lines are compared
by hand. Branch `ry/gen2b` in all three repos; how each part runs:
snax-forge `docs/RUN.md` section 8 (Questa 2022.4 on the host).

## The bar

For each design and N, read from the printed lines (`forge cycles`, `forge
data`, `forge counter`, `forge errors`):

- Verilator and Questa print the same lines;
- `forge errors: 0` and `forge data: 0 errors` everywhere;
- `forge counter` equal to SNAX-GVSoC's;
- the window within 10% of the RTL's: |w_gvsoc − w_rtl| / w_rtl ≤ 0.10.

Met for vecadd and vsum at N = 64 and 512 (Runs).

## Where things live

- snax-forge never runs RTL (D140): it makes the bundle and builds the
  comparison ELF, the one SNAX-GVSoC runs; the runtime it linked
  (`sw/`'s build for `snax_alu_cluster_old`, since `snax_forge`'s) differed
  from a bundle's cluster
  file only in fields the runtime does not read.
- snax_cluster owns the RTL builds and runs
  (`target/snitch_cluster/snax_forge.mk`, RUN.md section 8) and the vecadd
  and vsum fixtures in `target/snitch_cluster/cfg/snax_forge/`, which its
  `snax-forge-ci.yml` builds with Verilator, checking each counter line.

## The shell rule and its cases (snax-forge open item 84)

`SnaxShell`'s rule (start, a start held while busy and answered in E + 1,
busy, the counter) was written twice, in `snax_shell.cpp` and by hand in
snax-forge's `ShellCasesSpec`. It is now `SnaxShellRule` in
`snax/snax_shell.hpp`, plain C++ (`snax_shell.cpp` keeps the ports, the CSR
block and the event that sends a held start), checked by `tests/snax/shell/`
(`make regress`'s `shell`), stepped with `SnaxUnitRule`, against hand-worked
cases; `ShellCasesSpec` drives vecadd's Chisel shell wrapper (`CsrManager`,
`CtrlAdapter`, `ElementwiseTiledSpatial`) through the same files
(`SNAX_GVSOC_SHELL_CASES`), every access's result and the busy every cycle.
The hardware is the reference; both sides agree on all eight cases, so no
rule changed and no `make regress` result moved.

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

All done: R1 snax_cluster #660 (`StreamerGen` reads its params from the
JSON, open item 87), R2 vecadd on the RTL; A1 to A4 the shell rule and its
cases; B1 to B4 vsum's bundles, fixture, CI matrix and runs.

## Deferred

- vecmul, vsum_tree and W = 8 on the RTL.
- snax-forge open item 83 (control alignment: a zero-count start, a done
  CSR, the counter's place, blocks taking a Decoupled `ctrl`).
- snax-forge open item 89: snax_cluster's testharness leaves the cluster's
  top-level CSR port undriven (task-queue CSRs `0x5FE`, `0x5FF`).
- snax-forge open item 90: snax_cluster's generated SV is not reproducible
  (`ComplexQueue`'s random `_H` suffix, the streamer header's `Generated at`
  line).
