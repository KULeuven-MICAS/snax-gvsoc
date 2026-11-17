# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests of snapshots.py's check_end() and check_window(), and of
regress.py's check_quiet() and run_mark(). Run from snax-gvsoc:

    python3 -m unittest discover -s tests/snax -p 'test_*.py'

The log is a quiet run written by hand in GVSoC's header and docs/EVENTS.md's
grammar, as forge/dot_3's: a linked group (mul, sum), one reader, a crossbar of
two inputs and one bank; marks 1 at 100 and 2 at 200 around the group's one run
(10 to 140) and the streamer's (reader0 ends at 142), the end at 300.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classes  # noqa: E402
import regress  # noqa: E402
import snapshots  # noqa: E402

GROUP = "/chip/soc/cluster_0/snax_acc0/group_dot"
STREAMER = "/chip/soc/cluster_0/snax_acc0/streamer_dot"
XBAR = "/chip/soc/cluster_0/tcdm/snax_xbar"


def line(path, cycle, rest):
    return f"{cycle}00000: {cycle}: [\x1b[34m{path}/summary  \x1b[0m] {cycle} {rest}"


def snap(cycle, mark, group, mul, total, reader, inputs, bank):
    """One snapshot of every component; group, reader, each input and bank their counts."""
    return [
        line(GROUP, cycle, f"snap mark={mark} busy={group[0]} stall_in={group[1]} "
                           f"stall_out={group[2]} flush={group[3]}"),
        line(GROUP, cycle, f"snap mark={mark} unit=mul firings={mul[0]} pushes={mul[1]}"),
        line(GROUP, cycle, f"snap mark={mark} unit=sum firings={total[0]} pushes={total[1]}"),
        *(line(XBAR, cycle, f"snap mark={mark} input={i} grants={g} stalls={s}")
          for i, (g, s) in enumerate(inputs)),
        line(XBAR, cycle, f"snap mark={mark} bank=0 reads={bank[0]} writes={bank[1]} "
                          f"conflicts={bank[2]}"),
        line(STREAMER, cycle, f"snap mark={mark} mover=reader0 busy={reader[0]} "
                              f"stall_xbar={reader[1]} stall_fifo={reader[2]} idle={reader[3]}"),
    ]


ZERO = ((0, 0, 0, 0), (0, 0), (0, 0), (0, 0, 0, 0), [(0, 0), (5, 0)], (0, 0, 0))
RUN = ((128, 3, 0, 1), (128, 128), (128, 1), (128, 1, 0, 3), [(128, 1), (9, 0)], (128, 0, 1))
END = ((128, 3, 0, 1), (128, 128), (128, 1), (128, 1, 0, 3), [(128, 1), (12, 0)], (128, 0, 1))
LOG = [
    *snap(100, 1, *ZERO),
    line(GROUP, 140, "run index=0 firings=128 busy=128 stall_in=3 stall_out=0 flush=1"),
    line(STREAMER, 142, "mover mover=reader0 run=0 busy=128 stall_xbar=1 stall_fifo=0 idle=3 "
                        "qmax=2"),
    *snap(200, 2, *RUN),
    line(XBAR, 300, "input index=0 name=reader0.lane0 grants=128 stalls=1 stalls_dma=0 "
                    "whole_run=0"),
    line(XBAR, 300, "input index=1 name=core0 grants=12 stalls=0 stalls_dma=0 whole_run=1"),
    line(XBAR, 300, "bank index=0 reads=128 writes=0 conflicts=1"),
    *snap(300, -1, *END),
]


def parsed(lines=LOG):
    return classes.parse("\n".join(lines) + "\n")


class Snapshots(unittest.TestCase):
    def test_lines_group_into_snapshots_per_component(self):
        snaps = snapshots.snapshots(parsed())
        self.assertEqual([s.mark for s in snaps[GROUP]], [1, 2, -1])
        self.assertEqual(snaps[XBAR][2].items[("input", "1")], [12, 0])
        self.assertEqual(snaps[GROUP][1].items[("unit", "sum")], [128, 1])
        self.assertEqual((snaps[STREAMER][2] - snaps[STREAMER][0])[("mover", "reader0")],
                         [128, 1, 0, 3])

    def test_the_log_passes_both_checks(self):
        self.assertIsNone(snapshots.check_end(parsed()))
        self.assertIsNone(snapshots.check_window(parsed(), 1))

    def test_an_end_off_the_input_lines_fails_with_the_numbers(self):
        log = [x.replace("grants=12 stalls=0", "grants=13 stalls=0") if "mark=-1" in x else x
               for x in LOG]
        self.assertEqual(snapshots.check_end(parsed(log)),
                         f"{XBAR} mark=-1 input=1 (snapshot vs lines): grants 13 vs 12")

    def test_an_end_off_the_run_lines_fails(self):
        log = [x.replace("flush=1", "flush=2") if "mark=-1" in x else x for x in LOG]
        self.assertIn("group (snapshot vs lines): flush 2 vs 1", snapshots.check_end(parsed(log)))

    def test_no_end_snapshot_fails(self):
        why = snapshots.check_end(parsed([x for x in LOG if "mark=-1" not in x]))
        self.assertIn("0 snapshot(s) of mark -1, the last mark 2", why)

    def test_summary_lines_without_snapshots_fail(self):
        why = snapshots.check_end(parsed([x for x in LOG if "snap" not in x]))
        self.assertTrue(why.endswith("summary lines but no snap line"), why)

    def test_a_window_off_the_run_fails_with_its_cycles_and_numbers(self):
        log = [x.replace("busy=128 stall_xbar=1", "busy=126 stall_xbar=1")
               if "mark=2" in x else x for x in LOG]
        self.assertEqual(snapshots.check_window(parsed(log), 1),
                         f"{STREAMER} window 1 (cycles 100 to 200) mover=reader0 "
                         "(window vs lines): busy 126 vs 128")

    def test_the_window_of_another_mark_fails(self):
        why = snapshots.check_window(parsed(), 2)
        self.assertIn("window 2 (cycles 200 to 300) group (window vs lines): busy 0 vs 128", why)

    def test_one_unit_firings_against_the_run(self):
        one = [x for x in LOG if "unit=sum" not in x]
        self.assertIsNone(snapshots.check_window(parsed(one), 1))
        off = [x.replace("unit=mul firings=128", "unit=mul firings=127") if "mark=2" in x
               else x for x in one]
        self.assertTrue(snapshots.check_window(parsed(off), 1).endswith(
            "unit=mul: firings 127 vs the run's 128"))


class Regress(unittest.TestCase):
    def test_check_quiet_reads_trace_log(self):
        with tempfile.TemporaryDirectory() as d:
            traces = Path(d) / "trace.log"
            traces.write_text("\n".join(LOG) + "\n")
            self.assertIsNone(regress.check_quiet(traces, 1))
            self.assertIsNone(regress.check_quiet(traces, None))
            traces.write_text("\n".join([*LOG, "forge"]) + "\n")
            self.assertIn("not a trace line", regress.check_quiet(traces, 1))

    def test_run_mark_of_the_fixtures(self):
        self.assertEqual(regress.run_mark("dot_3"), 5)
        self.assertIsNone(regress.run_mark("dot_1"))


if __name__ == "__main__":
    unittest.main()
