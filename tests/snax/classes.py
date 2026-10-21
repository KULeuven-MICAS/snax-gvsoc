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

`python3 tests/snax/classes.py LOG ...` checks each log, which needs the
components' `summary` and `beats` traces on, and exits 1 on the first
failure; regress.py calls check() on the forge/ fixtures' runs.
"""

import re
import sys

LINE = re.compile(r"\[(?:\x1b\[\d+m)?(?P<path>\S+)/(?P<trace>summary|beats)\s*(?:\x1b\[\d+m)?\]"
                  r" (?P<cycle>-?\d+) (?P<kind>run|mover|class)(?P<fields>( \S+=\S+)*)$")
UNIT_CLASSES = ["busy", "stall_in", "stall_out", "flush"]
MOVER_CLASSES = ["busy", "stall_xbar", "stall_fifo", "idle"]


def runs(text):
    """Per (component path, mover or None): its runs as (name, end, counts)
    and its class lines as (cycle, mode), in the log's order."""
    spans, lines = {}, {}
    for line in text.splitlines():
        m = LINE.search(line)
        if m is None:
            continue
        fields = dict(f.split("=", 1) for f in m.group("fields").split())
        cycle = int(m.group("cycle"))
        key = (m.group("path"), fields.get("mover"))
        if m.group("kind") == "class":
            lines.setdefault(key, []).append((cycle, fields["mode"]))
        elif m.group("kind") == "run":
            counts = {c: int(fields[c]) for c in UNIT_CLASSES}
            spans.setdefault(key, []).append((f"run {fields['index']}", cycle, counts))
        else:
            counts = {c: int(fields[c]) for c in MOVER_CLASSES}
            spans.setdefault(key, []).append((f"run {fields['run']}", cycle, counts))
    return spans, lines


def check(text):
    """None when every run's class lines match its summary line, else why not.
    A log without class lines fails: the beats trace must be on."""
    spans, lines = runs(text)
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
            why = check(f.read())
        if why is not None:
            print(f"{path}: {why}")
            return 1
        print(f"{path}: class lines match the summary lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
