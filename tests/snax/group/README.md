# SnaxGroupRule's cases

The control model of a group (`snax/snax_group.hpp`'s `SnaxGroupRule`, snax-forge C§17's Control) against shared cases, with g++ only. `make regress` runs it after `datapath`, as `group`. snax-forge's Chisel specs drive a group's `<tag>_<group>_ctrl` and its datapaths through the same files, from the folder `SNAX_GVSOC_GROUP_CASES` names (as `SNAX_GVSOC_UNIT_CASES` for `tests/snax/unit/`), cycle-exact, so the format below is the contract between the two.

- `gen.py` writes `cases/*.txt` from `snax/snax_group_rule.py`, C§17's rule in Python (over the group's edges, written from C§17, not from the C++): it steps each case, comments each cycle with what fires, reads, holds and pushes, and checks every dot variant's busy cycles against C§17's formulas before it writes a file (a disagreement stops it). The files are checked in; run `gen.py` again only to change them (Python 3 with numpy, for the W = 1 cases' data).
- `tb.cpp` steps `SnaxGroupRule` with each case's outer valids and ready and compares, every cycle, each unit's fire and give, each buffer's occupancy and busy, and the run line at the end of the run, whose classes must add up to the case's busy cycles. For a dot case it also runs the group's datapaths with the rule's enables (`SnaxGroupDatapaths`, the component's wiring) on int64 beats and checks each result against its job's sum: the case's own `lanes`, `data` and `sums` when it has them, else 4 lanes of the tb's own beats and their sum of products.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/group`) and runs it on every `cases/*.txt`; exit 1 on any difference.

## The rule in one paragraph

A group is a graph of units whose links are edges, each a wire (depth 0) or a buffer of D beats; until tier A it is one chain (a fork or a join is refused). A start carries JOBS and each unit's T; unit k fires JOBS * prod T_v times over itself and the units after it, gives a result on every T-th firing and pushes it L cycles later, its pipeline stalling as a whole when its head has no room. A unit gives into a wire only when the next unit takes in that cycle, into a buffer when it has room or the next unit takes; a unit reads its input in every cycle it wants to, has a beat and is not frozen: at span S (SerialAccumulate) lane l in place, one a cycle, taking the beat on lane S - 1, so a wire's producer holds its result until the last lane; at span 1 the read is its firing. A seeded fold's job's first beat waits for its seed too (fire = a.valid and (not first or seed.valid)), and its firing takes the seed (seed.ready = fire and first). The group is busy from the cycle after the start to the push of the last unit's last result; its classes are judged at its boundary (docs/EVENTS.md).

## A case file

Plain text; `#` starts a comment, blank lines are skipped. Header lines, then `cycles` and one line per cycle from cycle 0:

| Line | What |
|---|---|
| `unit NAME DATAPATH latency L ii N span S t T inputs I [seed 1]` | a unit, head first: its catalogue datapath, timing, T (a result every T-th firing) and number of outer inputs; `seed 1`, the last of them a fold's seed (one beat per job: its job's first beat waits for it, its first firing takes it) |
| `link FROM TO depth D` | an edge from unit FROM's output to unit TO's input after its outer ones (a chain: one fewer than the units): 0 a wire, >= 1 a buffer; the occupancy columns follow the links' order |
| `jobs J` | the start's JOBS |
| `start CYCLE taken\|ignored\|refused` | the start, offered in that cycle, and its expected answer |
| `expect run index=I firings=F busy=B stall_in=SI stall_out=SO flush=FL` | the run line expected at the end of run I (`firings` the head's) |
| `lanes L` | optional, with the next two: the lanes of the case's own data |
| `data a\|b V...` | the head's input a or b, element i * L + l lane l of the beat it fires i-th, signed decimal int64 |
| `sums S...` | each job's expected result, in push order (JOBS of them) |
| `cycles` | the cycle lines follow |

A cycle line: `V... R | F G | F G ... | O... | B`: the outer inputs' valid, unit by unit in port order (a seeded unit's seed last among its own), and the outer output's ready; per unit whether it fires (takes its input beat) and gives (pushes a result into its link or the outer output); per buffer its occupancy after the cycle (the column is absent when every link is a wire); busy. The rule is stepped only in busy cycles, each unit's outer valids ANDed, a seed's apart.

## The cases

| Case | What |
|---|---|
| `dot<v>_n<N>_j<J>` | dot variant v = 2 to 6 at W = 4, N = 8 (T = 2) and N = 16 (T = 4), JOBS 1 and 2: dot 2 SimdLanes mul (L 0, T 1) -> buffer of depth 1 -> TreeAccumulate sum (L 1, T = N / W); dot 3 the same with a wire; dot 4 Mac (accumulate, L 1, T = N / W) -> wire -> TreeAccumulate (L 1, T 1); dot 5 Mac -> wire -> SerialAccumulate (L 1, span 4, T 1); dot 6 Mac -> buffer of depth 1 -> SerialAccumulate |
| `dot4_backpressure` | dot 4, T = 2, JOBS 2, the writer not ready for two cycles: the sum's head held (stall_out), the MAC's result behind it |
| `dot6_input_gap` | dot 6, T = 4, JOBS 2, reader a without a beat for a cycle: stall_in |
| `dot5_w1_j2`, `dot6_w1_j2` | dot 5 and dot 6 at W = 1, T = 4, JOBS 2: SerialAccumulate at span 1, which reads (and fires) once per beat; random int64 data (numpy, seeded) and each job's sum from numpy |
| `dot4_jobs0` | dot 4 with JOBS 0: the empty run, ignored, busy never rises |
| `seed_none`, `seed_first`, `seed_both` | the fold's seed (snax-forge B2 R5, D149): acc (TreeAccumulate, T 2) -> wire -> sum (TreeAccumulate, T 2), JOBS 2, neither, the first or both seeded, every seed there from the start: the same cycles all three (gen.py checks it) |
| `seed_late` | matvec_seed's sum alone (TreeAccumulate, T 4, JOBS 2), its seed missing in cycles 1 to 3 and 8 to 9: each job's first beat waits for it (stall_in), the job's other beats do not |
| `seed_serial_late` | Mac (T 2) -> wire -> SerialAccumulate (span 4, seeded, T 1), JOBS 2, the seed missing in cycles 1 to 4 and 7: the sum reads its job's first beat lane by lane only while its seed is there, the Mac holds its result |

Their busy cycles E - s, as C§17's Cycles table (and the formulas C2 = JT + 2, C3 = JT + 1, C4 = JT + 2, C5 = J(T + W - 1) + 2, C6 = (J - 1) max(T, W) + T + W + 2) gives them:

| T, J | dot 2 | dot 3 | dot 4 | dot 5 | dot 6 |
|---|---|---|---|---|---|
| 2, 1 | 4 | 3 | 4 | 7 | 8 |
| 2, 2 | 6 | 5 | 6 | 12 | 12 |
| 4, 1 | 6 | 5 | 6 | 9 | 10 |
| 4, 2 | 10 | 9 | 10 | 16 | 14 |

## Running

    tests/snax/group/run.sh

It prints `PASS` per case (`, data` where the dot product is checked too) and ends with `30 passed, 0 failed`.
