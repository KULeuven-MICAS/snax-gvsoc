# SnaxUnit's rule

GEN3 step 1 (`docs/plans/GEN3.md`): the cycle rule and the op table of
`snax/snax_unit.hpp`, the code `SnaxUnit` (`snax/snax_unit.cpp`) runs,
against hand-worked cases, with g++ only. `make regress` runs it first, as
`unit`.

- `tb.cpp` drives the rule cycle by cycle from a case file and compares,
  every cycle, whether it fires, pushes and is busy, each start's answer,
  and the trace line at the end of every run (`SnaxUnitRule::run_line`, the
  line the component prints), whose busy, stall_in, stall_out and flush must
  add up to the run's busy cycles in the case file. It also checks the op table on fixed vectors
  (wrapping at 8 to 64 bits, signed and unsigned min and max).
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/unit`) and runs
  it on every `cases/*.txt`; exit 1 on any difference.

## A case file

`#` starts a comment. Header lines, then `cycles` and one line per cycle
from cycle 0:

| Line | What |
|---|---|
| `wait lockstep\|pipelined` | the rule (default lockstep) |
| `latency L`, `ii N` | pipelined only (defaults 0 and 1) |
| `inputs N` | input columns (default 2) |
| `start CYCLE COUNT taken\|ignored\|refused` | a start offered in that cycle (before the cycle's step), and its expected answer |
| `expect run I: firings F busy B stall_in SI stall_out SO flush FL` | the trace line expected at the end of run I, in order |
| `like FILE` | run FILE (beside this one) with this file's `wait`, `latency` and `ii` instead of its own; one run per `like` |
| `cycles` | the cycle lines follow |

A cycle line: each input's valid, the output's ready (room), then the
expected fire, push and busy, all 0 or 1. The rule is stepped only in busy
cycles, with every input valid ANDed. The expected values are worked by
hand from the rules in `snax_unit.hpp`; each case says how in its comments.

| Case | What |
|---|---|
| `lockstep_no_stalls` | four firings back to back; a start in the run's last cycle refused, one in the next cycle taken |
| `lockstep_input_missing` | a or b or both missing: stall_in |
| `lockstep_out_not_ready` | no room: stall_out; no room and an input missing: stall_in |
| `lockstep_count_zero` | a start with count 0 ignored, busy stays 0 |
| `pipelined_l2_backpressure` | L = 2: the pipeline freezes on a full head with no room, results in flight after the last firing (flush, but a frozen cycle: stall_out) |
| `pipelined_ii2` | L = 1, II 2: the II gap is busy, with or without inputs; one flush cycle |
| `pipelined_l0` | every lockstep case again as pipelined with L = 0, II 1, its expectations unchanged |

## Running

From snax-gvsoc's root (in the image or on any host with g++ and C++17):

    tests/snax/unit/run.sh

It prints `PASS` per case (and `ops`) and ends with `11 passed, 0 failed`.
