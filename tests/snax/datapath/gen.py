#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""Writes vectors.txt, the datapath classes' vectors (README.md), from NumPy.

    python3 gen.py        (with NumPy; the tb itself needs no Python)

Each test drives one datapath of snax/snax_datapath.hpp cycle by cycle: per
cycle the enables and the inputs, and the output eval must give (its
registers before the cycle's clock edge). The expected values come from
NumPy's integer arithmetic (astype, wrapping), each datapath's rule written
here as C§17 states it, not from the C++. The random tests use a fixed seed,
so the file is the same every time.
"""

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RNG = np.random.default_rng(2026)
NP = {f"{s}int{w}": getattr(np, f"{s}int{w}") for w in (8, 16, 32, 64) for s in ("", "u")}


def rand(dtype: str, n: int) -> np.ndarray:
    info = np.iinfo(NP[dtype])
    return RNG.integers(info.min, info.max, n, dtype=NP[dtype], endpoint=True)


def wrap(v, dtype: str):
    return np.asarray(v).astype(NP[dtype])


class Test:
    def __init__(self, name, datapath, ins, op_t, out_t, lanes, **kw):
        self.lines = [f"test {name}", f"datapath {datapath}", f"in {' '.join(ins)}",
                      f"optype {op_t}", f"out {out_t}", f"lanes {lanes}"]
        self.lines += [f"{k} {int(v) if isinstance(v, bool) else v}" for k, v in kw.items()]
        self.ins, self.op_t, self.out_t, self.lanes = ins, op_t, out_t, lanes

    def step(self, en, values, out):
        fire, first, read, lane, eon, load, ws, rs = en
        ins = " ; ".join(" ".join(str(int(x)) for x in v) for v in values)
        o = " ".join(str(int(x)) for x in np.atleast_1d(out))
        self.lines.append(f"step {int(fire)} {int(first)} {int(read)} {lane} {int(eon)} {int(load)} "
                          f"{ws} {rs} : {ins} => {o}")

    def text(self):
        return "\n".join(self.lines) + "\n"


EN0 = (0, 0, 0, 0, 0, 0, 0, 0)


def en(fire=0, first=0, read=0, lane=0, e=0, load=0, ws=0, rs=0):
    return (fire, first, read, lane, e, load, ws, rs)


def elementwise(name, op, t_a, t_b, t_out, lanes, steps=6):
    t = Test(name, "ElementwiseLanes", [t_a, t_b], np.result_type(NP[t_a], NP[t_b]).name,
             t_out, lanes, op=op)
    for _ in range(steps):
        a, b = rand(t_a, lanes), rand(t_b, lanes)
        T = np.result_type(NP[t_a], NP[t_b])
        x, y = a.astype(T), b.astype(T)
        r = {"add": x + y, "sub": x - y, "mul": x * y, "min": np.minimum(x, y),
             "max": np.maximum(x, y), "xor": x ^ y}[op]
        t.step(en(fire=1), [a, b], wrap(r, t_out))
    return t


def tree(name, t_in, t_out, lanes, beats, firings=10):
    t = Test(name, "TreeAccumulate", [t_in], t_out, t_out, lanes, op="add")
    acc, d = NP[t_out](0), 0
    for k in range(firings):
        fire = RNG.random() < 0.8
        a = rand(t_in, lanes)
        first = d == 0
        t.step(en(fire=fire, first=first), [a], acc)
        if fire:
            x = a.astype(NP[t_out]).sum(dtype=NP[t_out])
            acc = x if first else wrap(acc + x, t_out)
            d = (d + 1) % beats
    return t


def mac(name, t_in, op_t, out_t, lanes, beats, firings=12):
    t = Test(name, "Mac", [t_in, t_in], op_t, out_t, lanes, accumulate=True, regOut=False)
    s, d = np.zeros(lanes, NP[out_t]), 0
    for _ in range(firings):
        fire = RNG.random() < 0.8
        a, b = rand(t_in, lanes), rand(t_in, lanes)
        first = d == 0
        t.step(en(fire=fire, first=first), [a, b], s)
        if fire:
            p = (a.astype(NP[op_t]) * b.astype(NP[op_t])).astype(NP[out_t])
            s = p if first else wrap(s + p, out_t)
            d = (d + 1) % beats
    return t


def mac_plain(name, t_in, op_t, out_t, lanes, reg_out, steps=6):
    t = Test(name, "Mac", [t_in, t_in, out_t], op_t, out_t, lanes, accumulate=False,
             regOut=reg_out)
    r = np.zeros(lanes, NP[out_t])
    for _ in range(steps):
        e = RNG.random() < 0.7
        a, b, c = rand(t_in, lanes), rand(t_in, lanes), rand(out_t, lanes)
        y = wrap((a.astype(NP[op_t]) * b.astype(NP[op_t])).astype(NP[out_t]) + c, out_t)
        t.step(en(e=e), [a, b, c], r if reg_out else y)
        if reg_out and e:
            r = y
    return t


def serial(name, t_in, t_out, lanes, beats, words=4):
    t = Test(name, "SerialAccumulate", [t_in], t_out, t_out, lanes)
    acc, d = NP[t_out](0), 0
    for _ in range(words):
        a = rand(t_in, lanes)
        first = d == 0
        for lane in range(lanes):
            read = True
            t.step(en(read=read, first=first, lane=lane), [a], acc)
            x = a[lane].astype(NP[t_out])
            acc = x if (first and lane == 0) else wrap(acc + x, t_out)
        d = (d + 1) % beats
    t.step(EN0, [rand(t_in, lanes)], acc)
    return t


def buffer(name, dtype, lanes, depth, steps=12):
    t = Test(name, "LinkBuffer", [dtype], dtype, dtype, lanes, depth=depth)
    slots = [np.zeros(lanes, NP[dtype]) for _ in range(depth)]
    w = r = occ = 0
    for _ in range(steps):
        take = occ > 0 and RNG.random() < 0.6
        load = (occ < depth or take) and RNG.random() < 0.7
        a = rand(dtype, lanes)
        t.step(en(load=load, ws=w, rs=r), [a], slots[r])
        if load:
            slots[w] = a
            w = (w + 1) % depth
        if take:
            r = (r + 1) % depth
        occ += int(load) - int(take)
    return t


def fixed():
    """The round's named vectors (G1's prompt)."""
    out = []
    # Plain W = 4: y = a * b + c
    t = Test("mac_plain_w4", "Mac", ["int64"] * 3, "int64", "int64", 4, accumulate=False,
             regOut=False)
    t.step(EN0, [[3, 5, -9, 5], [-1, 0, 2, -4], [8, -9, -4, -3]], [5, -9, -22, -23])
    out.append(t)
    # Accumulate W = 2, J = 2, T = 3: A's rows against p, lane by lane
    t = Test("mac_acc_w2_j2_t3", "Mac", ["int64"] * 2, "int64", "int64", 2, accumulate=True,
             regOut=False)
    rows, p = [[1, -2, 3, 4, -5, 6], [2] * 6], [2, 1, 0, -1, 3, 2]
    s = [0, 0]
    for j, row in enumerate(rows):
        for k in range(3):
            a, b = row[2 * k:2 * k + 2], p[2 * k:2 * k + 2]
            t.step(en(fire=1, first=k == 0), [a, b], s)
            prod = [x * y for x, y in zip(a, b)]
            s = prod if k == 0 else [x + y for x, y in zip(s, prod)]
        assert s == [[-13, 6], [10, 4]][j]
    t.step(EN0, [[0, 0], [0, 0]], [10, 4])
    out.append(t)
    # The int32 product that wraps, W = 2, T = 8: q = (-2147478991, 4)
    t = Test("mac_int32_wrap_w2_t8", "Mac", ["int32"] * 2, "int32", "int32", 2, accumulate=True,
             regOut=False)
    a = [[46341, 1]] + [[3, 1]] * 3 + [[3, 0]] * 3 + [[6, 0]]
    b = [[46341, 1]] + [[1, 1]] * 6 + [[1, 0]]
    s = np.zeros(2, np.int32)
    for k in range(8):
        t.step(en(fire=1, first=k == 0), [a[k], b[k]], s)
        prod = (np.array(a[k], np.int32) * np.array(b[k], np.int32)).astype(np.int32)
        s = prod if k == 0 else (s + prod).astype(np.int32)
    assert s.tolist() == [-2147478991, 4], s
    t.step(EN0, [[0, 0], [0, 0]], s)
    out.append(t)
    # SerialAccumulate over (-13, 6): -13, then -7
    t = Test("serial_partials", "SerialAccumulate", ["int64"], "int64", "int64", 2)
    t.step(en(read=1, first=1, lane=0), [[-13, 6]], [0])
    t.step(en(read=1, first=1, lane=1), [[-13, 6]], [-13])
    t.step(EN0, [[0, 0]], [-7])
    out.append(t)
    return out


def main():
    tests = fixed()
    with np.errstate(over="ignore"):
        for t_in, t_out, sizes in (("int64", "int64", (1, 2, 4)), ("int32", "int32", (2, 4, 8))):
            for lanes in sizes:
                tests.append(elementwise(f"elementwise_add_{t_in}_w{lanes}", "add", t_in, t_in,
                                         t_out, lanes))
                tests.append(elementwise(f"elementwise_mul_{t_in}_w{lanes}", "mul", t_in, t_in,
                                         t_out, lanes))
                tests.append(tree(f"tree_{t_in}_w{lanes}", t_in, t_out, lanes, 3))
                tests.append(mac(f"mac_acc_{t_in}_w{lanes}", t_in, t_in, t_out, lanes, 3))
                tests.append(mac_plain(f"mac_plain_{t_in}_w{lanes}", t_in, t_in, t_out, lanes,
                                       False))
                tests.append(mac_plain(f"mac_regout_{t_in}_w{lanes}", t_in, t_in, t_out, lanes,
                                       True))
                tests.append(serial(f"serial_{t_in}_w{lanes}", t_in, t_out, lanes, 2))
        tests.append(tree("tree_int32_to_int64_w4", "int32", "int64", 4, 2))
        tests.append(mac("mac_acc_int32_to_int64_w4", "int32", "int32", "int64", 4, 2))
        tests.append(serial("serial_int32_to_int64_w4", "int32", "int64", 4, 1))
        for depth in (1, 2, 4):
            tests.append(buffer(f"buffer_int64_w4_d{depth}", "int64", 4, depth))
            tests.append(buffer(f"buffer_int32_w4_d{depth}", "int32", 4, depth))
    head = ("# The datapath classes' vectors (snax/snax_datapath.hpp), written by gen.py from "
            "NumPy; do not edit.\n")
    (HERE / "vectors.txt").write_text(head + "\n".join(t.text() for t in tests))
    print(f"wrote vectors.txt: {len(tests)} tests")


if __name__ == "__main__":
    main()
