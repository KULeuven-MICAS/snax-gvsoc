#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""snax/snax_group_rule.py: the dot variants against C§17's formulas, the groups it refuses,
and one unit against the unit cases (tests/snax/unit/cases).

    python3 -m unittest discover -s tests/snax -p 'test_*.py'
"""

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "snax"))
sys.path.insert(0, str(HERE / "group"))
import gen  # noqa: E402
from snax_group_rule import GroupError, GroupRule  # noqa: E402

UNIT_CASES = HERE / "unit" / "cases"
CLASSES = ("busy", "stall_in", "stall_out", "flush")


def unit(name, L=0, ii=1, span=1, inputs=2):
    return dict(name=name, L=L, ii=ii, span=span, inputs=inputs)


def link(src, dst, depth=0, to_input=0):
    return {"from": src, "to": dst, "to_input": to_input, "depth": depth}


def totals(rows):
    return {k: sum(1 for r in rows if r[5] == k) for k in CLASSES}


class Dot(unittest.TestCase):
    def test_busy_cycles_are_the_formula(self):
        for v, (units, depth, fold) in gen.VARIANTS.items():
            us = [dict(name=u[0], L=u[2], ii=1, span=u[3], inputs=u[4]) for u in units]
            rule = GroupRule(us, [link(us[0]["name"], us[1]["name"], depth)])
            for n in (8, 16):
                t = n // gen.W
                for j in (1, 2):
                    ts = [t, 1] if fold == "mac" else [1, t]
                    rows, end = rule.run(j, ts, lambda c: (1, 1), lambda c: 1, 64)
                    with self.subTest(dot=v, n=n, jobs=j):
                        self.assertIsNotNone(end)
                        self.assertEqual(sum(totals(rows).values()), gen.formula(v, t, j))
                        self.assertEqual(end, gen.formula(v, t, j))

    def test_counts_over_the_chain(self):
        rule = GroupRule([unit("mul"), unit("sum", inputs=0)], [link("mul", "sum")])
        self.assertEqual(rule.firings_per_run(2, [1, 4]), [8, 8])
        self.assertEqual(rule.firings_per_run(2, [4, 1]), [8, 2])

    def test_the_links_need_not_be_in_unit_order(self):
        rule = GroupRule([unit("sum", L=1, inputs=0), unit("mul")], [link("mul", "sum", 1)])
        self.assertEqual(rule.order, [1, 0])
        self.assertEqual(rule.output, 0)
        self.assertEqual(rule.firings_per_run(1, [4, 1]), [4, 4])


class Refused(unittest.TestCase):
    def test_a_fork(self):
        with self.assertRaisesRegex(GroupError, r"unit a has 2 out-edges \(a fork\)"):
            GroupRule([unit("a"), unit("b", inputs=0), unit("c", inputs=0)],
                      [link("a", "b"), link("a", "c")])

    def test_a_join(self):
        with self.assertRaisesRegex(GroupError, r"unit c has 2 in-edges \(a join\)"):
            GroupRule([unit("a"), unit("b"), unit("c", inputs=0)],
                      [link("a", "c"), link("b", "c", to_input=1)])

    def test_a_cycle(self):
        with self.assertRaisesRegex(GroupError, "cycle"):
            GroupRule([unit("a"), unit("b")], [link("a", "b"), link("b", "a")])

    def test_two_chains(self):
        with self.assertRaisesRegex(GroupError, "units a, b have no out-edge"):
            GroupRule([unit("a"), unit("b")], [])

    def test_an_unknown_unit(self):
        with self.assertRaisesRegex(GroupError, "no unit c"):
            GroupRule([unit("a"), unit("b")], [link("a", "c")])


def unit_case(path):
    """A unit case's header and its cycle lines: per cycle the input valids, the output's
    ready, then the expected fire, push and busy."""
    head, cycles, in_cycles = {}, [], False
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].split()
        if not line:
            continue
        if in_cycles:
            cycles.append([int(x) for x in line])
        elif line[0] == "cycles":
            in_cycles = True
        else:
            head.setdefault(line[0], []).append(line[1:])
    return head, cycles


class OneUnit(unittest.TestCase):
    """A group of one unit and no links is the unit cases' rule: every case with one start, in
    cycle 0, stepped through the rule, cycle by cycle and its run line."""

    CASES = sorted(p for p in UNIT_CASES.glob("*.txt")
                   if re.findall(r"^start ", p.read_text(), re.M) == ["start "]
                   and re.search(r"^start 0 \d+ \d+ taken$", p.read_text(), re.M))

    def test_there_are_cases(self):
        self.assertGreaterEqual(len(self.CASES), 3)

    def test_the_unit_cases(self):
        for path in self.CASES:
            head, cycles = unit_case(path)
            n_in = int(head.get("inputs", [["2"]])[0][0])
            _, jobs, t, _ = head["start"][0]
            rule = GroupRule([unit("u", L=int(head.get("latency", [["0"]])[0][0]),
                                   ii=int(head.get("ii", [["1"]])[0][0]))], [])
            rows, end = rule.run(int(jobs), [int(t)], lambda c: cycles[c][:n_in],
                                 lambda c: cycles[c][n_in], len(cycles))
            with self.subTest(case=path.stem):
                got = [[*r[2][0], r[4]] for r in rows]
                self.assertEqual(got, [c[n_in + 1:] for c in cycles])
                cls = totals(rows)
                run = (f"index=0 firings={sum(r[2][0][0] for r in rows)} "
                       + " ".join(f"{k}={cls[k]}" for k in CLASSES))
                self.assertEqual(head["expect"][0], ["run", *run.split()])

    def test_recomputed_busy_cycles(self):
        # The busy cycles E - s the cases state in their comments
        for name, busy in (("pipelined_l2_backpressure", 10), ("pipelined_rate_t4", 9),
                           ("lockstep_out_not_ready", 7)):
            head, cycles = unit_case(UNIT_CASES / f"{name}.txt")
            n_in = int(head.get("inputs", [["2"]])[0][0])
            _, jobs, t, _ = head["start"][0]
            rule = GroupRule([unit("u", L=int(head["latency"][0][0]),
                                   ii=int(head["ii"][0][0]))], [])
            rows, end = rule.run(int(jobs), [int(t)], lambda c: cycles[c][:n_in],
                                 lambda c: cycles[c][n_in], len(cycles))
            with self.subTest(case=name):
                self.assertEqual(end, busy)
                self.assertEqual(sum(totals(rows).values()), busy)


if __name__ == "__main__":
    unittest.main()
