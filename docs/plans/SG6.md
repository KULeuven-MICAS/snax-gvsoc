# SG6 plan: Zicsr on SNAX CSRs

SG6 is the sixth task of M16 in snax-forge, after SG5. Every CSR instruction
on snax_cluster's SNAX CSRs (0x3C0 to 0x5FF) does what Zicsr says, on the RTL
and on SNAX-GVSoC; SG4's two CSR-form warnings go. Acceptance: `snax-csr`
covers every form and passes on SNAX-GVSoC, its original four parts pass on
the RTL, and nothing else moves (`snax-alu` against `rtl/`, `make regress`).

This file is the checklist; `docs/notes/NOTES.md` is the log. A step is
ticked here when its entry is in the notes.

## How the steps are run

- In rounds, on the MICAS server: the commands run in the author's
  container (the RTL build split between the container and Questa on the
  host), on the branch `ry/sg6-zicsr` in snax_cluster and here; commits and
  pushes are done by hand.
- Anything not verified is said so.

## The forms

On a SNAX CSR, before SG6:

| Form | Zicsr | RTL before | SNAX-GVSoC before |
|---|---|---|---|
| `csrrw` / `csrrwi`, `rd` = `x0` (`csrw`, `csrwi`) | write | write | write |
| `csrrw` / `csrrwi`, `rd` not `x0` | read, then write; `rd` gets the old value | write; `rd` gets `rs1` (or `uimm`) plus the CSR number | as Zicsr, warned (SG4 P3) |
| `csrrs`, `rs1` = `x0` (`csrr`) | read | read | read |
| `csrrc`, `rs1` = `x0` | read | read | read, then writes the value read back |
| `csrrsi` / `csrrci`, `uimm` = 0 | read | read | read, then writes the value read back |
| `csrrs` / `csrrc`, `rs1` not `x0` | read, then write old `\|` mask / old `& ~` mask | read | as Zicsr, warned (SG4 P3) |
| `csrrsi` / `csrrci`, `uimm` not 0 | the same with `uimm` | read | as Zicsr, warned (SG4 P3) |

SNAX-GVSoC's write-back on the no-write forms was GVSoC's ISS
(`priv.hpp`, every core and every CSR); on a read-only SNAX CSR it stops the
run. No SNAX program used those forms before SG6.

## The RTL change (round 1)

snax_cluster `9fbf35d` (#657, merged from the branch `ry/sg6-zicsr`), two
files:

- `hw/snitch/src/snitch.sv`, the SNAX branches of the decoder: `csrrw` /
  `csrrwi` with `rd` not `x0` take `rd` from the accelerator's response, as
  `csrrs` does; `csrrs` / `csrrc` send `rs1`, `csrrsi` / `csrrci` the
  `uimm`, as operand A, the mask.
- `hw/snax_util/src/snax_intf_translator.sv`: the forms that read then
  write go out as a read, then a write from latched address, select,
  operation and mask; the write's value is the old value, or old `|` / `& ~`
  mask, the old value going to the core. They are accepted only when no older
  read is outstanding, and the core's `qready` stays low until the write is
  taken (`RmwIdle`, `RmwWaitRsp`, `RmwWrite`). `csrw` and `csrr` keep their
  handshake and timing.

## The GVSoC change (round 2)

- `core/models/cpu/iss/include/isa/priv.hpp`: `csrrc` with `rs1` = `x0` and
  `csrrsi` / `csrrci` with 0 write nothing, as `csrrs` already did. For every
  core; a row in `UPSTREAM.md`.
- `SnaxCsr::handle()` and `Iss::snax_csr_access()` lose SG4's warnings, and
  `Iss` their flags.
- Left: upstream's generic `csrrw` / `csrrwi` path reads with `rd` = `x0`
  too; SNAX CSRs go through `SnaxCsr::handle()`, which does not.

## Tests

| Test | Where | Checks |
|---|---|---|
| `snax-csr` before SG6 (four parts) | RTL | Four lines of `0 errors`, exit 0 (17 and 20 errors before) |
| `snax-csr` with SG6's part 3 | SNAX-GVSoC | Four lines of `0 errors`, exit 0, no warning; 110 accesses |
| `snax-alu` at five sizes | RTL | The phases and printed lines equal SG5's `rtl/` tables, same ELFs |
| Regression (`make regress`) | SNAX-GVSoC | Round 2: only `snax-csr`'s expected file changes; from round 3 on, every program exits 0 |

- Part 3 adds `csrrwi`, `csrrsi` and `csrrci` with `rd` not `x0` on 960, and
  `csrrc` with `x0`, `csrrsi` and `csrrci` with 0 on the read-only 982: a
  write there stops the run, so they pass only if nothing is written.
- The extended `snax-csr` runs on SNAX-GVSoC only, by the author's choice;
  on the RTL its original four parts ran.
- A static scan of the 31 ELFs `make regress` runs finds the no-write forms
  in `snax-csr` only, so the `priv.hpp` change moves no other program.

## Decided

- Both sides follow Zicsr on SNAX CSRs; the RTL is fixed in snax_cluster
  (decoder and translator), not modelled here as it was.
- A read-then-write waits for no older read outstanding: no reordering in
  the translator; `csrw` and `csrr` unchanged on the RTL.
- `priv.hpp`'s fix is for every core and every CSR: it is Zicsr, not a SNAX
  rule.
- SG4's warnings go; `snax-csr`'s expected file loses its two warning lines.
- The extended `snax-csr` runs on SNAX-GVSoC only.
- The RTL reference is snax_cluster `9fbf35d` (#657), the pin in the notes.
- `make regress` checks only that each program finishes: exit 0 within its
  timeout. No exact numbers, `expected/` files, RTL references or ELF
  hashes; SG5's `expected/` and `rtl/` folders are removed.
- The comparison with the RTL (SG5's three-tier target) is made by hand, on
  demand, from fresh runs of the same ELF on both sides with
  `tests/snax/phases.py` (README, "Comparing with the RTL"). Better ways
  come with more accelerators.

## Steps

| # | Step | Status |
|---|---|---|
| 1 | Round 1: the RTL change on snax_cluster's `ry/sg6-zicsr`; `snax-csr` (four parts) and `snax-alu` at five sizes on the RTL | done 2026-10-14 |
| 2 | Round 2: `priv.hpp`, SG4's warnings removed, `snax-csr`'s part 3 extended, the regression's expected file updated; this plan | done 2026-10-14 |
| 3 | Round 3: the snax_cluster PR (#657, merged); `make regress` pass/finish only; the pin moved to `9fbf35d`; snax-forge's docs (STATUS, D120, D124) | done 2026-10-14 |
