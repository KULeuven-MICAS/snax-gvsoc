#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""snax/snax_group_rule.py: the dot variants against the control rule's formulas, the groups it refuses,
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




class Refused(unittest.TestCase):
    def test_a_fork(self):
        with self.assertRaisesRegex(GroupError, r"unit a has 2 out-edges \(a fork\)"):
            GroupRule([unit("a"), unit("b", inputs=0), unit("c", inputs=0)],
                      [link("a", "b"), link("a", "c")])

    def test_a_cycle(self):
        with self.assertRaisesRegex(GroupError, "cycle"):
            GroupRule([unit("a"), unit("b")], [link("a", "b"), link("b", "a")])

    def test_two_chains(self):
        with self.assertRaisesRegex(GroupError, "the chains ending at a and at b: no fork joins them"):
            GroupRule([unit("a"), unit("b")], [])

    def test_an_unknown_unit(self):
        with self.assertRaisesRegex(GroupError, "no unit c"):
            GroupRule([unit("a"), unit("b")], [link("a", "c")])


class Fork(unittest.TestCase):
    """Two chains on one reader: bicg's one pass at N = W, q by vmul -> sum, s by mac."""

    def group(self, depth=1, **kw):
        us = [unit("vmul"), unit("sum", L=1, inputs=0), unit("mac", L=1)]
        return GroupRule(us, [link("vmul", "sum", depth)], forks=[[("vmul", 0), ("mac", 0)]],
                         **kw)

    def test_unequal_firings_never_end(self):
        # NB (D189): LOWER refuses this; the group waits for mac's partner for ever
        _, end = self.group().run([4, 2], [1, 1, 4], lambda c: (1, 1, 1), lambda c: (1, 1), 64)
        self.assertIsNone(end)

    def test_several_chains_take_jobs_and_ready_per_output(self):
        with self.assertRaisesRegex(GroupError, "jobs 4: a group of 2 chains takes one per"):
            self.group().firings_per_run(4, [1, 1, 4])
        with self.assertRaisesRegex(GroupError, r"ready \[1\]: one per output, 2"):
            self.group().run([4, 1], [1, 1, 4], lambda c: (1, 1, 1), lambda c: [1], 4)

    def test_with_every_input_there_the_run_is_the_longer_chains(self):
        for depth in (0, 1):
            rows, end = self.group(depth).run([4, 1], [1, 1, 4], lambda c: (1, 1, 1),
                                              lambda c: (1, 1), 32)
            q = GroupRule([unit("vmul"), unit("sum", L=1, inputs=0)], [link("vmul", "sum", depth)])
            mac = GroupRule([unit("mac", L=1)], [])
            alone = [q.run(4, [1, 1], lambda c: (1, 1), lambda c: 1, 32)[1],
                     mac.run(1, [4], lambda c: (1, 1), lambda c: 1, 32)[1]]
            with self.subTest(depth=depth):
                self.assertEqual(end, max(alone))


class ForkRefused(unittest.TestCase):

    def test_a_member_fed_by_a_link(self):
        with self.assertRaisesRegex(GroupError, "sum is fed by a link; a fork feeds chains' heads"):
            GroupRule([unit("mul"), unit("sum", inputs=1), unit("mac")], [link("mul", "sum")],
                      forks=[[("sum", 0), ("mac", 0)]])

    def test_a_seed(self):
        with self.assertRaisesRegex(GroupError, "mac has no outer input 1 that is not its seed"):
            GroupRule([unit("a"), dict(unit("mac"), seed=True)], [],
                      forks=[[("a", 0), ("mac", 1)]])

    def test_a_span(self):
        with self.assertRaisesRegex(GroupError, "b has span 4"):
            GroupRule([unit("a"), unit("b", span=4)], [], forks=[[("a", 0), ("b", 0)]])

    def test_one_member(self):
        with self.assertRaisesRegex(GroupError, "gives one input to two or more units"):
            GroupRule([unit("a")], [], forks=[[("a", 0)]])

    def test_an_input_in_two_forks(self):
        with self.assertRaisesRegex(GroupError, "a.0 is in another fork too"):
            GroupRule([unit("a"), unit("b"), unit("c")], [],
                      forks=[[("a", 0), ("b", 0)], [("a", 0), ("c", 0)]])

    def test_outputs_that_are_not_the_sinks(self):
        with self.assertRaisesRegex(GroupError, r"outputs \['mul', 'mac'\]: each chain's sink"):
            GroupRule([unit("mul"), unit("sum", inputs=0), unit("mac")], [link("mul", "sum")],
                      output=["mul", "mac"], forks=[[("mul", 0), ("mac", 0)]])


