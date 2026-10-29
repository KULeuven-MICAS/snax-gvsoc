# SnaxShell's rule

The rule of `snax/snax_shell.hpp`, the code `SnaxShell` (`snax/snax_shell.cpp`) runs for one group of an accelerator (snax-forge C§17, D146: START, JOBS, the units' read-write CSRs, STATUS, COUNTER; a start, a start held while busy, the empty run, the sticky done bit, the counter), against hand-worked cases, with g++ only. `make regress` runs it after `unit`, as `shell`. snax-forge's Chisel specs drive their shell through the same files, from the folder `SNAX_GVSOC_SHELL_CASES` names, so both sides read one set of cases and the format below is the contract between the two.

- `tb.cpp` steps `SnaxShellRule` with `snax_group.hpp`'s `SnaxUnitRule` (a group of one unit), wired as GVSoC wires them: the shell's accepted start, but the empty run, starts the unit with JOBS and JOB_BEATS as they stand, and the unit's busy feeds the shell (rising in the start's cycle, falling in the run's last cycle E). Every cycle it takes a held start in E + 1, then the cycle's CSR access, then the unit's step, and compares each access's result and STATUS.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/shell`) and runs it on every `cases/*.txt`; exit 1 on any difference.

## A case file

Plain text; `#` starts a comment, blank lines are skipped. Header lines, then `cycles` and one line per cycle from cycle 0:

| Line | What |
|---|---|
| `csrs START JOBS [NAME...]` | the group's read-write CSRs in CSR order (default `START JOBS`); `JOB_BEATS` among them is the fold's job_beats, otherwise 1 |
| `latency`, `ii`, `inputs` | the unit, as `tests/snax/unit/`'s cases give it (defaults 0, 1, 2) |
| `cycles` | the cycle lines follow |

The offsets follow from `csrs`: its names from 0 in order, then STATUS, then COUNTER (the default: `0` START, `1` JOBS, `2` STATUS, `3` COUNTER, vecadd's group; with `JOB_BEATS`: `2` JOB_BEATS, `3` STATUS, `4` COUNTER, vsum's).

A cycle line: each input's valid and the output's ready (0 or 1), then the cycle's CSR access, its expected result and the expected STATUS:

| Access | Result |
|---|---|
| `w OFFSET VALUE` | the cycle the write is answered in: its own cycle, or for a held start E + 1 |
| `r OFFSET` | the value read in that cycle |
| `-` | none: `-` |
| `.` | the write of an earlier line, still held (or answered in this cycle): `-` |

Values may be decimal or `0x` hex. One access per cycle: the core issues CSR accesses one at a time, and a held write takes every cycle from the one it is offered in to the one it is answered in, each written `.` after the first. The STATUS column is what STATUS would read in that cycle, whether or not the line reads it: bit 0 busy (from the cycle after the accepted start to E), bit 1 done (from E + 1, an empty run's from a + 1, until the cycle after the next accepted start), so 0, 1 or 2. The expected values are worked by hand from the rules in `snax_shell.hpp`; each case says how in its comments.

| Case | What |
|---|---|
| `field_read_back` | JOBS read back as written (all 32 bits); START written with bit 0 clear reads back too |
| `start_bit0_clear` | START with bit 0 clear: a plain write, no run, the counter never reset (0) |
| `start_held` | a start while busy held through E and answered in E + 1, then its run |
| `read_busy` | STATUS 0 before the start, 1 from the cycle after it to E, 2 (done) after |
| `counter` | the counter reset by an accepted start, counting busy cycles, holding after the run, reset by the next |
| `count_zero` | a start with JOBS 0 after a run: the empty run, no busy cycle, the counter reset, done still set |
| `start_in_last_cycle` | a start offered exactly in E: held one cycle, answered in E + 1 |
| `counter_after_start` | the counter read in the first cycle after an accepted start, taken at once and held: 0 whatever the last run counted (a read in the start's own cycle cannot happen: its write is that cycle's access) |
| `status_sticky` | done set at E + 1, kept through writes to JOBS and to START with bit 0 clear, cleared by the next accepted start |
| `jobs_zero` | a fold group (with JOB_BEATS): a start with JOBS 0, then one with JOB_BEATS 0 after a run: STATUS 2 from a + 1, COUNTER 0 |

## Running

From snax-gvsoc's root (in the image or on any host with g++ and C++17):

    tests/snax/shell/run.sh

It prints `PASS` per case and ends with `10 passed, 0 failed`.
