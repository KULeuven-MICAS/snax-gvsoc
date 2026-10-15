#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""SNAX-GVSoC's regression (SG5, pass/finish only since SG6): `make regress`.

Builds sw/ (`make -C sw`: the runtime per cluster, the math library and
snax_cluster's plain tests, from the pinned copy, CI1) and the programs
of sw/apps/, then runs each SNAX program, the same ELF, on each SNAX target
(SNAX_TARGETS: `snax_alu`, plain interconnect, and `snax_alu_sparse`, SG7),
named <program>.<target>: `snax-alu` at DATA_LEN 4, 100, 128, 1024, 4096,
`snax-stream`, `alu-timing`, the seven `stream-timing` cases, `dma-timing`
and `snax-csr`; then the plain tests on the `snitch` target: one per
sw/tests/*.c (the 17 of COPIED in sw/sync.py), each from build/sw/tests/; a
plain ELF missing is a failure.

A program passes when it exits 0 within TIMEOUT seconds: every SNAX program
but `stream-timing` returns its error count, `stream-timing` returns 0. No
output or cycle count is compared; the comparison with the RTL is made by
hand with phases.py (README, "Comparing with the RTL").

Each run's stdout and stderr go to build/regress/work/<name>/run.log; a
failure prints that path and the log's last lines. Under GitHub Actions
(GITHUB_ACTIONS=true) each failure also prints an `::error` line, an
annotation on the run naming the program, why and its log. `-k SUBSTRING`
runs only the programs whose name holds it.

Needs GVSoC built for `snitch;snax_alu;snax_alu_sparse` (README). Exit code 0 when every
program passes, 1 otherwise.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SW = ROOT / "sw"
APPS = SW / "apps"
BUILD = ROOT / "build" / "sw"

SNAX_TARGETS = ["snax_alu", "snax_alu_sparse"]
SIZES = [4, 100, 128, 1024, 4096]
STREAM_CASES = ["zero_bound", "a_alone", "ab_other_banks", "ab_same_banks", "a_stride0",
                "prio_queued", "idle_restart"]
PLAIN_DIR = BUILD / "tests"
PLAIN_TESTS = sorted(c.stem for c in (SW / "tests").glob("*.c"))  # COPIED in sw/sync.py
WORK = ROOT / "build" / "regress" / "work"
TIMEOUT = 300  # seconds per program; each takes a few
TAIL = 20  # lines of a failed run's log printed
ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def gvrun(target, elf, workdir, log):
    """Runs one ELF, its output into log; returns its exit code, or None when
    it does not finish."""
    env = dict(os.environ)
    env["PATH"] = f"{ROOT / 'install' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{ROOT / 'install' / 'python'}:{env.get('PYTHONPATH', '')}"
    cmd = ["gvrun", "--target", target, "--work-dir", str(workdir),
           "--param", f"chip/soc/binary={elf}", "run"]
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "w") as out:
            p = subprocess.run(cmd, env=env, cwd=ROOT, stdout=out,
                               stderr=subprocess.STDOUT, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    return p.returncode


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

    def run(self, name, target, elf, work=None):
        if not self.selected(name):
            return
        self.count += 1
        log = WORK / (work or name) / "run.log"
        code = gvrun(target, elf, log.parent, log)
        if code == 0:
            return
        why = f"did not finish within {TIMEOUT} s" if code is None else f"exit {code}"
        self.fail(name, why, log)

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

    make(SW)

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
    print(f"  {check.count} run")

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
