# The datapath classes

The datapaths of `snax/snax_datapath.hpp`, one plain C++ class per entry of snax-forge's catalogue (C§17, `hw/chisel/blocks.json`: `ElementwiseLanes`, `TreeAccumulate`, `Mac`, `SerialAccumulate`, `LinkBuffer`), against NumPy's vectors, with g++ only. `make regress` runs it after `shell`, as `datapath`. The control model (`snax/snax_group.hpp`) gives them their enables; here the vectors give them.

- `gen.py` writes `vectors.txt` with NumPy (a fixed seed, so the same file every time): per test a datapath, its params and per cycle its enables, its inputs and the output its `eval` must give, each datapath's rule written in Python from C§17, the arithmetic NumPy's (`astype`, wrapping). `vectors.txt` is checked in, so the tb needs no Python; run `gen.py` again (in snax-forge's pixi environment or anywhere with NumPy) only to change the vectors.
- `tb.cpp` builds each test's datapath from the registry (`snax_datapath_new`), then per step calls `eval` with the inputs and the enables, compares every output lane, and calls `commit`. It also checks the registry: each name builds with its latency and span, an unknown name and a Mac of the wrong shape are refused.
- `run.sh [OBJ_DIR]` builds it into `OBJ_DIR` (default `build/datapath`) and runs it; exit 1 on any difference.

## A test

    test NAME
    datapath Mac                 a catalogue name
    in int32 int32               the inputs' types, in port order
    optype int32                 the op's type (Mac, ElementwiseLanes)
    out int64                    the output's type (a LinkBuffer's dtype)
    lanes 4
    accumulate 1                 Mac only; also regOut, depth (LinkBuffer), op
    step F FI R L E LD WS RS : IN0 ; IN1 ... => OUT

A step's enables are fire, first, read, lane, en, load, wslot and rslot (`SnaxEnables`), then each input's lanes, `;` between inputs, then the output lanes eval must give: its registers before the step's clock edge for a registered datapath, the combinational result for ElementwiseLanes and a plain Mac without regOut. A fold's or SerialAccumulate's output is one value.

## What it covers

- Each class at three sizes, int64 (1, 2, 4 lanes) and int32 (2, 4, 8), random beats and enables; a tree, a MAC and a serial sum from int32 into int64; LinkBuffer at depth 1, 2 and 4.
- Mac in its three forms: accumulate, plain, plain with regOut. Plain at W = 4: a = (3, 5, -9, 5), b = (-1, 0, 2, -4), c = (8, -9, -4, -3) give y = (5, -9, -22, -23).
- Accumulate at W = 2, J = 2, T = 3: A's rows (1, -2, 3, 4, -5, 6) and (2, 2, 2, 2, 2, 2) against p = (2, 1, 0, -1, 3, 2), a beat a cycle, give the partials (-13, 6) and (10, 4); dot's sums of them are q = (-7, 14).
- The int32 product that wraps, W = 2, T = 8: 46341 x 46341 wraps at int32, and the partials are (-2147478991, 4).
- SerialAccumulate over the beat (-13, 6): -13 after lane 0, -7 after lane 1.

## Running

    tests/snax/datapath/run.sh

It prints `PASS` per test and ends with `56 passed, 0 failed`.
