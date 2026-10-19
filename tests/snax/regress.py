#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""SNAX-GVSoC's regression (SG5, pass/finish only since SG6): `make regress`.

First runs SnaxUnit's rule against its hand-worked cases
(tests/snax/unit/run.sh, g++ only; `unit`, passes when it exits 0). Then
builds sw/ (`make -C sw`: the runtime per cluster, the math library and
snax_cluster's plain tests, from the pinned copy, CI1) and the programs
of sw/apps/, then runs each SNAX program, the same ELF, on each SNAX target
(SNAX_TARGETS: `snax_alu`, plain interconnect, and `snax_alu_sparse`, SG7),
named <program>.<target>: `snax-alu` at DATA_LEN 4, 100, 128, 1024, 4096,
`snax-stream`, `alu-timing`, the seven `stream-timing` cases, `dma-timing`,
`snax-csr`, the three `core-tcdm` cases and the `dma-tcdm` case; then
`snax-shell` on `snax_tiled_add` (GEN3 step 2: SnaxShell and SnaxUnit), with
the unit's trace on and the counter check below; then
each generated accelerator of forge/ (FORGE) with its program,
`forge-elementwise` (GEN3 step 5) or `forge-reduce` (step 6b), named
<program>.<design> (forge-reduce.vsum-r16 runs vsum with its len overridden
to 16, four sums): the fixture's manifest.json gives its cluster file, the
unit's trace path and the one accelerator task's beats; it runs on
`snax_hjson` with `--param hjson=<cluster file>` (LNK2a: its components are
not the default file's, so gvrun warns and runs it on the JSON config), with
the counter check; then
the plain tests on the `snitch` target: one per sw/tests/*.c (the 17 of COPIED in sw/sync.py), each
from build/sw/tests/; a plain ELF missing is a failure.

A program passes when it exits 0 within TIMEOUT seconds: every SNAX program
returns its error count, but `stream-timing` and the `core-tcdm` cases other
than `subword`, which return 0. No other output or cycle count is compared; the comparison with the RTL is made by
hand with phases.py (README, "Comparing with the RTL").

The counter check (check_counter, GEN3): a program on SnaxShell and
SnaxUnit prints the shell's counter after its first unit run as
`<program> counter: <n>`; it passes when n is busy + stall_in + stall_out +
flush of the unit's first trace line (`run 0: ...`) and that run fired the
program's beats (snax-shell's in OWN_TARGET, a fixture's from its manifest;
a manifest with other than one accelerator task fails).

gvrun runs with PYTHONDONTWRITEBYTECODE=1, so no __pycache__ lands beside
the modules it imports. Each run's stdout and stderr go to build/regress/work/<name>/run.log; a
failure prints that path and the log's last lines. Under GitHub Actions
(GITHUB_ACTIONS=true) each failure also prints an `::error` line, an
annotation on the run naming the program, why and its log. `-k SUBSTRING`
runs only the programs whose name holds it.

Needs GVSoC built for `snitch;snax_alu;snax_alu_sparse;snax_tiled_add;snax_hjson`
(README). Exit code 0 when every program
passes, 1 otherwise.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SW = ROOT / "sw"
APPS = SW / "apps"
BUILD = ROOT / "build" / "sw"

SNAX_TARGETS = ["snax_alu", "snax_alu_sparse"]
# Programs on one target each, with the counter check: (program, target, the
# unit's trace path, the beats of its first run: snax-shell's RUN_BEATS,
# DATA_LEN 192 / 4 lanes / 3 runs)
OWN_TARGET = [("snax-shell", "snax_tiled_add", "snax_acc0/unit", 16)]
# Generated accelerators, forge/<design>/ (forge/README.md), each run on
# snax_hjson from its cluster file by its program: (design, program, forge-elementwise's datagen.py mode: 0 add, 2 mul;
# None for a program without one, forge-reduce's RATE_OVERRIDE or None)
FORGE_DIR = ROOT / "forge"
FORGE_TARGET = "snax_hjson"
FORGE = [("vecadd", "forge-elementwise", 0, None), ("vecmul", "forge-elementwise", 2, None),
         ("vsum", "forge-reduce", None, None),
         # The derived task list overridden by hand (len 16 for vsum's T = N
         # = 64): 4 sums per run, the multi-output path, until a kernel gives
         # T < N
         ("vsum", "forge-reduce", None, 16)]
SIZES = [4, 100, 128, 1024, 4096]
STREAM_CASES = ["zero_bound", "a_alone", "ab_other_banks", "ab_same_banks", "a_stride0",
                "prio_queued", "idle_restart"]
CORE_TCDM_CASES = ["subword", "core_vs_reader", "after_stores"]
DMA_TCDM_CASES = ["dma_vs_reader"]
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


RUN_LINE = re.compile(r"run 0: firings (\d+) busy (\d+) stall_in (\d+) stall_out (\d+) flush (\d+)")


def check_counter(program, output, trace, beats):
    """The counter check: the counter program prints (`<program> counter: <n>`
    in output) against the unit's first run line in trace. Returns None when
    it holds, else why not."""
    counter = re.search(rf"^{re.escape(program)} counter: (\d+)$", output, re.MULTILINE)
    if counter is None:
        return f"no `{program} counter:` line"
    run = RUN_LINE.search(trace)
    if run is None:
        return "no `run 0:` line in the unit's trace"
    firings, *classes = (int(n) for n in run.groups())
    if firings != beats:
        return f"run 0 fired {firings} times, not {beats}"
    if int(counter.group(1)) != sum(classes):
        return (f"counter {counter.group(1)}, busy + stall_in + stall_out + flush "
                f"{' + '.join(map(str, classes))} = {sum(classes)}")
    return None


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

    def selected_snax(self, program):
        """Whether the SNAX program runs on any target."""
        return any(self.selected(f"{program}.{target}") for target in SNAX_TARGETS)

    def run_snax(self, program, elf):
        """Runs the SNAX program's ELF on every SNAX target."""
        for target in SNAX_TARGETS:
            self.run(f"{program}.{target}", target, elf)

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

    make(SW)

    count = check.count
    print(f"SNAX programs on {', '.join(SNAX_TARGETS)}")
    for n in SIZES:
        if check.selected_snax(f"snax-alu-{n}"):
            make(APPS / "snax-alu", f"DATA_LEN={n}")
        check.run_snax(f"snax-alu-{n}", BUILD / "apps" / "snax-alu" / str(n) / "snax-alu.elf")
    for prog in ("snax-stream", "alu-timing", "dma-timing", "snax-csr"):
        if check.selected_snax(prog):
            make(APPS / prog)
        check.run_snax(prog, BUILD / "apps" / prog / f"{prog}.elf")
    if any(check.selected_snax(f"stream-timing-{case}") for case in STREAM_CASES):
        make(APPS / "stream-timing")
    for case in STREAM_CASES:
        check.run_snax(f"stream-timing-{case}",
                       BUILD / "apps" / "stream-timing" / f"stream-timing-{case}.elf")
    if any(check.selected_snax(f"core-tcdm-{case}") for case in CORE_TCDM_CASES):
        make(APPS / "core-tcdm")
    for case in CORE_TCDM_CASES:
        check.run_snax(f"core-tcdm-{case}",
                       BUILD / "apps" / "core-tcdm" / f"core-tcdm-{case}.elf")
    if any(check.selected_snax(f"dma-tcdm-{case}") for case in DMA_TCDM_CASES):
        make(APPS / "dma-tcdm")
    for case in DMA_TCDM_CASES:
        check.run_snax(f"dma-tcdm-{case}",
                       BUILD / "apps" / "dma-tcdm" / f"dma-tcdm-{case}.elf")
    print(f"  {check.count - count} run")

    count = check.count
    print(f"SNAX programs on their own target: {', '.join(entry[1] for entry in OWN_TARGET)}")
    for prog, target, unit, beats in OWN_TARGET:
        name = f"{prog}.{target}"
        if check.selected(name):
            make(APPS / prog)
        log = check.run(name, target, BUILD / "apps" / prog / f"{prog}.elf",
                        options=[f"--trace={unit}"])
        if log is not None:
            # Program output and trace share the log
            text = log.read_text(errors="replace")
            why = check_counter(prog, text, text, beats)
            if why is not None:
                check.fail(name, why, log)
    print(f"  {check.count - count} run")

    count = check.count
    def variant(design, rate):
        """The design's name in the run's name and the build folder."""
        return design if rate is None else f"{design}-r{rate}"

    print(f"forge/'s accelerators: "
          f"{', '.join(f'{prog}.{variant(design, rate)}' for design, prog, _, rate in FORGE)}")
    for design, prog, mode, rate in FORGE:
        name = f"{prog}.{variant(design, rate)}"
        if not check.selected(name):
            continue
        folder = FORGE_DIR / design
        # Plain json: the manifest is snax-forge's, read without it
        manifest = json.loads((folder / "manifest.json").read_text())
        tasks = manifest["tasks"]
        if len(tasks) != 1:
            check.count += 1
            check.fail(name, f"{len(tasks)} accelerator tasks in "
                       f"{(folder / 'manifest.json').relative_to(ROOT)}, not 1")
            continue
        make(APPS / prog, f"DESIGN={design}", *([f"MODE={mode}"] if mode is not None else []),
             *([f"RATE_OVERRIDE={rate}"] if rate is not None else []))
        cluster = (folder / manifest["cluster"]).resolve()
        log = check.run(name, FORGE_TARGET,
                        BUILD / "apps" / prog / variant(design, rate) / f"{prog}.elf",
                        options=["--param", f"hjson={cluster}", f"--trace={manifest['trace']}"])
        if log is not None:
            text = log.read_text(errors="replace")
            why = check_counter(prog, text, text, tasks[0]["beats"])
            if why is not None:
                check.fail(name, why, log)
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
