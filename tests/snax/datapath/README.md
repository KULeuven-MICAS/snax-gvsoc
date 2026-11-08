# The datapath classes

The datapaths of `snax/snax_datapath.hpp`, one plain C++ class per entry of snax-forge's catalogue (C§17, `hw/chisel/blocks.json`: `SimdLanes`, `TreeAccumulate`, `Mac`, `SerialAccumulate`, `LaneAccumulate`, `LinkBuffer`), against NumPy's vectors, with g++ only. `make regress` runs it after `shell`, as `datapath`. The control model (`snax/snax_group.hpp`) gives them their enables; here the vectors give them.

- `gen.py` writes `vectors.txt` with NumPy (a fixed seed, so the same file every time): per test a datapath, its params and per cycle its enables, its inputs and the output its `eval` must give, each datapath's rule written in Python from C§17, the arithmetic NumPy's (`astype`, wrapping). `vectors.txt` is checked in, so the tb needs no Python; run `gen.py` again (in snax-forge's pixi environment or anywhere with NumPy) only to change the vectors.
- `tb.cpp` builds each test's datapath from the registry (`snax_datapath_new`), then per step calls `eval` with the inputs and the enables, compares every output lane, and calls `commit`. It also checks the registry: each name builds with its latency and span, an unknown name and a Mac of the wrong shape are refused.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/datapath`) and runs it; exit 1 on any difference.

## A test

    test NAME
    datapath Mac                 a catalogue name
    in int32 int32               the inputs' types, in port order
    optype int32                 the op's type (Mac, SimdLanes)
    out int64                    the output's type (a LinkBuffer's dtype)
    lanes 4
    accumulate 1                 Mac only; also regOut, depth (LinkBuffer), op, k (a one-stream SimdLanes' constant)
    seed 1                       a seeded fold (TreeAccumulate, SerialAccumulate): its last input the seed, one element
    k1 3                         axpby's (op axpby) k1, baked, or `k1 csr` (from its CSR); k2 likewise; `kcsr`: a one-stream k from its CSR
    set k1 7                     a CSR slot's value, given to the datapath (set_scalar) before the next step
    step F FI R L E LD WS RS : IN0 ; IN1 ... => OUT

A step's enables are fire, first, read, lane, en, load, wslot and rslot (`SnaxEnables`), then each input's lanes, `;` between inputs, then the output lanes eval must give: its registers before the step's clock edge for a registered datapath, the combinational result for SimdLanes and a plain Mac without regOut. A fold's or SerialAccumulate's output is one value.

## What it covers

- Each class at three sizes, int64 (1, 2, 4 lanes) and int32 (2, 4, 8), random beats and enables; a tree, a MAC and a serial sum from int32 into int64; LinkBuffer at depth 1, 2 and 4.
- SimdLanes at one stream (relu's, the header's `k`: op(a, k) at a's type): add, sub, mul, min and max at int32 (4 lanes) and int64 (2), each with k = 0, -1, the type's min and max, and a random k; and max(a, 0) from int32 into int64.
- SimdLanes at axpby (axpy's, `k1 * a + k2 * b` at the inputs' result type, + b without k2): k1 baked or from its CSR, k2 unset, baked or from its CSR, at int32 (2 and 4 lanes), int64 (2) and int64 with an int16 b (4), a CSR slot's value set anew every other step; int32 into int64; and one stream with k from its CSR (add, mul, max at int32 and int64), k set anew every step.
- Mac in its three forms: accumulate, plain, plain with regOut. Plain at W = 4: a = (3, 5, -9, 5), b = (-1, 0, 2, -4), c = (8, -9, -4, -3) give y = (5, -9, -22, -23).
- Accumulate at W = 2, J = 2, T = 3: A's rows (1, -2, 3, 4, -5, 6) and (2, 2, 2, 2, 2, 2) against p = (2, 1, 0, -1, 3, 2), a beat a cycle, give the partials (-13, 6) and (10, 4); dot's sums of them are q = (-7, 14).
- The int32 product that wraps, W = 2, T = 8: 46341 x 46341 wraps at int32, and the partials are (-2147478991, 4).
- SerialAccumulate over the beat (-13, 6): -13 after lane 0, -7 after lane 1.
- The fold's seed (snax-forge B2 R5, D149): TreeAccumulate and SerialAccumulate seeded at int64 (1, 2 and 4 lanes) and int32 into int64 (2 and 4), random beats, seeds and enables: a job's first firing starts from its seed (TreeAccumulate), or adds it on the first beat's last lane (SerialAccumulate); and matvec_acc's worked example on TreeAccumulate at W = 2, rows (1, 2, 3, 4) against p = (1, 2, 0, 1) from q = 1: 6 after the first beat, 10 after the second.
- LaneAccumulate (rowsum 2's): its worked example at W = 2, J = 2, T = 3, A's rows (1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12) a column a beat, giving (6, 15) then (24, 33); random beats and enables at int64 (1, 4 and 8 lanes), int32 (4 and 8) and int32 into int64 (4 and 8); the registry builds it at L 1, span 1, and refuses it with two inputs.
- `snax/snax_types.hpp`'s arithmetic, which the classes run, on fixed vectors worked by hand in `tb.cpp`, for the edges the NumPy vectors do not reach: `ops`, the op table (wrapping at 8 to 64 bits, signed and unsigned min and max); `tree`, a fold's tree over a beat's lanes (`snax_op_tree`: halves first, wrapping); `types`, NumPy's result types (`snax_op_result_type`: int64 with uint64 refused); `beats`, whole beats (`snax_op_elementwise` and `snax_op_fold` on 64-bit channel words, lane 0 lowest, with int8, uint8, int16, int32 and int64 ports).

## Running

    tests/snax/datapath/run.sh

It prints `PASS` per test (and `registry`, `ops`, `tree`, `types` and `beats`) and ends with `157 passed, 0 failed`.
