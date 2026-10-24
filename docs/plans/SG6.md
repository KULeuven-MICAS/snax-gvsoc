# SG6 plan: Zicsr on SNAX CSRs

SG6 is the sixth task of M16 in snax-forge, after SG5. Every CSR instruction
on snax_cluster's SNAX CSRs (0x3C0 to 0x5FF) does what Zicsr says, on the RTL
and on SNAX-GVSoC; SG4's two CSR-form warnings go. Acceptance: `snax-csr`
covers every form and passes on SNAX-GVSoC, its original four parts pass on
the RTL, and nothing else moves (`snax-alu` against SG5's RTL tables,
`make regress`). Closed 2026-10-14; the log is `docs/notes/NOTES.md` (SG6
steps 1 to 3).

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

## The RTL change (round 1)

snax_cluster `9fbf35d` (#657, from `ry/sg6-zicsr`):

- `hw/snitch/src/snitch.sv`: `csrrw` / `csrrwi` with `rd` not `x0` take
  `rd` from the accelerator's response; `csrrs` / `csrrc` send `rs1`,
  `csrrsi` / `csrrci` the `uimm`, as the mask.
- `hw/snax_util/src/snax_intf_translator.sv`: the read-then-write forms go
  out as a read, then a write from latched address and mask, accepted only
  when no older read is outstanding; `csrw` and `csrr` keep their handshake
  and timing.

## The GVSoC change (round 2)

- `core/models/cpu/iss/include/isa/priv.hpp`: `csrrc` with `rs1` = `x0` and
  `csrrsi` / `csrrci` with 0 write nothing, for every core; a row in
  `UPSTREAM.md`.
- `SnaxCsr::handle()` and `Iss::snax_csr_access()` lose SG4's warnings.
- Left: upstream's generic `csrrw` / `csrrwi` path reads with `rd` = `x0`
  too; SNAX CSRs go through `SnaxCsr::handle()`, which does not.

## Steps

All done 2026-10-14: round 1, the RTL change, after which `snax-csr`'s four
parts print four lines of `0 errors` on the RTL (17 and 20 errors before)
and `snax-alu` at five sizes equals SG5's tables; round 2, `priv.hpp`, SG4's
warnings removed, `snax-csr`'s part 3 extended (110 accesses, no warning);
round 3, the snax_cluster PR (#657, merged), `make regress` pass/finish
only, the pin moved to `9fbf35d`, snax-forge's docs (STATUS, D120, D124).

## Decided

- Both sides follow Zicsr on SNAX CSRs; the RTL is fixed in snax_cluster,
  not modelled here.
- `priv.hpp`'s fix is for every core and every CSR: it is Zicsr, not a SNAX
  rule. A static scan of the 31 ELFs `make regress` ran found the no-write
  forms in `snax-csr` only.
- The extended `snax-csr` runs on SNAX-GVSoC only.
- `make regress` checks only that each program finishes: exit 0 within its
  timeout. No exact numbers, expected files, RTL references or ELF hashes.
- The comparison with the RTL (SG5's three-tier target) is made by hand, on
  demand, from fresh runs of the same ELF on both sides.
