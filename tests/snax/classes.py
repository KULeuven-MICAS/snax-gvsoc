#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""The class lines of a run's log against its summary lines (docs/EVENTS.md).

A unit's `run` line at E counts the classes of its busy cycles, n in all, so
the run covers E - n + 1 to E; a streamer's `mover` line at its end e those
of the mover's cycles, e - n + 1 to e. Per run, the class lines (`beats`,
level beat) must start at the span's first cycle, change class at every
line, lie inside a run's span, and the lengths of the runs of each class
(a line to the next one in the span, or to its end) must add up to the
summary line's count of that class. Equal, or fail.

parse() reads a trace file line by line: every line must be a trace line
(GVSoC's header, then `<cycle> <kind> <key>=<value> ...`), and a `run`,
`mover` or `class` line must have its fields, its counts integers. Any other
line fails with the file and its line number, never skipped: a line cut in
two by another writer turns into a wrong count when skipped. regress.py's
counter check reads the unit's `run` lines from the same parse.

`python3 tests/snax/classes.py LOG ...` checks each log, which needs the
components' `summary` and `beats` traces on and nothing else in it, and
exits 1 on the first failure; regress.py calls parse() and check() on the
forge/ fixtures' trace.log.
"""

import re
import sys
from collections import namedtuple

LINE = re.compile(r"^ *\d+: +-?\d+: \[(?:\x1b\[\d+m)?(?P<path>\S+)/(?P<trace>\w+) *(?:\x1b\[\d+m)?\]"
                  r" (?P<cycle>-?\d+) (?P<kind>\w+)(?P<fields>(?: [^\s=]+=\S+)*)$")
UNIT_CLASSES = ["busy", "stall_in", "stall_out", "flush"]
MOVER_CLASSES = ["busy", "stall_xbar", "stall_fifo", "idle"]
# The fields a line of these kinds must have, and those of them that are counts
FIELDS = {"run": ["index", "firings", *UNIT_CLASSES], "mover": ["mover", "run", *MOVER_CLASSES],
          "class": ["mode"]}
COUNTS = {"run": FIELDS["run"], "mover": FIELDS["mover"][1:], "class": []}

Line = namedtuple("Line", "number path trace cycle kind fields")


class LineError(ValueError):
    """A line of a trace file that does not parse; the message names the file
    and the line number."""


def parse(text, name="trace.log"):
    """Every line of a trace file as a Line (module doc); a LineError naming
    name and the line number on the first one that does not parse."""
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        m = LINE.match(line)
        if m is None:
            raise LineError(f"{name} line {number}: not a trace line: {line!r}")
        fields = dict(f.split("=", 1) for f in m.group("fields").split())
        kind, path = m.group("kind"), m.group("path")
        need = FIELDS.get(kind, []) + (["mover"] if kind == "class" and path.endswith("/streamer")
                                       else [])
        missing = [f for f in need if f not in fields]
        if missing:
            raise LineError(f"{name} line {number}: a {kind} line without "
                            f"{', '.join(missing)}: {line!r}")
        bad = [f for f in COUNTS.get(kind, []) if not fields[f].isdigit()]
        if bad:
            raise LineError(f"{name} line {number}: {', '.join(bad)} not an integer: {line!r}")
        out.append(Line(number, path, m.group("trace"), int(m.group("cycle")), kind, fields))
    return out


def unit_runs(parsed):
    """The unit's `run` lines by index: [firings, busy, stall_in, stall_out, flush]."""
    return {int(x.fields["index"]): [int(x.fields[f]) for f in FIELDS["run"][1:]]
            for x in parsed if x.kind == "run"}


def runs(parsed):
    """Per (component path, mover or None): its runs as (name, end, counts)
    and its class lines as (cycle, mode), in the log's order."""
    spans, lines = {}, {}
    for x in parsed:
        key = (x.path, x.fields.get("mover"))
        if x.kind == "class":
            lines.setdefault(key, []).append((x.cycle, x.fields["mode"]))
        elif x.kind == "run":
            counts = {c: int(x.fields[c]) for c in UNIT_CLASSES}
            spans.setdefault(key, []).append((f"run {x.fields['index']}", x.cycle, counts))
        elif x.kind == "mover":
            counts = {c: int(x.fields[c]) for c in MOVER_CLASSES}
            spans.setdefault(key, []).append((f"run {x.fields['run']}", x.cycle, counts))
    return spans, lines


def check(parsed):
    """None when every run's class lines match its summary line, else why not;
    parsed as parse() gives it. A log without class lines fails: the beats
    trace must be on."""
    spans, lines = runs(parsed)
    if not lines:
        return "no class lines: the beats trace is off"
    for key, items in sorted(spans.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        where = key[0] + (f" {key[1]}" if key[1] else "")
        todo = sorted(lines.get(key, []))
        for name, end, counts in items:
            first = end - sum(counts.values()) + 1
            mine = [(c, mode) for c, mode in todo if first <= c <= end]
            todo = [(c, mode) for c, mode in todo if not first <= c <= end]
            if not mine or mine[0][0] != first:
                return f"{where} {name}: no class line at its first cycle {first}"
            got = dict.fromkeys(counts, 0)
            for i, (cycle, mode) in enumerate(mine):
                if mode not in got:
                    return f"{where} {name}: class {mode} at {cycle} is not one of {list(got)}"
                if i > 0 and mine[i - 1][1] == mode:
                    return f"{where} {name}: class {mode} at {cycle} repeats the one before"
                nxt = mine[i + 1][0] if i + 1 < len(mine) else end + 1
                got[mode] += nxt - cycle
            if got != counts:
                return f"{where} {name} ({first} to {end}): class runs {got}, summary {counts}"
        if todo:
            return f"{where}: class line at {todo[0][0]} outside every run"
    for key in lines:
        if key not in spans:
            return f"{key[0]} {key[1] or ''}: class lines without a summary line"
    return None


def main():
    for path in sys.argv[1:]:
        with open(path, errors="replace") as f:
            text = f.read()
        try:
            why = check(parse(text, path))
        except LineError as e:
            print(e)  # it names the file and the line
            return 1
        if why is not None:
            print(f"{path}: {why}")
            return 1
        print(f"{path}: class lines match the summary lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
