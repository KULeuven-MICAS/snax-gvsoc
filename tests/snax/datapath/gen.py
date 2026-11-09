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


def simd(name, op, t_a, t_b, t_out, lanes, steps=6):
    t = Test(name, "SimdLanes", [t_a, t_b], np.result_type(NP[t_a], NP[t_b]).name,
             t_out, lanes, op=op)
    for _ in range(steps):
        a, b = rand(t_a, lanes), rand(t_b, lanes)
        T = np.result_type(NP[t_a], NP[t_b])
        x, y = a.astype(T), b.astype(T)
        r = {"add": x + y, "sub": x - y, "mul": x * y, "min": np.minimum(x, y),
             "max": np.maximum(x, y), "xor": x ^ y}[op]
        t.step(en(fire=1), [a, b], wrap(r, t_out))
    return t


def simd_k(name, op, t_a, t_out, lanes, k, steps=6):
    """A one-stream SimdLanes: op(a, k) at a's type, k its constant (the header's `k`)."""
    t = Test(name, "SimdLanes", [t_a], t_a, t_out, lanes, op=op, k=k)
    y = NP[t_a](k)
    for _ in range(steps):
        a = rand(t_a, lanes)
        r = {"add": a + y, "sub": a - y, "mul": a * y, "min": np.minimum(a, y),
             "max": np.maximum(a, y)}[op]
        t.step(en(fire=1), [a], wrap(r, t_out))
    return t


def axpby(name, t_a, t_b, t_out, lanes, k1, k2, steps=6):
    """SimdLanes at axpby: k1 * a + k2 * b at the inputs' result type (k2 None: + b), each of
    k1 and k2 an int (baked, the header's) or "csr" (read from its CSR: a random value set
    before every other step, `set`)."""
    T = np.result_type(NP[t_a], NP[t_b])
    kw = {"op": "axpby", "k1": k1} | ({} if k2 is None else {"k2": k2})
    t = Test(name, "SimdLanes", [t_a, t_b], T.name, t_out, lanes, **kw)
    now = {s: None for s, v in (("k1", k1), ("k2", k2)) if v == "csr"}
    for i in range(steps):
        for s in now:
            if i % 2 == 0:
                now[s] = int(rand(T.name, 1)[0])
                t.lines.append(f"set {s} {now[s]}")
        c1 = T.type(now.get("k1", k1) if k1 == "csr" else k1)
        a, b = rand(t_a, lanes), rand(t_b, lanes)
        x, y = a.astype(T), b.astype(T)
        scaled = y if k2 is None else T.type(now["k2"] if k2 == "csr" else k2) * y
        t.step(en(fire=1), [a, b], wrap(c1 * x + scaled, t_out))
    return t


def simd_kcsr(name, op, t_a, lanes, steps=6):
    """A one-stream SimdLanes with k read from its CSR (kcsr): a random k set before each step."""
    t = Test(name, "SimdLanes", [t_a], t_a, t_a, lanes, op=op)
    t.lines.append("kcsr")
    for _ in range(steps):
        k = int(rand(t_a, 1)[0])
        t.lines.append(f"set k {k}")
        a, y = rand(t_a, lanes), NP[t_a](k)
        r = {"add": a + y, "sub": a - y, "mul": a * y, "min": np.minimum(a, y),
             "max": np.maximum(a, y)}[op]
        t.step(en(fire=1), [a], wrap(r, t_a))
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


def tree_seed(name, t_in, t_out, lanes, beats, firings=10):
    """A seeded TreeAccumulate (D163): its second input the seed, one element; a job's first
    firing starts from it, acc <- seed + tree(a)."""
    t = Test(name, "TreeAccumulate", [t_in, t_out], t_out, t_out, lanes, op="add", seed=True)
    acc, d = NP[t_out](0), 0
    for _ in range(firings):
        fire = RNG.random() < 0.8
        a, q = rand(t_in, lanes), rand(t_out, 1)
        first = d == 0
        t.step(en(fire=fire, first=first), [a, q], acc)
        if fire:
            x = a.astype(NP[t_out]).sum(dtype=NP[t_out])
            acc = wrap(q[0] + x, t_out) if first else wrap(acc + x, t_out)
            d = (d + 1) % beats
    return t


def serial_seed(name, t_in, t_out, lanes, beats, words=4):
    """A seeded SerialAccumulate: lane by lane as unseeded, and the job's first beat's firing
    (its last lane, fire) adds the seed."""
    t = Test(name, "SerialAccumulate", [t_in, t_out], t_out, t_out, lanes, seed=True)
    acc, d = NP[t_out](0), 0
    for _ in range(words):
        a, q = rand(t_in, lanes), rand(t_out, 1)
        first = d == 0
        for lane in range(lanes):
            fire = lane == lanes - 1
            t.step(en(fire=fire, read=1, first=first, lane=lane), [a, q], acc)
            x = a[lane].astype(NP[t_out])
            acc = x if (first and lane == 0) else wrap(acc + x, t_out)
            if first and fire:
                acc = wrap(acc + q[0], t_out)
        d = (d + 1) % beats
    t.step(EN0, [rand(t_in, lanes), rand(t_out, 1)], acc)
    return t


