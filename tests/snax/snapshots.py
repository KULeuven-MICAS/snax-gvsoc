#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""The snap lines of a run's log against its summary lines (docs/EVENTS.md,
Snapshots).

A component's snapshots are its snap lines, running totals since boot, one
snapshot per mark written (a line per input and bank of the crossbar and one
for its copies, a line per group and per unit, a line per mover). Window k is snapshot k + 1 minus
snapshot k. Two checks, each equal or fail, with the numbers:

- check_end(): the last snapshot of every component is mark=-1 and equals its
  whole-run lines: the crossbar's `input`, `bank` and `copies` lines, the sum of a
  group's `run` lines (the classes, and the firings of a group of one unit),
  the sum of each mover's `mover` lines. A component with summary lines and no
  snapshot fails.
- check_window(mark): in a log of one accelerator run, the window from the
  snapshot of mark to the next equals the run: a group's one `run` line (the
  classes, and the firings of a group of one unit), each mover's one `mover`
  line.

Both read the lines classes.parse() gives. regress.py runs check_end() on
every forge run and both on the quiet build of a fixture with one `run` mark
in its obs_marks.json. `python3 tests/snax/snapshots.py LOG [MARK]` checks a
log, which needs the components' `summary` traces on and nothing else in it;
with MARK, the window from it too.
"""

import sys

import classes

# A snap line's item: the field naming it (None for a group's own line; "copies" for the
# crossbar's line of the DMA's copies inside L1, which names no item), and its counts
COUNTS = {"input": ["grants", "stalls"], "bank": ["reads", "writes", "conflicts"],
          "unit": ["firings", "pushes"], "mover": classes.MOVER_CLASSES,
          "copies": classes.FIELDS["copies"], None: classes.UNIT_CLASSES}
# The crossbar's whole-run lines a snap line of the same item must equal
XBAR_KINDS = ("input", "bank", "copies")


class Snapshot:
    """One snapshot of a component: its cycle, its mark, and per item ((field, name),
    (None, None) for a group's own line, ("copies", None) for the crossbar's copies) its
    counts in COUNTS' order."""

    def __init__(self, cycle, mark):
        self.cycle = cycle
        self.mark = mark
        self.items = {}

    def __sub__(self, other):
        """The window from other to this one, per item of this one."""
        return {k: [a - b for a, b in zip(v, other.items.get(k, [0] * len(v)))]
                for k, v in self.items.items()}


def snapshots(parsed):
    """Per component path, its snapshots in the log's order. A line starts a new snapshot
    when its cycle or mark differs from the one before or its item is in it already. A
    ValueError names the line of a count or a mark that is not an integer."""
    out = {}
    for x in parsed:
        if x.kind != "snap":
            continue
        field = next((f for f in ("input", "bank", "unit", "mover") if f in x.fields), None)
        if field is None and "copy_reads" in x.fields:
            field = "copies"
        key = (field, x.fields[field] if field in ("input", "bank", "unit", "mover") else None)
        try:
            mark = int(x.fields["mark"])
            counts = [int(x.fields[f]) for f in COUNTS[field]]
        except (KeyError, ValueError):
            raise ValueError(f"line {x.number}: a snap line without its integer mark and "
                             f"{', '.join(COUNTS[field])}") from None
        snaps = out.setdefault(x.path, [])
        if not snaps or (snaps[-1].cycle, snaps[-1].mark) != (x.cycle, mark) \
                or key in snaps[-1].items:
            snaps.append(Snapshot(x.cycle, mark))
        snaps[-1].items[key] = counts
    return out


def whole_run(parsed):
    """Per component path, what its mark=-1 snapshot must equal, by item: the input, bank
    and copies lines; the group's run lines' classes added up; each mover's mover lines'
    classes added up. And per path the group's firings, its run lines' added up."""
    want, firings = {}, {}
    for x in parsed:
        items = want.setdefault(x.path, {}) if x.kind in (*XBAR_KINDS, "run",
                                                          "mover") else None
        if x.kind in ("input", "bank"):
            items[(x.kind, x.fields["index"])] = [int(x.fields[f]) for f in COUNTS[x.kind]]
        elif x.kind == "copies":
            items[("copies", None)] = [int(x.fields[f]) for f in COUNTS["copies"]]
        elif x.kind in ("run", "mover"):
            key = (None, None) if x.kind == "run" else ("mover", x.fields["mover"])
            field = None if x.kind == "run" else "mover"
            add = [int(x.fields[f]) for f in COUNTS[field]]
            items[key] = [a + b for a, b in zip(items.get(key, [0] * len(add)), add)]
            if x.kind == "run":
                firings[x.path] = firings.get(x.path, 0) + int(x.fields["firings"])
    return want, firings


