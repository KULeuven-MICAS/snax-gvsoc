# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of classes.py's parse() and check(), and of regress.py's
check_traces() on a forge/ run's trace.log. Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

The log is one run written by hand in GVSoC's header and docs/EVENTS.md's
grammar: the unit starts at 10 and ends at 20 (stall_in 11-12, busy 13-20),
reader0 ends at 21 (busy 11-18, idle 19-21).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classes  # noqa: E402
import regress  # noqa: E402

UNIT = "/chip/soc/cluster_0/snax_acc0/unit"
STREAMER = "/chip/soc/cluster_0/snax_acc0/streamer"


def line(path, trace, cycle, rest):
    return f"{cycle}00000: {cycle}: [\x1b[34m{path}/{trace:<20}\x1b[0m] {cycle} {rest}"


LOG = [
    line(UNIT, "events", 10, "start count=8 rate=1"),
    line(STREAMER, "beats", 11, "class mover=reader0 mode=busy"),
    line(UNIT, "beats", 11, "class mode=stall_in"),
    line(UNIT, "beats", 13, "class mode=busy"),
    line(UNIT, "beats", 13, "fire n=0 b=0,0 value=0x1,0x2"),
    line(STREAMER, "beats", 19, "class mover=reader0 mode=idle"),
    line(UNIT, "summary", 20, "run index=0 firings=8 busy=8 stall_in=2 stall_out=0 flush=0"),
    line(STREAMER, "summary", 21,
         "mover mover=reader0 run=0 busy=8 stall_xbar=0 stall_fifo=0 idle=3 qmax=1,1"),
]
CLASS = 5  # LOG[CLASS] is a streamer class line, line 6 of the file


def cut(lines, k, at):
    """The log with line k cut in two after `at` characters of it."""
    return [*lines[:k], lines[k][:at], lines[k][at:], *lines[k + 1:]]


class Parse(unittest.TestCase):
    def test_a_whole_log_parses_and_its_classes_match(self):
        parsed = classes.parse("\n".join(LOG) + "\n")
        self.assertEqual([x.kind for x in parsed],
                         ["start", "class", "class", "class", "fire", "class", "run", "mover"])
        self.assertEqual(classes.unit_runs(parsed), {0: [8, 8, 2, 0, 0]})
        self.assertIsNone(classes.check(parsed))

    def test_a_cut_class_line_fails_naming_the_file_and_the_line(self):
        # "... class mover=reader0 mode=id" | "le": the head parses, the tail does not
        text = "\n".join(cut(LOG, CLASS, len(LOG[CLASS]) - 2))
        with self.assertRaises(classes.LineError) as e:
            classes.parse(text, "work/forge.vecadd/trace.log")
        self.assertEqual(str(e.exception), "work/forge.vecadd/trace.log line 7: not a trace "
                         "line: 'le'")
        # "... class mover=reader0 mod" | "e=idle": the head does not
        with self.assertRaises(classes.LineError) as e:
            classes.parse("\n".join(cut(LOG, CLASS, len(LOG[CLASS]) - 6)), "trace.log")
        self.assertTrue(str(e.exception).startswith("trace.log line 6: not a trace line: "))

    def test_a_class_line_cut_at_a_field_lacks_it(self):
        head = LOG[CLASS][:LOG[CLASS].index(" mode=")]  # "... class mover=reader0"
        with self.assertRaises(classes.LineError) as e:
            classes.parse("\n".join([*LOG[:CLASS], head]), "trace.log")
        self.assertIn("trace.log line 6: a class line without mode", str(e.exception))

    def test_a_run_line_cut_in_a_count_fails(self):
        run = LOG[6]
        for at in (run.index("busy=") + 6, run.index(" stall_in")):
            with self.assertRaises(classes.LineError):
                classes.parse("\n".join(cut(LOG, 6, at)))

    def test_any_other_line_fails(self):
        for other in ("forge cycles: 226", "", "12: 12: [x/beats] 12"):
            with self.assertRaises(classes.LineError) as e:
                classes.parse("\n".join([*LOG[:3], other, *LOG[3:]]))
            self.assertIn("line 4: not a trace line", str(e.exception))


class CheckTraces(unittest.TestCase):
    """regress.py's checks of a forge/ run read trace.log through parse()."""

    def run_checks(self, trace_lines):
        with tempfile.TemporaryDirectory() as d:
            log, traces = Path(d) / "run.log", Path(d) / "trace.log"
            log.write_text("forge cycles: 30\nforge counter add_acc: 10\nforge errors: 0\n")
            traces.write_text("\n".join(trace_lines) + "\n")
            manifest = {"trace": "snax_acc0/unit", "tasks": [{"name": "add_acc", "beats": 8}]}
            why, where = regress.check_traces(
                log, traces, lambda text, parsed: regress.check_counters(text, parsed, manifest))
            return why, None if where is None else where.name

    def test_a_whole_trace_passes_both_checks(self):
        self.assertEqual(self.run_checks(LOG), (None, None))

    def test_a_cut_class_line_fails_the_run(self):
        why, where = self.run_checks(cut(LOG, CLASS, len(LOG[CLASS]) - 2))
        self.assertEqual(where, "trace.log")
        self.assertTrue(why.endswith("trace.log line 7: not a trace line: 'le'"), why)

    def test_a_cut_run_line_fails_the_run_not_the_counter(self):
        why, where = self.run_checks(cut(LOG, 6, LOG[6].index(" flush")))
        self.assertEqual(where, "trace.log")
        self.assertIn("line 7: a run line without flush", why)


class TwoUnits(unittest.TestCase):
    """An accelerator of two groups (snax-forge D148, forge/dot_1): each task's counter is
    checked against its own unit's runs, from its trace path in the manifest."""

    MANIFEST = {"trace": "snax_acc0", "tasks": [
        {"name": "mult_mul", "beats": 8, "trace": "snax_acc0/unit_mul"},
        {"name": "sum_sum", "beats": 4, "trace": "snax_acc0/unit_sum"}]}

    def parsed(self):
        mul, total = (f"/chip/soc/cluster_0/snax_acc0/unit_{u}" for u in ("mul", "sum"))
        return classes.parse("\n".join([
            line(mul, "summary", 20, "run index=0 firings=8 busy=8 stall_in=2 stall_out=0 flush=0"),
            line(total, "summary", 40, "run index=0 firings=4 busy=4 stall_in=1 stall_out=0 flush=1"),
        ]) + "\n")

    def test_each_task_against_its_unit(self):
        log = "forge counter mult_mul: 10\nforge counter sum_sum: 6\n"
        self.assertIsNone(regress.check_counters(log, self.parsed(), self.MANIFEST))
        self.assertEqual(regress.task_traces(self.MANIFEST),
                         ["snax_acc0/unit_mul", "snax_acc0/unit_sum"])
        self.assertEqual(classes.unit_runs(self.parsed(), "snax_acc0/unit_sum"),
                         {0: [4, 4, 1, 0, 1]})

    def test_a_counter_of_the_other_unit_fails(self):
        log = "forge counter mult_mul: 10\nforge counter sum_sum: 10\n"
        why = regress.check_counters(log, self.parsed(), self.MANIFEST)
        self.assertTrue(why.startswith("sum_sum: counter 10"), why)


if __name__ == "__main__":
    unittest.main()