class Bank(unittest.TestCase):
    """A banked Mac with r held: one job of M rows, ROWS beats a row."""

    def mac(self, rows=2, hold=(1,)):
        return GroupRule([dict(unit("mac", L=1), rows=rows, hold=list(hold))], [])

    def test_refused(self):
        for kw, text in (({"rows": 0}, "a bank has one row or more"),
                         ({"rows": 1, "hold": [1]}, "it has no bank"),
                         ({"rows": 2, "hold": [2]}, "not an outer input of its own")):
            with self.subTest(**kw), self.assertRaisesRegex(GroupError, text):
                GroupRule([dict(unit("mac", L=1), **kw)], [])
        with self.assertRaisesRegex(GroupError, "it is a chain's sink"):
            GroupRule([dict(unit("mac", L=1), rows=2), unit("sum", L=1, inputs=0)],
                      [link("mac", "sum")])
        with self.assertRaisesRegex(GroupError, "T 5 is not a multiple of its 2 rows"):
            self.mac().run(1, [5], lambda c: (1, 1), lambda c: 1, 4)


class Atax(unittest.TestCase):
    """atax's one group: vmul -> sum gives t[i] once a row into mac's bank over a held link
    (y += A[i] t[i]); mac reads A again, or takes vmul's forked A through a buffer of depth D.
    T = N // W beats a row, the bank has ROWS = T rows, M rows of A."""

    def units(self, rows, mac_inputs):
        return [unit("vmul"), unit("sum", L=1, inputs=0),
                dict(unit("mac", L=1, inputs=mac_inputs), rows=rows)]

    def links(self, depth=1):
        return [link("vmul", "sum", 1), dict(link("sum", "mac", depth, 1), hold=True)]

    def two_reads(self, m, rows):
        g = GroupRule(self.units(rows, 1), self.links())
        return g, g.run(1, [1, rows, m * rows], lambda c: (1, 1, 1), lambda c: 1, 2000)[1]

    def one_read(self, m, rows, depth):
        g = GroupRule(self.units(rows, 0), self.links(),
                      forks=[[("vmul", 0)]], fork_links=[{"fork": 0, "to": "mac", "to_input": 0,
                                                          "depth": depth}])
        return g.run(1, [1, rows, m * rows], lambda c: (1, 1), lambda c: 1, 2000)[1]

    def test_t_is_taken_once_a_row(self):
        # sum fires T times a row and gives once; mac fires T times a row and takes t once
        for m, rows in ((3, 2), (64, 8), (64, 4)):
            g, end = self.two_reads(m, rows)
            with self.subTest(m=m, rows=rows):
                self.assertEqual(g.firings_per_run(1, [1, rows, m * rows]), [m * rows] * 3)
                self.assertIsNotNone(end)
                # t[0] after vmul's T beats and sum's latency, then one row a T cycles
                self.assertEqual(end, rows + 3 + m * rows)

    def test_a_buffer_of_t_plus_2_runs_as_a_second_read(self):
        for m, rows in ((3, 2), (64, 8), (64, 4)):
            with self.subTest(m=m, rows=rows):
                self.assertEqual(self.one_read(m, rows, rows + 2), self.two_reads(m, rows)[1])

    def test_a_buffer_of_t_stalls(self):
        for m, rows in ((3, 2), (64, 8)):
            end = self.one_read(m, rows, rows)
            with self.subTest(m=m, rows=rows):
                self.assertIsNotNone(end)
                self.assertGreater(end, self.two_reads(m, rows)[1])

    def test_a_buffer_below_t_never_ends(self):
        # NB (D196): LOWER refuses D < T; the fork waits for room that mac's first t never frees
        for m, rows in ((3, 2), (64, 8)):
            with self.subTest(m=m, rows=rows):
                self.assertIsNone(self.one_read(m, rows, rows - 1))

    def test_refused(self):
        with self.assertRaisesRegex(GroupError, "a held link is a buffer into a bank"):
            GroupRule(self.units(1, 1), self.links())
        with self.assertRaisesRegex(GroupError, "a held link is a buffer into a bank"):
            GroupRule(self.units(2, 1), self.links(depth=0))
        for depth, text in ((0, "a buffer of depth 1 or more"),
                            (2, "not after the fork's units")):
            to = "mac" if depth == 0 else "vmul"
            with self.subTest(depth=depth), self.assertRaisesRegex(GroupError, text):
                GroupRule(self.units(2, 0), self.links(), forks=[[("vmul", 0)]],
                          fork_links=[{"fork": 0, "to": to, "to_input": 0, "depth": depth}])


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
                                   ii=int(head.get("ii", [["1"]])[0][0]), inputs=n_in)], [])
            rows, end = rule.run(int(jobs), [int(t)], lambda c: cycles[c][:n_in],
                                 lambda c: cycles[c][n_in], len(cycles))
            with self.subTest(case=path.stem):
                got = [[*r[2][0], r[4]] for r in rows]
                self.assertEqual(got, [c[n_in + 1:] for c in cycles])
                cls = totals(rows)
                run = (f"index=0 firings={sum(r[2][0][0] for r in rows)} "
                       + " ".join(f"{k}={cls[k]}" for k in CLASSES))
                self.assertEqual(head["expect"][0], ["run", *run.split()])


if __name__ == "__main__":
    unittest.main()