def one_unit(snap):
    """The unit item of a group's snapshot of one unit, else None."""
    units = [k for k in snap.items if k[0] == "unit"]
    return units[0] if len(units) == 1 else None


def differ(path, what, got, want, fields):
    """Why got is not want, field by field."""
    return (f"{path} {what}: " + ", ".join(f"{f} {g} vs {w}" for f, g, w in
                                           zip(fields, got, want) if g != w))


def name(key):
    if key[0] is None:
        return "group"
    return key[0] if key[1] is None else f"{key[0]}={key[1]}"


def check_end(parsed):
    """None when every component's last snapshot is mark=-1 and equals its whole-run
    lines (module doc), else why not, with the numbers (snapshot vs lines)."""
    try:
        snaps = snapshots(parsed)
    except ValueError as e:
        return str(e)
    want, firings = whole_run(parsed)
    for path in want:
        if path not in snaps:
            return f"{path}: summary lines but no snap line"
    for path, items in sorted(snaps.items()):
        ends = [s for s in items if s.mark == -1]
        if len(ends) != 1 or items[-1].mark != -1:
            return (f"{path}: {len(ends)} snapshot(s) of mark -1, the last mark "
                    f"{items[-1].mark}; one, the last, expected")
        end, lines = items[-1], want.get(path, {})
        for key in lines:
            if key not in end.items:
                return f"{path}: no snap line for {name(key)}"
        for key, got in end.items.items():
            if key[0] in XBAR_KINDS and key not in lines:
                return f"{path}: snap line for {name(key)} but no {key[0]} line"
            if key[0] == "unit":
                continue
            expected = lines.get(key, [0] * len(got))
            if got != expected:
                return differ(path, f"mark=-1 {name(key)} (snapshot vs lines)", got, expected,
                              COUNTS[key[0]])
        unit = one_unit(end)
        if unit is not None and end.items[unit][0] != firings.get(path, 0):
            return (f"{path} mark=-1 unit={unit[1]}: firings {end.items[unit][0]} vs the run "
                    f"lines' {firings.get(path, 0)}")
    return None


def check_window(parsed, mark):
    """None when, per component, the window from the snapshot of mark to the next equals
    the one run's group and mover lines (module doc), else why not, with the numbers
    (window vs lines). The crossbar has no per-run line: its window is not checked."""
    try:
        snaps = snapshots(parsed)
    except ValueError as e:
        return str(e)
    runs = {}
    for x in parsed:
        if x.kind == "run":
            runs.setdefault((x.path, None), []).append(x)
        elif x.kind == "mover":
            runs.setdefault((x.path, x.fields["mover"]), []).append(x)
    if not snaps:
        return "no snap line"
    for path, items in sorted(snaps.items()):
        at = [i for i, s in enumerate(items) if s.mark == mark]
        if len(at) != 1 or at[0] + 1 == len(items):
            return f"{path}: {len(at)} snapshot(s) of mark {mark}; one, not the last, expected"
        first, last = items[at[0]], items[at[0] + 1]
        window = last - first
        where = f"{path} window {mark} (cycles {first.cycle} to {last.cycle})"
        for key, got in window.items():
            if key[0] not in (None, "mover"):
                continue
            lines = runs.get((path, key[1]), [])
            if len(lines) != 1:
                return f"{path} {name(key)}: {len(lines)} run(s), one expected"
            want = [int(lines[0].fields[f]) for f in COUNTS[key[0]]]
            if got != want:
                return differ(where, f"{name(key)} (window vs lines)", got, want,
                              COUNTS[key[0]])
        unit = one_unit(last)
        if unit is not None and (path, None) in runs:
            want = int(runs[(path, None)][0].fields["firings"])
            if window[unit][0] != want:
                return f"{where} unit={unit[1]}: firings {window[unit][0]} vs the run's {want}"
    return None


def main():
    path = sys.argv[1]
    with open(path, errors="replace") as f:
        text = f.read()
    try:
        parsed = classes.parse(text, path)
    except classes.LineError as e:
        print(e)
        return 1
    why = check_end(parsed)
    if why is None and len(sys.argv) > 2:
        why = check_window(parsed, int(sys.argv[2]))
    if why is not None:
        print(f"{path}: {why}")
        return 1
    print(f"{path}: snapshots match the summary lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
