# The rule of one unit

The cycle rule of one unit (`snax/snax_group.hpp`'s `SnaxGroupRule` with one unit and no links, as `SnaxGroup` (`snax/snax_group.cpp`) runs a group of one unit) against hand-worked cases, with g++ only; the arithmetic of `snax/snax_types.hpp` is checked once, by `tests/snax/datapath/`. `make regress` runs it first, as `unit`. snax-forge's Chisel specs drive its nest controller and datapaths through the same files (`SNAX_GVSOC_UNIT_CASES`), so the format below is the contract between the two.

- `tb.cpp` drives the rule cycle by cycle from a case file and compares, every cycle, whether it fires, pushes and is busy, each start's answer, and the summary line at the end of every run (`SnaxGroupRule::run_line`, the line the component prints), whose busy, stall_in, stall_out and flush must add up to the run's busy cycles in the case file. A case with `types` also computes each firing's result from its beat, as the component does, and compares every pushed result.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/unit`) and runs it on every `cases/*.txt`; exit 1 on any difference.

## The rule in one line

A start carries jobs J and job_beats T: the run fires J * T times, a result every T-th firing, with latency L and initiation interval II (L = 0, II 1 is lockstep: fire when every input has a beat and the output has room, push in the same cycle). J or T 0 is the empty run: the unit ignores the start (the shell ends that run itself).

## A case file

Plain text; `#` starts a comment, blank lines are skipped. Header lines, in any order, then `cycles` and one line per cycle from cycle 0:

| Line | What |
|---|---|
| `latency L`, `ii N` | the unit's L >= 0 and II >= 1 (defaults 0 and 1) |
| `inputs N` | input columns: 2 (an elementwise op) or 1 (a fold, or with `k` an elementwise op on one input); default 2 |
| `lanes W` | input lanes (default 1): a fold's tree, or the op's lanes; only the data uses it |
| `start CYCLE J T taken\|ignored\|refused` | a start offered in that cycle (before the cycle's step) with jobs J and job_beats T, and its expected answer |
| `expect run index=I firings=F busy=B stall_in=SI stall_out=SO flush=FL` | the summary line expected at the end of run I, in order (`docs/EVENTS.md`) |
| `types IN... OUT` | optional: each input's and the output's NumPy integer type (`int8` .. `uint64`); with it the data below is checked |
| `op NAME` | the op with `types`: add, sub, mul, and, or, xor, min, max (default add), or axpby (two inputs, `k1 * a + k2 * b`) |
| `fold tree\|lanes` | a one-input fold's form with `types`: `tree` (the default) sums each beat's lanes into one result, `lanes` (snax-forge's LaneAccumulate) keeps each lane's own sum, W results per push |
| `k V` | one input's constant (decimal): the case is a one-stream SimdLanes, each lane op(a, k) at the input's type, W results per push |
| `k1 V [csr]`, `k2 V [csr]` | axpby's k1 (required) and k2 (optional; none: `+ b`), decimal; with `csr` the slot is read from its CSR (K1, K2), V the value the program wrote, sent with each start, otherwise baked; each lane `k1 * a + k2 * b` at the inputs' result type, wrapping, W results per push |
| `beat N V...` | the input lanes of the case's N-th firing (from 0, over every run): W values per input, input 0 first |
| `result N V...` | the case's N-th pushed result: W values for an elementwise op, one for a fold |
| `cycles` | the cycle lines follow |

A cycle line: each input's valid, the output's ready (room), then the expected fire, push and busy, all 0 or 1. The rule is stepped only in busy cycles, with every input valid ANDed. Values are decimal or `0x` hex, taken modulo their type's width. An elementwise result is the op at the inputs' NumPy result type, cast to the output's; a fold casts each lane to the output's type, sums them through its tree (`fold lanes`: each lane on its own), and starts a result on each job's first firing. The expected values are worked by hand from the rules in `snax_group.hpp` and `snax_types.hpp`; each case says how in its comments.

| Case | What |
|---|---|
| `lockstep_no_stalls` | L = 0, II 1: four firings back to back; a start in the run's last cycle refused, one in the next cycle taken |
| `lockstep_input_missing` | L = 0, II 1: a or b or both missing: stall_in |
| `lockstep_out_not_ready` | L = 0, II 1: no room: stall_out; no room and an input missing: stall_in |
| `pipelined_l2_backpressure` | L = 2: the pipeline freezes on a full head with no room, results in flight after the last firing (flush, but a frozen cycle: stall_out) |
| `pipelined_ii2` | L = 1, II 2: the II gap is busy, with or without inputs; one flush cycle |
| `pipelined_rate_t4` | a fold at L = 1, II 1, J = 2, T = 4 (TreeAccumulate at T = 4, n = 8): a result every fourth firing, the next input taken as it leaves; a start in the last cycle refused, the next run in the cycle after |
| `pipelined_rate_backpressure` | the same with no room: a waiting result freezes the pipeline (stall_out), an empty head needs no room |
| `pipelined_rate_one` | T = 1: every firing a result, pushed while the next input is taken |
| `pipelined_tree_tn` | a fold over 4 lanes at J = 1, T = 8: one sum per run, a missing input (stall_in) and a sum with no room (stall_out) |
| `pipelined_tree_t4` | a fold over 4 lanes at J = 2: T = 4 with the first sum waiting for room, then T = 2 |
| `empty_run` | jobs 0, job_beats 0 and both: ignored, busy stays 0; a run between them as usual. The only case of the empty run: it is ignored at any L and II |
| `relu_one_stream` | relu's one-stream SimdLanes (op max, k 0) at W = 4, int32, N = 8: JOBS = 2, T = 1, L = 0; A = (-3, 5, 0, -1 \| 7, -8, 2, -2) gives B = (0, 5, 0, 0 \| 7, 0, 2, 0) |
| `axpy_k1_csr` | axpy's SimdLanes (op axpby, k1 from its CSR K1 = 3, `+ b`) at W = 2, int32, N = 4: JOBS = 2, T = 1, L = 0; x = (1, -2 \| 4, 0), y = (10, 20 \| -5, 7) give y' = (13, 14 \| 7, 7) |
| `axpby_int64_wrap` | axpby at int64, W = 2, J = 2: k1 baked at -2, k2 from its CSR at 2^62 + 1, so `k1 * a + k2 * b` wraps at int64 (2^63 + 16 gives -2^63 + 16) |
| `lane_fold_rowsum` | rowsum 2's lane accumulator, its worked example: `fold lanes`, W = 2, J = M / W = 2, T = N = 3, L = 1, int64; A's rows (1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12), a column a beat, give (6, 15) then (24, 33), each pushed the cycle after its job's last firing |
| `fold_jobs` | J = 2, T = 3, L = 1, int32 in, int64 out, with data: beats (k, k, k, k) for k = 1 .. 6 give 24 and 60, pushed in the cycles after firings 3 and 6, the next input taken as a result leaves |

## Running

From snax-gvsoc's root (in the image or on any host with g++ and C++17):

    tests/snax/unit/run.sh

It prints `PASS` per case and ends with `16 passed, 0 failed`.