def lane_acc(name, t_in, t_out, lanes, beats, firings=12):
    """LaneAccumulate: per lane s <- first ? a : s + a at t_out, a job every `beats` fires."""
    t = Test(name, "LaneAccumulate", [t_in], t_out, t_out, lanes)
    s, d = np.zeros(lanes, NP[t_out]), 0
    for _ in range(firings):
        fire = RNG.random() < 0.8
        a = rand(t_in, lanes)
        first = d == 0
        t.step(en(fire=fire, first=first), [a], s)
        if fire:
            x = a.astype(NP[t_out])
            s = x if first else wrap(s + x, t_out)
            d = (d + 1) % beats
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
    """The named vectors, worked by hand and checked against NumPy here."""
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
    # LaneAccumulate, rowsum 2's worked example: W = 2, J = 2, T = 3, a column a beat; A's rows
    # (1, 2, 3), (4, 5, 6) give 6, 15, then (7, 8, 9), (10, 11, 12) give 24, 33
    t = Test("lane_acc_rowsum_w2_j2_t3", "LaneAccumulate", ["int64"], "int64", "int64", 2)
    a = np.arange(1, 13).reshape(4, 3)
    s = [0, 0]
    for j in range(2):
        for k in range(3):
            col = a[2 * j:2 * j + 2, k].tolist()
            t.step(en(fire=1, first=k == 0), [col], s)
            s = col if k == 0 else [x + y for x, y in zip(s, col)]
        assert s == [[6, 15], [24, 33]][j], s
    t.step(EN0, [[0, 0]], s)
    out.append(t)
    return out


def main():
    tests = fixed()
    with np.errstate(over="ignore"):
        for t_in, t_out, sizes in (("int64", "int64", (1, 2, 4)), ("int32", "int32", (2, 4, 8))):
            for lanes in sizes:
                tests.append(simd(f"simd_add_{t_in}_w{lanes}", "add", t_in, t_in,
                                         t_out, lanes))
                tests.append(simd(f"simd_mul_{t_in}_w{lanes}", "mul", t_in, t_in,
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
        # one stream (relu's): every op at int32 and int64, k random and at the edges (drawn
        # after the tests above, so theirs stay as they were)
        for t_in, lanes in (("int32", 4), ("int64", 2)):
            info = np.iinfo(NP[t_in])
            for op in ("add", "sub", "mul", "min", "max"):
                ks = [0, -1, int(info.min), int(info.max), int(rand(t_in, 1)[0])]
                for i, k in enumerate(ks):
                    tests.append(simd_k(f"simd_k_{op}_{t_in}_w{lanes}_{i}", op, t_in, t_in, lanes,
                                        k))
        tests.append(simd_k("simd_k_max_int32_to_int64_w4", "max", "int32", "int64", 4, 0))
        # axpby (axpy's): k1 baked or from its CSR, k2 unset, baked or from its CSR, at int32
        # (2 and 4 lanes), int64 (2) and an int16 b into int64; then one stream with k from its
        # CSR (drawn after the tests above, so theirs stay as they were)
        for t_a, t_b, lanes in (("int32", "int32", 2), ("int32", "int32", 4),
                                ("int64", "int64", 2), ("int64", "int16", 4)):
            for k1, k2 in ((3, None), ("csr", None), (-7, "csr"), ("csr", "csr"), ("csr", 5)):
                tag = f"k1{'r' if k1 == 'csr' else k1}" + (
                    "" if k2 is None else f"_k2{'r' if k2 == 'csr' else k2}")
                tests.append(axpby(f"axpby_{t_a}x{t_b}_w{lanes}_{tag}".replace("-", "m"), t_a,
                                   t_b, np.result_type(NP[t_a], NP[t_b]).name, lanes, k1, k2))
        tests.append(axpby("axpby_int32_to_int64_w4_k1r", "int32", "int32", "int64", 4, "csr",
                           None))
        for t_in, lanes in (("int32", 4), ("int64", 2)):
            for op in ("add", "mul", "max"):
                tests.append(simd_kcsr(f"simd_kcsr_{op}_{t_in}_w{lanes}", op, t_in, lanes))
        # LaneAccumulate (rowsum 2's) at W 1, 4 and 8: int64, int32 (whole words: 4 and 8) and
        # int32 into int64 (drawn after the tests above, so theirs stay as they were)
        for t_in, t_out, sizes in (("int64", "int64", (1, 4, 8)), ("int32", "int32", (4, 8)),
                                   ("int32", "int64", (4, 8))):
            for lanes in sizes:
                name = f"lane_acc_{t_in}" + ("" if t_in == t_out else f"_to_{t_out}")
                tests.append(lane_acc(f"{name}_w{lanes}", t_in, t_out, lanes, 3))
        # the fold's seed (B2 R5, D163): TreeAccumulate and SerialAccumulate at W 1, 2 and 4,
        # int64, and int32 into int64 (drawn after the tests above, so theirs stay as they were)
        for t_in, t_out, sizes in (("int64", "int64", (1, 2, 4)), ("int32", "int64", (2, 4))):
            for lanes in sizes:
                name = t_in if t_in == t_out else f"{t_in}_to_{t_out}"
                tests.append(tree_seed(f"tree_seed_{name}_w{lanes}", t_in, t_out, lanes, 3))
                tests.append(serial_seed(f"serial_seed_{name}_w{lanes}", t_in, t_out, lanes, 2))
    # matvec_acc's worked example on TreeAccumulate at W = 2: rows (1, 2, 3, 4) . p = (1, 2, 0,
    # 1) in two beats, q = 1: 1 + 5 = 6, then 6 + 4 = 10
    t = Test("tree_seed_matvec_w2", "TreeAccumulate", ["int64", "int64"], "int64", "int64", 2,
             op="add", seed=True)
    t.step(en(fire=1, first=1), [[1, 4], [1]], [0])
    t.step(en(fire=1, first=0), [[0, 4], [7]], [6])
    t.step(EN0, [[0, 0], [0]], [10])
    tests.append(t)
    head = ("# The datapath classes' vectors (snax/snax_datapath.hpp), written by gen.py from "
            "NumPy; do not edit.\n")
    (HERE / "vectors.txt").write_text(head + "\n".join(t.text() for t in tests))
    print(f"wrote vectors.txt: {len(tests)} tests")


if __name__ == "__main__":
    main()
