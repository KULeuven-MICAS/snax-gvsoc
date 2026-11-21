#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""Writes cases/*.txt, the shared group cases (README.md), from the control rule.

    python3 gen.py

The group rule of snax/snax_group_rule.py (written from snax-forge's control rule,
Control, not from snax/snax_group.hpp) steps each case, whose cycle table is
written with a comment per cycle; every dot variant's busy cycles E - s are
checked against the rule's formulas before a file is written, so a case never
states a total the formula does not give. The files are checked in; tb.cpp reads them.
The W = 1 cases carry their data: seeded random int64 beats and each job's sum from numpy
(so this script needs numpy).
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "snax"))
from snax_group_rule import GroupRule  # noqa: E402

W = 4

# dot 2-6: (datapath, L, span, inputs) per unit, the link's depth, whose T is N / W
VARIANTS = {
    2: ([("mul", "SimdLanes", 0, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 1, "sum"),
    3: ([("mul", "SimdLanes", 0, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 0, "sum"),
    4: ([("mac", "Mac", 1, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 0, "mac"),
    5: ([("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, W, 0)], 0, "mac"),
    6: ([("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, W, 0)], 1, "mac"),
}


def formula(v, t, j, w=W):
    """The busy cycles E - s of dot variant v at w lanes."""
    return {2: j * t + 2, 3: j * t + 1, 4: j * t + 2, 5: j * (t + w - 1) + 2,
            6: (j - 1) * max(t, w) + t + w + 2}[v]


def dot_data(seed, jobs, beats, lanes):
    """Random int64 beats of a and b (lane l of beat i is element i * lanes + l) and each job's
    sum of products over its beats, wrapping at int64 as the datapaths do."""
    rng = np.random.default_rng(seed)
    i64 = np.iinfo(np.int64)
    a, b = (rng.integers(i64.min, i64.max, size=jobs * beats * lanes, dtype=np.int64,
                         endpoint=True) for _ in range(2))
    sums = (a * b).reshape(jobs, beats * lanes).sum(axis=1, dtype=np.int64)
    return {"lanes": lanes, "a": a.tolist(), "b": b.tolist(), "sums": sums.tolist()}


def packed_words(sent_at, pushes_at, d_out):
    """The words the packer sends: push n's result is -(n + 1), its low 64 / d_out bits at its
    slice, the slices above a short last word zero (snax_group.hpp's SnaxPacker)."""
    bits, words, word, slice_, n = 64 // d_out, [], 0, 0, 0
    for push, sent in zip(pushes_at, sent_at):
        if not push:
            continue
        word = 0 if slice_ == 0 else word
        word |= ((-(n + 1)) & ((1 << bits) - 1)) << (slice_ * bits)
        n += 1
        if sent:
            words.append(word)
            slice_ = 0
        else:
            slice_ += 1
    return words


def write(name, title, units, depths, jobs, ts, valid=lambda c: (1, 1), ready=lambda c: 1,
          formula_total=None, comment=(), data=None, d_out=1, d_in=()):
    # A chain: link k joins unit k to unit k + 1's only input
    links = [{"from": units[k][0], "to": units[k + 1][0], "to_input": 0, "depth": d}
             for k, d in enumerate(depths)]
    m = GroupRule([dict(name=u[0], datapath=u[1], L=u[2], ii=1, span=u[3], inputs=u[4],
                        seed=len(u) > 5 and u[5]) for u in units], links)
    sliced = [(i, d) for i, d in enumerate(d_in) if d > 1]
    if sliced:  # a sliced input's reader has ceil(pops / d_in) words, then no more
        fired = m.firings_per_run(jobs, ts)
        port = [(k, len(u) > 5 and u[5] and j == u[4] - 1)
                for k, u in enumerate(units) for j in range(u[4])]
        pops = [fired[port[i][0]] // (ts[port[i][0]] if port[i][1] else 1) for i, _ in sliced]
        words = [-(-n // d) for n, (_, d) in zip(pops, sliced)]
        given = valid

        def valid(c):
            v = list(given(c))
            for at, (i, _) in enumerate(sliced):
                if sum(t[at] for t in m.took) >= words[at]:
                    v[i] = 0
            return tuple(v)
    rows, end = m.run(jobs, ts, valid, ready, 64, d_out, d_in)
    if end is None:
        empty = jobs == 0 or 0 in ts
        assert empty, name
        last = 3
    else:
        last = end + 2
    rows = rows[: last + 1]
    classes = {k: sum(1 for r in rows if r[5] == k) for k in ("busy", "stall_in", "stall_out", "flush")}
    total = sum(classes.values())
    if formula_total is not None and total != formula_total:
        raise SystemExit(f"{name}: the rule gives E - s = {total}, the formula {formula_total}")
    lines = [f"# {title}", *(f"# {c}" for c in comment), ""]
    for u in units:
        k = units.index(u)
        lines.append(f"unit {u[0]} {u[1]} latency {u[2]} ii 1 span {u[3]} t {ts[k]} "
                     f"inputs {u[4]}" + (" seed 1" if len(u) > 5 and u[5] else ""))
    for e in links:
        lines.append(f"link {e['from']} {e['to']} depth {e['depth']}")
    lines.append(f"jobs {jobs}")
    if d_out > 1:
        lines.append(f"dout {d_out}")
    lines += [f"din {i} {d}" for i, d in sliced]
    result = "ignored" if (jobs == 0 or 0 in ts) else "taken"
    lines.append(f"start 0 {result}")
    if end is not None:
        heads = sum(r[2][0][0] for r in rows)
        lines.append(f"expect run index=0 firings={heads} busy={classes['busy']} "
                     f"stall_in={classes['stall_in']} stall_out={classes['stall_out']} "
                     f"flush={classes['flush']}")
        lines.append(f"# E - s = {total}" + (f", the rule's formula" if formula_total else ""))
    if d_out > 1:
        pushes_at = [r[2][m.output][1] for r in rows]
        words = packed_words(m.sent[: len(rows)], pushes_at, d_out)
        lines.append("words " + " ".join(f"0x{w:016x}" for w in words))
    if data is not None:
        lines.append(f"lanes {data['lanes']}")
        lines += [f"data {x} " + " ".join(map(str, data[x])) for x in ("a", "b")]
        lines.append("sums " + " ".join(map(str, data["sums"])))
    names = [x for u in units for x in ((["a", "b"][:u[4]] if not (len(u) > 5 and u[5])
             else [*["a", "b"][:u[4] - 1], f"{u[0]}.seed"]) if u[4] else [])]
    lines += ["", f"# {' '.join(names)} ready | " + " | ".join(f"{u[0]} fire give" for u in units)
              + (" | " + " ".join(f"occ{k}" for k, d in enumerate(depths) if d) if any(depths) else "")
              + (" | " + " ".join(f"took{i}" for i, _ in sliced) if sliced else "")
              + (" | sent" if d_out > 1 else "") + " | busy", "cycles"]
    for c, (v, r, out, occ, busy, cls, note) in enumerate(rows):
        cols = " ".join(map(str, v)) + f" {r} | " + " | ".join(f"{f} {g}" for f, g in out)
        if any(depths):
            cols += " | " + " ".join(str(occ[k]) for k, d in enumerate(depths) if d)
        if sliced:
            cols += " | " + " ".join(map(str, m.took[c]))
        if d_out > 1:
            cols += f" | {m.sent[c]}"
            note += " (word sent)" if m.sent[c] else ""
        lines.append(f"{cols} | {busy}    # {c}: {note}")
    (HERE / "cases" / f"{name}.txt").write_text("\n".join(lines) + "\n")
    return total


def seed_cases():
    """The fold's seed: a seeded unit's last outer input is its seed,
    one beat per job; its job's first beat waits for it (fire = a.valid and (not first or
    seed.valid)), the firing takes it. Two folds in a chain, acc (TreeAccumulate, T 2) into sum
    (TreeAccumulate, T 2) by a wire, JOBS 2, unseeded, the first seeded, both seeded: with
    every seed there from the start the three take the same cycles. A late seed on matvec_acc_v1's
    sum (TreeAccumulate, T 4, JOBS 2) and on a SerialAccumulate (span 4) after a Mac."""
    def chain(seed_acc, seed_sum):
        return [("acc", "TreeAccumulate", 1, 1, 1 + seed_acc, seed_acc),
                ("sum", "TreeAccumulate", 1, 1, seed_sum, seed_sum)]
    ones = {(0, 0): (1,), (1, 0): (1, 1), (1, 1): (1, 1, 1)}
    totals = {}
    for (sa, ss), name, what in (((0, 0), "seed_none", "neither seeded"),
                                 ((1, 0), "seed_first", "acc seeded, sum not"),
                                 ((1, 1), "seed_both", "both seeded")):
        totals[name] = write(name, f"acc (TreeAccumulate, T 2) -> a wire -> sum (TreeAccumulate, "
                             f"T 2), JOBS 2: {what}, every seed there", chain(sa, ss), [0], 2,
                             [2, 2], valid=lambda c, v=ones[(sa, ss)]: v,
                             comment=["a seeded unit takes its seed with its job's first "
                                      "firing; the cycles as unseeded"])
    assert len(set(totals.values())) == 1, totals
    late = {1, 2, 3, 8, 9}
    write("seed_late", "matvec_acc_v1's sum: TreeAccumulate, T 4, JOBS 2, its seed missing in "
          "cycles 1 to 3 and 8 to 9", [("sum", "TreeAccumulate", 1, 1, 2, 1)], [], 2, [4],
          valid=lambda c: (1, 0 if c in late else 1),
          comment=["each job's first beat waits for the seed (stall_in); its other beats do "
                   "not"])
    serial = [("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, W, 1, 1)]
    write("seed_serial_late", f"mac (Mac, T 2) -> a wire -> sum (SerialAccumulate, span {W}, "
          "seeded, T 1), JOBS 2, sum's seed missing in cycles 1 to 4 and 7", serial, [0], 2,
          [2, 1], valid=lambda c: (1, 1, 0 if c in {1, 2, 3, 4, 7} else 1),
          comment=["sum reads its job's first beat lane by lane only once its seed is there; "
                   "mac holds its result"])
    write("seed_mac_late", "mac (Mac, T 4, seeded: its seed has the output's lanes, D187) "
          "alone, JOBS 2, its seed missing in cycles 1 to 3 and 6 to 7",
          [("mac", "Mac", 1, 1, 3, 1)], [], 2, [4],
          valid=lambda c: (1, 1, 0 if c in {1, 2, 3, 6, 7} else 1),
          comment=["a seeded Mac waits for its seed on each job's first beat, as a seeded "
                   "fold; its other beats do not"])


def pack_cases():
    """The outer output's packer (D174): a fold's one-lane result packed d_out to a word, its
    room the writer's ready only on a sending push. sum (TreeAccumulate, T 2) alone at d_out
    2, 4 and 8 (int32, int16, int8 results), JOBS 1 (a short word at once), 9 (a short last
    word) and 10 (whole words at d_out 2); the writer not ready while the packer fills; and dot
    3 (SimdLanes -> wire -> TreeAccumulate, T 2) at d_out 2 over 3 jobs."""
    sum_ = [("sum", "TreeAccumulate", 1, 1, 1)]
    for d in (2, 4, 8):
        for j in (1, 9, 10):
            write(f"pack_d{d}_j{j}", f"sum (TreeAccumulate, T 2), JOBS {j}, its result packed "
                  f"{d} to a word ({64 // d}-bit results)", sum_, [], j, [2],
                  valid=lambda c: (1,), d_out=d,
                  comment=["a word every d_out pushes, the run's last push sending a short one; "
                           "push n's result is -(n + 1), so a word shows its slices"])
    # writer not ready in cycles 4 and 5, during the first word's filling push and its sending
    # push: the filling push goes ahead, the sending one waits (stall_out)
    write("pack_d2_backpressure", "sum (TreeAccumulate, T 2), JOBS 4, packed 2 to a word, the "
          "writer not ready in cycles 3 to 5", sum_, [], 4, [2], valid=lambda c: (1,),
          ready=lambda c: 0 if c in (3, 4, 5) else 1, d_out=2,
          comment=["a filling push needs no room at the writer; a sending one waits for it"])
    dot3 = VARIANTS[3][0]
    write("pack_dot3_d2_j3", "dot 3 at N = 8, W = 4 (T = 2), JOBS 3, the sum packed 2 to a word",
          dot3, [0], 3, [1, 2], d_out=2,
          comment=["three results: one whole word, then a short one on the last push"])


def slice_cases():
    """The input's slicer (D180): one word from the reader, d_in pops, low slice first, a word
    taken only while busy and shown the cycle after, the next taken on the last pop. sum
    (TreeAccumulate, T 2) alone, its input sliced 2, 4 and 8 (int32, int16, int8 lanes), JOBS
    3 and 2 (6 pops: whole words at 2, a short last word at 4; 4 pops of one word at 8); the
    reader without a word in cycles 3 to 5; the writer not ready in cycles 4 to 6;
    matvec_acc_v1's sum with its seed sliced 2; and dot 3 with a and b sliced 2 and the sum
    packed 2, matvec_v3's form at int8, W = 4."""
    sum_ = [("sum", "TreeAccumulate", 1, 1, 1)]
    for d, j in ((2, 3), (4, 3), (8, 2)):
        write(f"slice_d{d}_j{j}", f"sum (TreeAccumulate, T 2), JOBS {j}, its input sliced {d} "
              f"({64 // d}-bit lanes)", sum_, [], j, [2], valid=lambda c: (1,), d_in=(d,),
              comment=["the reader valid from cycle 0: the word is taken in cycle 1 (busy) and "
                       "popped from cycle 2; the run's last word may be left part popped"])
    write("slice_d2_reader_gap", "sum (TreeAccumulate, T 2), JOBS 3, its input sliced 2, the "
          "reader without a word in cycles 3 to 5", sum_, [], 3, [2],
          valid=lambda c: (0,) if c in (3, 4, 5) else (1,), d_in=(2,),
          comment=["the second word arrives late: the sum waits for it (stall_in)"])
    write("slice_d2_backpressure", "sum (TreeAccumulate, T 2), JOBS 3, its input sliced 2, the "
          "writer not ready in cycles 4 to 6", sum_, [], 3, [2], valid=lambda c: (1,),
          ready=lambda c: 0 if c in (4, 5, 6) else 1, d_in=(2,),
          comment=["the sum's head held (stall_out): no pop, the slicer keeps its word"])
    write("slice_seed_d2", "matvec_acc_v1's sum: TreeAccumulate, T 4, JOBS 3, its seed sliced 2",
          [("sum", "TreeAccumulate", 1, 1, 2, 1)], [], 3, [4], valid=lambda c: (1, 1),
          d_in=(1, 2), comment=["a seed popped on each job's first firing: a seed word "
                                "serves two jobs"])
    write("slice_dot3_d2_j2", "dot 3 at N = 8, W = 4 (T = 2), JOBS 2, a and b sliced 2, the "
          "sum packed 2 to a word", VARIANTS[3][0], [0], 2, [1, 2], d_out=2, d_in=(2, 2),
          comment=["matvec_v3 at int8, W = 4: both readers sliced, one cycle later than "
                   "pack_dot3"])
    write("slice_mac_bcast_d8", "mac (Mac, T 4, seeded), JOBS 2, its b sliced 8 and broadcast "
          "(D186): mvt's half 2 at int8, a and the seed wired", [("mac", "Mac", 1, 1, 3, 1)],
          [], 2, [4], valid=lambda c: (1, 1, 1), d_in=(1, 8, 1),
          comment=["b's one word gives the 8 firings their y2[i], one a firing; the broadcast "
                   "is wires (each lane gets the pop), so the rule does not see it"])


def main():
    table = {}
    for v, (units, depth, fold) in VARIANTS.items():
        for n in (8, 16):
            t = n // W
            for j in (1, 2):
                ts = [t, 1] if fold == "mac" else [1, t]
                link = "a buffer of depth 1" if depth else "a wire"
                total = write(f"dot{v}_n{n}_j{j}", f"dot {v} at N = {n}, W = {W} (T = {t}), "
                              f"JOBS {j}: {units[0][0]} -> {link} -> {units[1][1]} {units[1][0]}",
                              units, [depth], j, ts, formula_total=formula(v, t, j),
                              comment=[f"busy cycles E - s = {formula(v, t, j)}"])
                table[(v, t, j)] = total
    u4, u6 = VARIANTS[4][0], VARIANTS[6][0]
    write("dot4_backpressure", "dot 4 at N = 8 (T = 2), JOBS 2, the writer not ready in "
          "cycles 4 and 5", u4, [0], 2, [2, 1], ready=lambda c: 0 if c in (4, 5) else 1,
          comment=["sum's head held two cycles (stall_out); mac holds its result behind it"])
    write("dot6_input_gap", "dot 6 at N = 16 (T = 4), JOBS 2, reader a without a beat in "
          "cycle 3", u6, [1], 2, [4, 1], valid=lambda c: (0, 1) if c == 3 else (1, 1),
          comment=["mac waits a cycle for a (stall_in while nothing else fires)"])
    # SerialAccumulate at lanes 1 (span 1): it reads (and fires) once per beat
    for v, seed in ((5, 5), (6, 6)):
        units = [("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, 1, 0)]
        depth, t, j = VARIANTS[v][1], 4, 2
        link = "a buffer of depth 1" if depth else "a wire"
        write(f"dot{v}_w1_j{j}", f"dot {v} at N = 4, W = 1 (T = {t}), JOBS {j}: mac -> {link} "
              f"-> SerialAccumulate sum at span 1", units, [depth], j, [t, 1],
              formula_total=formula(v, t, j, 1),
              comment=[f"busy cycles E - s = {formula(v, t, j, 1)}",
                       f"random int64 data (numpy seed {seed}); each job's sum of a * b"],
              data=dot_data(seed, j, t, 1))
    write("dot4_jobs0", "dot 4, JOBS 0: the empty run, ignored; busy never rises", u4, [0], 0,
          [2, 1], comment=["the shell ends it in its own cycle (tests/snax/shell)"])
    seed_cases()
    pack_cases()
    slice_cases()
    print("T, J | " + " | ".join(f"dot {v}" for v in VARIANTS))
    for t in (2, 4):
        for j in (1, 2):
            print(f"{t}, {j} | " + " | ".join(str(table[(v, t, j)]) for v in VARIANTS))


if __name__ == "__main__":
    main()
