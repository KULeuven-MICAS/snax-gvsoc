# SnaxShell's rule

GEN2b round 3 (`docs/plans/GEN2b.md`, snax-forge C§17): the rule of
`snax/snax_shell.hpp`, the code `SnaxShell` (`snax/snax_shell.cpp`) runs (the
CSRs, a start, a start held while busy, busy, the counter), against
hand-worked cases, with g++ only. `make regress` runs it after `unit`, as
`shell`. snax-forge's `ShellCasesSpec` drives vecadd's Chisel shell wrapper
(`CsrManager`, `CtrlAdapter`, `ElementwiseTiledSpatial`) through the same
files, from the folder `SNAX_GVSOC_SHELL_CASES` names, so both sides read one
set of cases.

- `tb.cpp` steps `SnaxShellRule` with `snax_unit.hpp`'s `SnaxUnitRule`, wired
  as GVSoC wires them: the shell's accepted start starts the unit with the
  fields as they stand, and the unit's busy feeds the shell (rising in the
  start's cycle, falling in the run's last cycle E). Every cycle it takes a
  held start in E + 1, then the cycle's CSR access, then the unit's step,
  and compares each access's result and the busy CSR.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/shell`) and runs
  it on every `cases/*.txt`; exit 1 on any difference.

## A case file

`#` starts a comment. Header lines, then `cycles` and one line per cycle
from cycle 0:

| Line | What |
|---|---|
| `fields NAME...` | the shell's fields, in CSR order (default `loopCount`) |
| `config ROLE...` | the unit's role of each field, `count` or `rate` (default `count`), as SnaxUnit's `config` |
| `wait`, `latency`, `ii`, `inputs` | the unit, as `tests/snax/unit/`'s cases give it (defaults lockstep, 0, 1, 2) |
| `cycles` | the cycle lines follow |

A cycle line: each input's valid and the output's ready (0 or 1), then the
cycle's CSR access, its expected result and the expected busy:

| Access | Result |
|---|---|
| `w OFFSET VALUE` | the cycle the write is answered in: its own cycle, or for a held start E + 1 |
| `r OFFSET` | the value read in that cycle |
| `-` | none: `-` |
| `.` | the write of an earlier line, still held (or answered in this cycle): `-` |

OFFSET counts from the accelerator's first CSR: the fields in order, start,
busy, counter (vecadd: `0` loopCount, `1` start, `2` busy, `3` counter);
values may be decimal or `0x` hex. One access per cycle: the core issues CSR
accesses one at a time, and a held write takes every cycle from the one it
is offered in to the one it is answered in, each written `.` after the
first. The busy column is what the busy CSR would read in that cycle,
whether or not the line reads it. The expected values are worked by hand
from the rules in `snax_shell.hpp`; each case says how in its comments.

| Case | What |
|---|---|
| `field_read_back` | a field read back as written (all 32 bits); start written with bit 0 clear reads back too |
| `start_bit0_clear` | start with bit 0 clear: a plain write, no run, the counter never reset (0) |
| `start_held` | a start while busy held through E and answered in E + 1, then its run |
| `read_busy` | busy 0 before the start, 1 from the cycle after it to E, 0 after |
| `counter` | the counter reset by an accepted start, counting busy cycles, holding after the run, reset by the next |
| `count_zero` | a start of count 0 accepted by the shell and ignored by the unit: busy stays 0, the counter is still reset |
| `start_in_last_cycle` | a start offered exactly in E: held one cycle, answered in E + 1 |
| `counter_after_start` | the counter read in the first cycle after an accepted start, taken at once and held: 0 whatever the last run counted (a read in the start's own cycle cannot happen: its write is that cycle's access) |

## Running

From snax-gvsoc's root (in the image or on any host with g++ and C++17):

    tests/snax/shell/run.sh

It prints `PASS` per case and ends with `8 passed, 0 failed`.
