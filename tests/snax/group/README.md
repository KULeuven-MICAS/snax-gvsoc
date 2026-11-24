# SnaxGroupRule's cases

The control model of a group (`snax/snax_group.hpp`'s `SnaxGroupRule`) against shared cases, with g++ only. `make regress` runs it after `datapath`, as `group`. snax-forge's Chisel specs drive a group's `<tag>_<group>_ctrl` and its datapaths through the same files, from the folder `SNAX_GVSOC_GROUP_CASES` names (as `SNAX_GVSOC_UNIT_CASES` for `tests/snax/unit/`), cycle-exact, so the format below is the contract between the two.

- `gen.py` writes `cases/*.txt` from `snax/snax_group_rule.py`, the rule in Python (over the group's edges, written from snax-forge's contract, not from the C++): it steps each case, comments each cycle with what fires, reads, holds and pushes, and checks every dot variant's busy cycles against the formulas before it writes a file (a disagreement stops it). The files are checked in; run `gen.py` again only to change them (Python 3 with numpy, for the W = 1 cases' data).
- `tb.cpp` steps `SnaxGroupRule` with each case's outer valids and readies and compares, every cycle, each unit's fire and give, each buffer's occupancy and busy, and the run line at the end of the run, whose classes must add up to the case's busy cycles. For a dot case it also runs the group's datapaths with the rule's enables (`SnaxGroupDatapaths`, the component's wiring) on int64 beats and checks each result against its job's sum: the case's own `lanes`, `data` and `sums` when it has them, else 4 lanes of the tb's own beats and their sum of products. For a seeded Mac alone it runs the Mac on 4 lanes of int8 a and b into int32, a seed of 4 int32 lanes per job, and checks each lane of each result against its job's seed plus its products; an input sliced to one lane a pop is a broadcast, its slice given to the 4 lanes by `snax_group.hpp`'s `snax_broadcast`, as `SnaxGroup` does. For a fork case of bicg's one pass (`fork_*`) it runs the three datapaths on 4 lanes of int8 A, p and r into int32, A's row on both `vmul.a` and `mac.a`, and checks each of the sum's results against its row of q = A p and the Mac's against s = Aᵀ r (r_i on every lane), each seed added when seeded; `vmul` and `mac` must fire together. For atax's one group (`atax_*`) it runs vmul, sum and the banked Mac on 4 lanes of int8 A and x, t and y int32, t over the held link into the Mac's hold register and on its 4 lanes, A on `mac.a` from its own reader or through the fork's buffer, and checks each t against its row of A x and each of the bank's rows against y = Aᵀ t.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/group`) and runs it on every `cases/*.txt`; exit 1 on any difference.

## The rule in one paragraph

A group is a graph of units whose links are edges, each a wire (depth 0) or a buffer of D beats. It is one or more chains, each from a head to a sink that owns one outer output; a fork or a join of links is refused, and chains meet only at a forked outer input. The rule:

- **Firings.** A start carries JOBS and each unit's T. Unit k fires JOBS · ∏ T_v times over itself and the units after it, gives a result on every T-th firing and pushes it L cycles later; its pipeline stalls as a whole when its head has no room.
- **Giving.** A unit gives into a wire only when the next unit takes in that cycle, into a buffer when it has room or the next unit takes.
- **Reading.** A unit reads its input in every cycle it wants to, has a beat and is not frozen. At span S (SerialAccumulate) it reads lane l in place, one a cycle, and takes the beat on lane S − 1, so a wire's producer holds its result until the last lane. At span 1 the read is its firing.
- **Seed.** A seeded unit's (a fold's, or a Mac's) job's first beat waits for its seed too (fire = a.valid and (not first or seed.valid)), and its firing takes the seed (seed.ready = fire and first).
- **Fork.** One reader gives an input to the heads of several chains; its beat is taken only when every member fires, so a member that would fire waits while another cannot (`waits for its fork` in the comments). Each chain has its own JOBS and its sink its own output; a unit fires its chain's JOBS times the T over itself and the units after it.
- **Bank and hold.** A banked unit's sums are R rows, one a firing in turn; a job of T firings (a multiple of R) gives R results on its last R firings, so the bank drains while A's last row passes. A held input's beat is needed and taken only on the firings where fired mod R = 0. A seeded bank needs and takes a seed beat on each of a job's first R firings, so row ρ starts from seed beat ρ. A held link into a bank is the same: its beat is needed and taken on those firings only, so the bank takes one result of its producer every R firings.
- **Fork buffer.** A fork may give its beat to a unit further down a chain through a buffer of depth D: its beat is taken when every member fires and the buffer has room (occupancy < D, or its consumer fires), the consumer's input has a beat while the buffer holds one, popped on each of its firings. Such a fork may have one member; the buffer joins its consumer's chain to the fork's, as a member does.
- **Busy.** The group is busy from the cycle after the start to the push of the last unit's last result (every chain's); its classes are judged at its boundary (`docs/EVENTS.md`), stall_out when any output's unit is frozen.
- **Slicer** (`snax_group.hpp`'s `SnaxSlicer`, snax-forge's `FifoSlicer`). With d_in pops to a word, the unit sees the held word, not the reader's valid; a firing (a seed's take) pops a slice and the d_in-th empties it; the slicer takes the reader's word when empty or on that last pop, only while busy, so the word shows the cycle after. The start drops what it holds.
- **Packer** (`snax_group.hpp`'s `SnaxPacker`, snax-forge's `FifoPacker`). With d_out results to a word, the slice pointer clears at the start; a push puts the result's low 64 / d_out bits at the slice; the word goes to the writer when the slice is d_out − 1 or the push is the run's last result (counted, pushes = results − 1, not this cycle's push), the slices above zero. The outer output's room is the writer's ready only on such a sending push; a filling push needs none, so no cycle is added.

## A case file

Plain text; `#` starts a comment, blank lines are skipped. Header lines, then `cycles` and one line per cycle from cycle 0:

| Line | What |
|---|---|
| `unit NAME DATAPATH latency L ii N span S t T inputs I [seed 1] [rows R] [hold J]...` | a unit, head first: its catalogue datapath, timing, T (a result every T-th firing) and number of outer inputs; `seed 1`, the last of them a fold's seed (one beat per job: its job's first beat waits for it, its first firing takes it); `rows R`, a bank: a job gives R results, one on each of its last R firings, and its first R firings start each row (a seed taken on each); `hold J`, its outer input J read once every R firings and kept |
| `link FROM TO depth D [hold]` | an edge from unit FROM's output to unit TO's input after its outer ones and its fork buffers', before its seed (a chain: one fewer than its units): 0 a wire, >= 1 a buffer; `hold`, a buffer into a bank taken once a row; the occupancy columns follow the links' order |
| `fork U.I U.I ...` | optional: outer input I (0-based among unit U's own) of each unit listed is one reader's, its `V` column once, at the first member's place |
| `forkbuf F TO depth D` | optional: fork F's (0-based, the `fork` lines' order) beat through a buffer of depth D into unit TO's input after its outer ones; its occupancy column after the links' |
| `outputs U...` | with several chains: their sinks, in the order of the `jobs` values and the `R` columns |
| `jobs J...` | the start's JOBS, one per output (`JOBS_<sink>` with several chains) |
| `start CYCLE taken\|ignored\|refused` | the start, offered in that cycle, and its expected answer |
| `expect run index=I firings=F busy=B stall_in=SI stall_out=SO flush=FL` | the run line expected at the end of run I (`firings` the head's) |
| `lanes L` | optional, with the next two: the lanes of the case's own data |
| `data a\|b V...` | the head's input a or b, element i * L + l lane l of the beat it fires i-th, signed decimal int64 |
| `sums S...` | each job's expected result, in push order (JOBS of them) |
| `dout D` | optional: the outer output packed D results to a 64-bit word (2, 4 or 8), the cycle lines then with a `sent` column |
| `words W...` | with `dout`: the words the packer sends, in order (hex), push n's result taken as -(n + 1) so each slice shows |
| `din I D` | optional, one per sliced input: outer input I (0-based, the order of the `V` columns) through a slicer of D pops a word (2, 4 or 8), its `V` column then its reader's valid and the cycle lines with a `took` column |
| `cycles` | the cycle lines follow |

A cycle line is `V... R | F G | F G ... | O... | B`:

- `V... R...`: the outer inputs' valid, unit by unit in port order (a seeded unit's seed last among its own, a forked input once), then each outer output's ready;
- `F G` per unit: whether it fires (takes its input beat) and gives (pushes a result into its link or the outer output);
- `O...`: per buffer its occupancy after the cycle (absent when every link is a wire);
- `T...`, with `din`: per sliced input, whether its slicer took a word from the reader;
- `S`, with `dout`: whether a word went to the writer;
- `B`: busy.

The rule is stepped only in busy cycles, each unit's outer valids ANDed, a seed's apart.

## The cases

| Case | What |
|---|---|
| `dot<v>_n<N>_j<J>` | dot variant v = 2 to 6 at W = 4, N = 8 (T = 2) and N = 16 (T = 4), JOBS 1 and 2: dot 2 SimdLanes mul (L 0, T 1) -> buffer of depth 1 -> TreeAccumulate sum (L 1, T = N / W); dot 3 the same with a wire; dot 4 Mac (accumulate, L 1, T = N / W) -> wire -> TreeAccumulate (L 1, T 1); dot 5 Mac -> wire -> SerialAccumulate (L 1, span 4, T 1); dot 6 Mac -> buffer of depth 1 -> SerialAccumulate |
| `dot4_backpressure` | dot 4, T = 2, JOBS 2, the writer not ready for two cycles: the sum's head held (stall_out), the MAC's result behind it |
| `dot6_input_gap` | dot 6, T = 4, JOBS 2, reader a without a beat for a cycle: stall_in |
| `dot5_w1_j2`, `dot6_w1_j2` | dot 5 and dot 6 at W = 1, T = 4, JOBS 2: SerialAccumulate at span 1, which reads (and fires) once per beat; random int64 data (numpy, seeded) and each job's sum from numpy |
| `dot4_jobs0` | dot 4 with JOBS 0: the empty run, ignored, busy never rises |
| `seed_none`, `seed_first`, `seed_both` | the fold's seed: acc (TreeAccumulate, T 2) -> wire -> sum (TreeAccumulate, T 2), JOBS 2, neither, the first or both seeded, every seed there from the start: the same cycles all three (gen.py checks it) |
| `seed_late` | matvec_acc_v1's sum alone (TreeAccumulate, T 4, JOBS 2), its seed missing in cycles 1 to 3 and 8 to 9: each job's first beat waits for it (stall_in), the job's other beats do not |
| `pack_d<D>_j<J>` | sum (TreeAccumulate, T 2) alone, its result packed D = 2, 4, 8 to a word (int32, int16, int8 results), JOBS 1 (one short word), 9 (a short last word) and 10 (whole words at D 2) |
| `pack_d2_backpressure` | the same at D 2, JOBS 4, the writer not ready in cycles 3 to 5: the filling push goes ahead, the sending one waits (stall_out) |
| `pack_dot3_d2_j3` | dot 3 (T 2) at D 2, JOBS 3: one whole word, then a short one on the last push; the dot product checked as the other dot cases |
| `slice_d<D>_j<J>` | sum (TreeAccumulate, T 2) alone, its input sliced D = 2, 4, 8 (int32, int16, int8 lanes), JOBS 3 (whole words at D 2, a short last word at D 4) and 2 (four pops of one word at D 8): the first pop a cycle after the take, then no gap |
| `slice_d2_reader_gap`, `slice_d2_backpressure` | the same at D 2, JOBS 3: the reader without a word in cycles 3 to 5 (stall_in), or the writer not ready in cycles 4 to 6 (stall_out, the slicer keeps its word) |
| `slice_seed_d2` | matvec_acc_v1's sum (TreeAccumulate, T 4, JOBS 3), its seed sliced 2: one seed word serves two jobs |
| `slice_dot3_d2_j2` | dot 3 (T 2), JOBS 2, a and b sliced 2 and the sum packed 2: matvec_v3's form at int8, W = 4, one cycle after `pack_dot3` |
| `seed_serial_late` | Mac (T 2) -> wire -> SerialAccumulate (span 4, seeded, T 1), JOBS 2, the seed missing in cycles 1 to 4 and 7: the sum reads its job's first beat lane by lane only while its seed is there, the Mac holds its result |
| `seed_mac_late` | a seeded Mac alone (T 4, JOBS 2; its seed of its output's lanes), the seed missing in cycles 1 to 3 and 6 to 7: each job's first beat waits for it, its other beats do not |
| `fork_d1_m4`, `fork_d0_m4` | bicg's one pass at N = W, M = 4: vmul (SimdLanes) -> a buffer of depth 1 or a wire -> sum (TreeAccumulate, T 1, JOBS 4) gives q, mac (Mac, T 4, JOBS 1) gives s, A forked to vmul.a and mac.a: with every input there, the longer chain's cycles alone |
| `fork_r_late`, `fork_p_late`, `fork_a_late` | the same at depth 1 with r (mac.b) missing in cycles 2 and 3, p in cycle 3, or A in cycles 2 and 3: the member with its input waits for its fork (stall_in) |
| `fork_q_backpressure`, `fork_s_backpressure` | q's writer not ready in cycles 2 to 4 (sum holds, the buffer fills, mac waits for its fork) or s's in cycles 5 to 7 (mac holds its one result, q's chain drains) |
| `fork_seeded` | mvt's one pass: sum seeded per row (x1), mac seeded once (x2), mac's seed missing in cycles 1 and 2: vmul waits for its fork |
| `bank_r2_m3`, `bank_r2_r_late`, `bank_r2_s_backpressure` | a Mac with a bank of 2 rows and r held, M = 3: the bank's two results on the job's last two firings; r missing on a row's second firing (no wait) and first (a wait); s's writer not ready, the next job's beats waiting while the bank holds |
| `bank_fork_strips2` | bicg's one pass in 2 strips, M = 3, ROWS = 2: q's sum seeded from q every row (JOBS 6), the banked Mac (JOBS 2), A forked; each strip's s on its last row |
| `bank_seed_r2`, `bank_seed_r4` | a Mac with a seeded bank of 2 rows (M = 3, JOBS 2) and 4 rows (M = 2, JOBS 1), b held: each job's first ROWS firings take a seed beat, one a row |
| `bank_seed_r4_late` | the seeded bank of 4 rows, M = 2, JOBS 2, its seed missing in cycles 2 to 3, 7 and 10 to 11: a job's first ROWS firings wait for their seed beat (stall_in), a later one does not |
| `atax_hold_link`, `atax_hold_link_a_late` | atax's one group, A read twice, M = 3, ROWS = 2: vmul (SimdLanes) -> a buffer -> sum (TreeAccumulate, T 2) gives t[i] -> a held buffer -> mac's bank (T 6); then mac's A missing in cycles 6 to 8, t[1] in the buffer while row 0 still runs on the t[0] it holds |
| `atax_fork_buffer_d4`, `atax_fork_buffer_d2` | the same with A forked to vmul and through a buffer of depth 4 (T + 2, full rate) or 2 (T, 2 cycles a row of stall: vmul waits for its fork) to mac |
| `atax_fork_buffer_two_chains` | atax's one pass before t's link, M = 3, ROWS = 2: sum's chain gives t (JOBS 3), mac's reads it from L1, held a row (JOBS 1); A forked to vmul and through a buffer of depth 4 to mac, which joins the two chains |
| `bank_fork_seeded` | mvt's one pass at M = 3, ROWS = 2: x1's sum seeded per row (JOBS 3), x2's seeded bank (JOBS 1), y2 held, A forked, x2's seed missing in cycle 2: vmul waits for its fork |
| `slice_mac_bcast_d8` | a seeded Mac alone (T 4, JOBS 2), its b sliced 8 and broadcast: mvt's half 2 at int8; the broadcast is wires, so the rule sees the slicer only |

Their busy cycles E - s, as snax-forge's contract gives them (its Cycles table, and the formulas C2 = JT + 2, C3 = JT + 1, C4 = JT + 2, C5 = J(T + W - 1) + 2, C6 = (J - 1) max(T, W) + T + W + 2):

| T, J | dot 2 | dot 3 | dot 4 | dot 5 | dot 6 |
|---|---|---|---|---|---|
| 2, 1 | 4 | 3 | 4 | 7 | 8 |
| 2, 2 | 6 | 5 | 6 | 12 | 12 |
| 4, 1 | 6 | 5 | 6 | 9 | 10 |
| 4, 2 | 10 | 9 | 10 | 16 | 14 |

## Running

    tests/snax/group/run.sh

It prints `PASS` per case (`, data` where the dot product, the seeded Mac's sums, a fork case's q and s or a bank's rows, r held a row and each row's seed beat when seeded, are checked too) and ends with `66 passed, 0 failed`.
