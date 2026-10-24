#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""SNAX-GVSoC's regression, pass or finish: `make regress`.

First runs SnaxUnit's rule against its hand-worked cases
(tests/snax/unit/run.sh, g++ only; `unit`, passes when it exits 0), then
SnaxShell's rule with the unit's against its own (tests/snax/shell/run.sh;
`shell`, likewise). Then
builds sw/ (`make -C sw`: the runtime per cluster, the math library and
snax_cluster's plain tests, from the pinned copy) and the programs of
sw/apps/, then runs the cluster tests on `snax_hjson` with
forge/vecadd/'s cluster file (CLUSTER_DESIGN), named <program>.snax_hjson:
`dma-timing`, `snax-csr`, the seven `stream-timing` cases, the three
`core-tcdm` cases and the `dma-tcdm` case, each a plain run (exit code
only); then `snax-shell` on `snax_hjson` with forge/vecadd/'s cluster file
(SHELL_DESIGN: SnaxShell and SnaxUnit, a lockstep add), with the unit's
trace on and the counter check below; then
every folder of forge/ (FORGE_DIR) with the generic app `forge`
(snax-forge's generated main.c and data.h), named forge.<design>, and
`forge-reduce.vsum-r16` (FORGE_REDUCE: vsum with its len overridden to 16 by
hand, four sums, since no kernel gives T < n, snax-forge open item 81): the
fixture's manifest.json gives its cluster file, the unit's trace path and
each accelerator task's beats (the unit's `summary`, `events` and `beats`
traces under the trace path are on); it runs on `snax_hjson` with
`--param hjson=<cluster file>` (but for vecadd's, its components are not
the default file's, so gvrun warns and runs it on the JSON config), with the
counter checks;
then
the plain tests on the `snitch` target: one per sw/tests/*.c (the 17 of COPIED in sw/sync.py), each
from build/sw/tests/; a plain ELF missing is a failure.

A program passes when it exits 0 within TIMEOUT seconds: every SNAX program
returns its error count, but `stream-timing` and the `core-tcdm` cases other
than `subword`, which return 0. No other output or cycle count is
compared; the comparison with the RTL is made by hand (README, "Comparing
with the RTL").

The counter check (check_counter): a program on SnaxShell and
SnaxUnit prints the shell's counter after a unit run; it passes when the
counter is busy + stall_in + stall_out + flush of the unit's summary line
for that run (`run index=<k> ...` in trace.log, docs/EVENTS.md) and that run
fired the task's beats. A
hand-written program (snax-shell, forge-reduce) prints
`<program> counter: <n>` for run 0, its beats snax-shell's SHELL_BEATS or
the fixture's first task's; a generated one (check_counters) prints
`forge counter <task>: <n>` per accelerator task of its manifest, the k-th
task matched to run k.

The class check (classes.py): every forge/ fixture run above also has
the streamers' `summary`, `events` and `beats` traces on (CLASS_TRACES); it
passes when, per run of the unit and of each mover, the lengths of its
class runs (the `class` lines) add up per class to its summary line's
counts and cover its busy span exactly.

Both checks read trace.log through classes.parse(): a line of it that is not
a whole trace line fails the run, naming the file and the line number,
instead of being skipped (check_traces).

gvrun runs with PYTHONDONTWRITEBYTECODE=1, so no __pycache__ lands beside
the modules it imports. Each run's stdout and stderr go to build/regress/work/<name>/run.log, a
forge/ run's traces to trace.log beside it (GVSoC buffers its stdout, so the
program's output written there can cut a trace line in two); a failure
prints the file it read and its last lines. Under GitHub Actions
(GITHUB_ACTIONS=true) each failure also prints an `::error` line, an
annotation on the run naming the program, why and its log. `-k SUBSTRING`
runs only the programs whose name holds it.

Needs GVSoC built for the Makefile's SNAX_TARGETS
(`make build TARGETS='$(SNAX_TARGETS)'`). Exit code 0 when every program
passes, 1 otherwise.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import classes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SW = ROOT / "sw"
APPS = SW / "apps"
BUILD = ROOT / "build" / "sw"

# Generated accelerators, forge/<design>/ (forge/README.md): every folder, run
# on snax_hjson from its cluster file by the generic app
FORGE_DIR = ROOT / "forge"
FORGE_TARGET = "snax_hjson"
FORGE_APP = "forge"
# The cluster tests run on this fixture's cluster file (its manifest's), whose
# streamer and shell they are written for
CLUSTER_DESIGN = "vecadd"
CLUSTER_TESTS = ["dma-timing", "snax-csr"]
# snax-shell runs on this fixture's cluster file, whose CSRs and datapath it is
# written for, with the counter check; the beats of its first run are its
# RUN_BEATS, DATA_LEN 192 / 4 lanes / 3 runs
SHELL_DESIGN = "vecadd"
SHELL_BEATS = 16
# The hand-written forge-reduce on a fixture with its len overridden: (design,
# RATE_OVERRIDE). len 16 for vsum's T = N = 64, 4 sums per run, the
# multi-output path, which no kernel gives yet (T < n, snax-forge open item 81)
FORGE_REDUCE = [("vsum", 16)]
# The unit's traces a forge/ run writes below its manifest's trace path, and
# the streamers' for the class check, one --trace each (GVSoC compiles them as
# POSIX basic regexes: no +, no |): docs/EVENTS.md's only, not the components'
# own `comp` and `trace` lines, so every line of trace.log has its grammar
UNIT_TRACES = ("summary", "events", "beats")
CLASS_TRACES = [f"snax_acc[0-9]*/streamer/{t}$" for t in ("summary", "events", "beats")]
# The cluster tests built once into one ELF per case, <program>-<case>.elf
CASES = [
    ("stream-timing", ["zero_bound", "a_alone", "ab_other_banks", "ab_same_banks", "a_stride0",
                       "prio_queued", "idle_restart"]),
    ("core-tcdm", ["subword", "core_vs_reader", "after_stores"]),
    ("dma-tcdm", ["dma_vs_reader"]),
]
PLAIN_DIR = BUILD / "tests"
PLAIN_TESTS = sorted(c.stem for c in (SW / "tests").glob("*.c"))  # COPIED in sw/sync.py
WORK = ROOT / "build" / "regress" / "work"
TIMEOUT = 300  # seconds per program; each takes a few
TAIL = 20  # lines of a failed run's log printed
ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def gvrun(target, elf, workdir, log, options=()):
    """Runs one ELF, its output into log, options before the command;
    returns its exit code, or None when it does not finish."""
    env = dict(os.environ)
    env["PATH"] = f"{ROOT / 'install' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{ROOT / 'install' / 'python'}:{env.get('PYTHONPATH', '')}"
    # No __pycache__ beside the modules gvrun imports
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = ["gvrun", "--target", target, "--work-dir", str(workdir),
           "--param", f"chip/soc/binary={elf}", *options, "run"]
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "w") as out:
            p = subprocess.run(cmd, env=env, cwd=ROOT, stdout=out,
                               stderr=subprocess.STDOUT, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    return p.returncode


def cluster_file(design):
    """forge/<design>/'s cluster file, as its manifest names it (plain json: the manifest is
    snax-forge's, read without it)."""
    folder = FORGE_DIR / design
    return (folder / json.loads((folder / "manifest.json").read_text())["cluster"]).resolve()


def check_run(counter, lines, run, beats):
    """A counter against the unit's line for run `run` (lines: classes.unit_runs()),
    which must have fired beats times. Returns None when it holds, else why not."""
    if run not in lines:
        return f"no `run index={run}` line in the unit's trace"
    firings, *classes = lines[run]
    if firings != beats:
        return f"run {run} fired {firings} times, not {beats}"
    if counter != sum(classes):
        return (f"counter {counter}, run {run}'s busy + stall_in + stall_out + flush "
                f"{' + '.join(map(str, classes))} = {sum(classes)}")
    return None


def check_counter(program, log, lines, beats):
    """The counter check of a hand-written program: `<program> counter: <n>`
    in log (the program's output) against run 0 of lines (the unit's runs,
    classes.unit_runs()). Returns None when it holds, else why not."""
    counter = re.search(rf"^{re.escape(program)} counter: (\d+)$", log, re.MULTILINE)
    if counter is None:
        return f"no `{program} counter:` line"
    return check_run(int(counter.group(1)), lines, 0, beats)


def check_counters(log, lines, tasks):
    """The counter checks of a generated program: per accelerator task of the
    manifest, in order, `forge counter <task>: <n>` in log (the program's
    output) against run k of lines (the unit's runs, classes.unit_runs()).
    Returns None when they hold, else why not."""
    if not tasks:
        return "no accelerator task in the manifest"
    for k, task in enumerate(tasks):
        counter = re.search(rf"^forge counter {re.escape(task['name'])}: (\d+)$", log,
                            re.MULTILINE)
        if counter is None:
            return f"no `forge counter {task['name']}:` line"
        why = check_run(int(counter.group(1)), lines, k, task["beats"])
        if why is not None:
            return f"{task['name']}: {why}"
    return None


def check_traces(log, traces, counters):
    """A forge/ run's checks on its run.log (log) and its trace.log (traces):
    every line of trace.log parses (classes.parse), then counters(output,
    unit runs) and the class check hold. Returns (None, None) when they do,
    else (why not, the file it read)."""
    try:
        name = str(traces.relative_to(ROOT))
    except ValueError:  # not below the checkout
        name = str(traces)
    try:
        parsed = classes.parse(traces.read_text(errors="replace"), name)
    except classes.LineError as e:
        return str(e), traces
    why = counters(log.read_text(errors="replace"), classes.unit_runs(parsed))
    if why is not None:
        return why, log
    why = classes.check(parsed)
    return (None, None) if why is None else (why, traces)


def make(path, *args):
    p = subprocess.run(["make", "-s", "-C", str(path), *args], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(f"build failed: make -C {path} {' '.join(args)}\n{p.stdout}")


class Check:
    """Runs the programs whose name holds only (all when None) and collects
    the ones that did not exit 0."""

    def __init__(self, only=None):
        self.only = only
        self.count = 0
        self.failed = []

    def selected(self, name):
        return self.only is None or self.only in name

    def run(self, name, target, elf, work=None, options=()):
        """Runs one program; returns its log when it exited 0, else None."""
        if not self.selected(name):
            return None
        self.count += 1
        log = WORK / (work or name) / "run.log"
        code = gvrun(target, elf, log.parent, log, options)
        if code == 0:
            return log
        why = f"did not finish within {TIMEOUT} s" if code is None else f"exit {code}"
        self.fail(name, why, log)
        return None

    def run_fixture(self, name, design, app, elf, make_args, counters):
        """Builds app (make_args) and runs elf on FORGE_TARGET with forge/<design>/'s
        cluster file, the unit's UNIT_TRACES and CLASS_TRACES on, into trace.log beside
        the run's log; then check_traces() with counters(log, unit runs,
        manifest), its counter check."""
        if not self.selected(name):
            return
        manifest = json.loads((FORGE_DIR / design / "manifest.json").read_text())
        make(APPS / app, *make_args)
        traces = WORK / name / "trace.log"
        log = self.run(name, FORGE_TARGET, elf,
                       options=["--param", f"hjson={cluster_file(design)}",
                                *(f"--trace={t}:{traces}"
                                  for t in (*(f"{manifest['trace']}/{u}$" for u in UNIT_TRACES),
                                            *CLASS_TRACES))])
        if log is not None:
            # The traces in their own file: GVSoC buffers its stdout, so the
            # program's output there could cut a trace line in two
            why, where = check_traces(log, traces,
                                      lambda text, runs: counters(text, runs, manifest))
            if why is not None:
                self.fail(name, why, where)

    def run_script(self, name, script):
        """Runs a test script, its output into the log; it passes when it
        exits 0."""
        if not self.selected(name):
            return
        self.count += 1
        log = WORK / name / "run.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log, "w") as out:
                p = subprocess.run([str(script)], cwd=ROOT, stdout=out,
                                   stderr=subprocess.STDOUT, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            self.fail(name, f"did not finish within {TIMEOUT} s", log)
            return
        if p.returncode != 0:
            self.fail(name, f"exit {p.returncode}", log)

    def fail(self, name, why, log=None):
        self.failed.append(name)
        print(f"  FAIL {name}: {why}")
        if ACTIONS:
            where = f", log {log.relative_to(ROOT)}" if log is not None else ""
            print(f"::error title={name}::{why}{where}")
        if log is not None:
            print(f"  log {log.relative_to(ROOT)}, last {TAIL} lines:")
            for line in log.read_text(errors="replace").splitlines()[-TAIL:]:
                print(f"    {line}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("-k", metavar="SUBSTRING", dest="only",
                   help="run only the programs whose name holds SUBSTRING")
    check = Check(p.parse_args().only)

    print("SnaxUnit's rule (tests/snax/unit)")
    check.run_script("unit", HERE / "unit" / "run.sh")
    print(f"  {check.count} run")

    count = check.count
    print("SnaxShell's rule (tests/snax/shell)")
    check.run_script("shell", HERE / "shell" / "run.sh")
    print(f"  {check.count - count} run")

    make(SW)

    count = check.count
    print(f"cluster tests on {FORGE_TARGET}, forge/{CLUSTER_DESIGN}/'s cluster file")
    hjson = ["--param", f"hjson={cluster_file(CLUSTER_DESIGN)}"]
    programs = [(prog, [prog]) for prog in CLUSTER_TESTS]
    programs += [(prog, [f"{prog}-{case}" for case in cases]) for prog, cases in CASES]
    for prog, names in programs:
        if any(check.selected(f"{name}.{FORGE_TARGET}") for name in names):
            make(APPS / prog)
        for name in names:
            check.run(f"{name}.{FORGE_TARGET}", FORGE_TARGET,
                      BUILD / "apps" / prog / f"{name}.elf", options=hjson)
    print(f"  {check.count - count} run")

    count = check.count
    prog, name = "snax-shell", f"snax-shell.{FORGE_TARGET}"
    print(f"{prog} on {FORGE_TARGET}, forge/{SHELL_DESIGN}/'s cluster file")
    check.run_fixture(name, SHELL_DESIGN, prog, BUILD / "apps" / prog / f"{prog}.elf", [],
                      lambda log, runs, _: check_counter(prog, log, runs, SHELL_BEATS))
    print(f"  {check.count - count} run")

    count = check.count
    designs = sorted(d.name for d in FORGE_DIR.iterdir() if (d / "manifest.json").is_file())
    names = [f"{FORGE_APP}.{d}" for d in designs]
    names += [f"forge-reduce.{d}-r{r}" for d, r in FORGE_REDUCE]
    print(f"forge/'s accelerators: {', '.join(names)}")
    for design in designs:
        check.run_fixture(f"{FORGE_APP}.{design}", design, FORGE_APP,
                          BUILD / "apps" / FORGE_APP / design / f"{FORGE_APP}.elf",
                          [f"DESIGN={design}"],
                          lambda log, runs, manifest: check_counters(log, runs,
                                                                     manifest["tasks"]))
    for design, rate in FORGE_REDUCE:
        prog, variant = "forge-reduce", f"{design}-r{rate}"
        check.run_fixture(f"{prog}.{variant}", design, prog,
                          BUILD / "apps" / prog / variant / f"{prog}.elf",
                          [f"DESIGN={design}", f"RATE_OVERRIDE={rate}"],
                          lambda log, runs, manifest: check_counter(
                              "forge-reduce", log, runs, manifest["tasks"][0]["beats"]))
    print(f"  {check.count - count} run")

    print(f"plain tests on snitch ({PLAIN_DIR.relative_to(ROOT)})")
    count = check.count
    for test in PLAIN_TESTS:
        elf = PLAIN_DIR / f"{test}.elf"
        name = f"plain {test}"
        if not elf.is_file():
            if check.selected(name):
                check.fail(name, f"{elf.relative_to(ROOT)} missing")
            continue
        check.run(name, "snitch", elf, f"plain/{test}")
    print(f"  {check.count - count} run")

    if check.failed:
        print(f"regression FAILED: {len(check.failed)} program(s): {', '.join(check.failed)}")
        return 1
    print("regression passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
