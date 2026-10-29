# SnaxGroupRule's cases

The control model of a group (`snax/snax_group.hpp`'s `SnaxGroupRule`, snax-forge C§17's Control) against shared cases, with g++ only. `make regress` runs it after `datapath`, as `group`. snax-forge's Chisel specs (F2) drive a group's `<tag>_<group>_ctrl` and its datapaths through the same files, from the folder `SNAX_GVSOC_GROUP_CASES` names (as `SNAX_GVSOC_UNIT_CASES` for `tests/snax/unit/`), cycle-exact, so the format below is the contract between the two.

- `gen.py` writes `cases/*.txt` from a model of C§17's rule written in Python, not from the C++: it steps each case, comments each cycle with what fires, reads, holds and pushes, and checks every dot variant's busy cycles against C§17's formulas before it writes a file (a disagreement stops it). The files are checked in; run `gen.py` again only to change them (any Python 3).
- `tb.cpp` steps `SnaxGroupRule` with each case's outer valids and ready and compares, every cycle, each unit's fire and give, each buffer's occupancy and busy, and the run line at the end of the run, whose classes must add up to the case's busy cycles. For a dot case it also runs the group's datapaths with the rule's enables (`SnaxGroupDatapaths`, the component's wiring) on int64 beats at 4 lanes and checks each result against its job's sum of products.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/group`) and runs it on every `cases/*.txt`; exit 1 on any difference.

## The rule in one paragraph

A group is a chain of units, head first, each link a wire (depth 0) or a buffer of D beats. A start carries JOBS and each unit's T; unit k fires JOBS * prod T_v times over itself and the units after it, gives a result on every T-th firing and pushes it L cycles later, its pipeline stalling as a whole when its head has no room. A unit gives into a wire only when the next unit takes in that cycle, into a buffer when it has room or the next unit takes; a unit of span S (SerialAccumulate) reads lane l of its input in place, one a cycle, and takes the beat on lane S - 1, so a wire's producer holds its result until the last lane. The group is busy from the cycle after the start to the push of the last unit's last result; its classes are judged at its boundary (docs/EVENTS.md).

## A case file

Plain text; `#` starts a comment, blank lines are skipped. Header lines, then `cycles` and one line per cycle from cycle 0:

| Line | What |
|---|---|
| `unit NAME DATAPATH latency L ii N span S t T inputs I` | a unit, head first: its catalogue datapath, timing, T (a result every T-th firing) and number of outer inputs |
| `link FROM TO depth D` | the link from one unit to the next (one fewer than the units, in order): 0 a wire, >= 1 a buffer |
| `jobs J` | the start's JOBS |
| `start CYCLE taken\|ignored\|refused` | the start, offered in that cycle, and its expected answer |
| `expect run index=I firings=F busy=B stall_in=SI stall_out=SO flush=FL` | the run line expected at the end of run I (`firings` the head's) |
| `cycles` | the cycle lines follow |

A cycle line: `V... R | F G | F G ... | O... | B`: the outer inputs' valid, unit by unit in port order, and the outer output's ready; per unit whether it fires (takes its input beat) and gives (pushes a result into its link or the outer output); per buffer its occupancy after the cycle (the column is absent when every link is a wire); busy. The rule is stepped only in busy cycles, each unit's outer valids ANDed.

## The cases

| Case | What |
|---|---|
| `dot<v>_n<N>_j<J>` | dot variant v = 2 to 6 at W = 4, N = 8 (T = 2) and N = 16 (T = 4), JOBS 1 and 2: dot 2 ElementwiseLanes mul (L 0, T 1) -> buffer of depth 1 -> TreeAccumulate sum (L 1, T = N / W); dot 3 the same with a wire; dot 4 Mac (accumulate, L 1, T = N / W) -> wire -> TreeAccumulate (L 1, T 1); dot 5 Mac -> wire -> SerialAccumulate (L 1, span 4, T 1); dot 6 Mac -> buffer of depth 1 -> SerialAccumulate |
| `dot4_backpressure` | dot 4, T = 2, JOBS 2, the writer not ready for two cycles: the sum's head held (stall_out), the MAC's result behind it |
| `dot6_input_gap` | dot 6, T = 4, JOBS 2, reader a without a beat for a cycle: stall_in |
| `dot4_jobs0` | dot 4 with JOBS 0: the empty run, ignored, busy never rises |

Their busy cycles E - s, as C§17's Cycles table (and the formulas C2 = JT + 2, C3 = JT + 1, C4 = JT + 2, C5 = J(T + W - 1) + 2, C6 = (J - 1) max(T, W) + T + W + 2) gives them:

| T, J | dot 2 | dot 3 | dot 4 | dot 5 | dot 6 |
|---|---|---|---|---|---|
| 2, 1 | 4 | 3 | 4 | 7 | 8 |
| 2, 2 | 6 | 5 | 6 | 12 | 12 |
| 4, 1 | 6 | 5 | 6 | 9 | 10 |
| 4, 2 | 10 | 9 | 10 | 16 | 14 |

## Running

    tests/snax/group/run.sh

It prints `PASS` per case (`, data` where the dot product is checked too) and ends with `23 passed, 0 failed`.
