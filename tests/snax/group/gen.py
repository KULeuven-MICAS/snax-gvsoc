#
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#

"""Writes cases/*.txt, the shared group cases (README.md), from C§17's rule.

    python3 gen.py

The group rule of snax/snax_group_rule.py (written from snax-forge's C§17,
Control, not from snax/snax_group.hpp) steps each case, whose cycle table is
written with a comment per cycle; every dot variant's busy cycles E - s are
checked against C§17's formulas before a file is written, so a case never
states a total the formula does not give. The files are checked in; tb.cpp reads them.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "snax"))
from snax_group_rule import GroupRule  # noqa: E402

W = 4

# dot 2-6 (C§17): (datapath, L, span, inputs) per unit, the link's depth, whose T is N / W
VARIANTS = {
    2: ([("mul", "ElementwiseLanes", 0, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 1, "sum"),
    3: ([("mul", "ElementwiseLanes", 0, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 0, "sum"),
    4: ([("mac", "Mac", 1, 1, 2), ("sum", "TreeAccumulate", 1, 1, 0)], 0, "mac"),
    5: ([("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, W, 0)], 0, "mac"),
    6: ([("mac", "Mac", 1, 1, 2), ("sum", "SerialAccumulate", 1, W, 0)], 1, "mac"),
}


def formula(v, t, j):
    """C§17's busy cycles E - s of dot variant v."""
    return {2: j * t + 2, 3: j * t + 1, 4: j * t + 2, 5: j * (t + W - 1) + 2,
            6: (j - 1) * max(t, W) + t + W + 2}[v]


def write(name, title, units, depths, jobs, ts, valid=lambda c: (1, 1), ready=lambda c: 1,
          formula_total=None, comment=()):
    # A chain: link k joins unit k to unit k + 1's only input
    links = [{"from": units[k][0], "to": units[k + 1][0], "to_input": 0, "depth": d}
             for k, d in enumerate(depths)]
    m = GroupRule([dict(name=u[0], datapath=u[1], L=u[2], ii=1, span=u[3], inputs=u[4])
                   for u in units], links)
    rows, end = m.run(jobs, ts, valid, ready, 64)
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
                     f"inputs {u[4]}")
    for e in links:
        lines.append(f"link {e['from']} {e['to']} depth {e['depth']}")
    lines.append(f"jobs {jobs}")
    result = "ignored" if (jobs == 0 or 0 in ts) else "taken"
    lines.append(f"start 0 {result}")
    if end is not None:
        heads = sum(r[2][0][0] for r in rows)
        lines.append(f"expect run index=0 firings={heads} busy={classes['busy']} "
                     f"stall_in={classes['stall_in']} stall_out={classes['stall_out']} "
                     f"flush={classes['flush']}")
        lines.append(f"# E - s = {total}" + (f", C§17's formula" if formula_total else ""))
    lines += ["", "# a b ready | " + " | ".join(f"{u[0]} fire give" for u in units)
              + (" | " + " ".join(f"occ{k}" for k, d in enumerate(depths) if d) if any(depths) else "")
              + " | busy", "cycles"]
    for c, (v, r, out, occ, busy, cls, note) in enumerate(rows):
        cols = f"{v[0]} {v[1]} {r} | " + " | ".join(f"{f} {g}" for f, g in out)
        if any(depths):
            cols += " | " + " ".join(str(occ[k]) for k, d in enumerate(depths) if d)
        lines.append(f"{cols} | {busy}    # {c}: {note}")
    (HERE / "cases" / f"{name}.txt").write_text("\n".join(lines) + "\n")
    return total


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
                              comment=[f"C§17: busy cycles E - s = {formula(v, t, j)}"])
                table[(v, t, j)] = total
    u4, u6 = VARIANTS[4][0], VARIANTS[6][0]
    write("dot4_backpressure", "dot 4 at N = 8 (T = 2), JOBS 2, the writer not ready in "
          "cycles 4 and 5", u4, [0], 2, [2, 1], ready=lambda c: 0 if c in (4, 5) else 1,
          comment=["sum's head held two cycles (stall_out); mac holds its result behind it"])
    write("dot6_input_gap", "dot 6 at N = 16 (T = 4), JOBS 2, reader a without a beat in "
          "cycle 3", u6, [1], 2, [4, 1], valid=lambda c: (0, 1) if c == 3 else (1, 1),
          comment=["mac waits a cycle for a (stall_in while nothing else fires)"])
    write("dot4_jobs0", "dot 4, JOBS 0: the empty run, ignored; busy never rises", u4, [0], 0,
          [2, 1], comment=["the shell ends it in its own cycle (tests/snax/shell)"])
    print("T, J | " + " | ".join(f"dot {v}" for v in VARIANTS))
    for t in (2, 4):
        for j in (1, 2):
            print(f"{t}, {j} | " + " | ".join(str(table[(v, t, j)]) for v in VARIANTS))


if __name__ == "__main__":
    main()
