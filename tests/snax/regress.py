#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""SNAX-GVSoC's regression (SG5, pass/finish only since SG6): `make regress`.

Builds the SNAX programs of tests/snax/ and runs each on the `snax_alu`
target: `snax-alu` at DATA_LEN 4, 100, 128, 1024, 4096, `snax-stream`,
`alu-timing`, the five `stream-timing` cases, `dma-timing` and `snax-csr`.
The plain tests of snax_cluster run on the `snitch` target when their ELFs
are in build/regress/plain/ (`make regress-plain` builds them).

A program passes when it exits 0 within TIMEOUT seconds: every SNAX program
but `stream-timing` returns its error count, `stream-timing` returns 0. No
output or cycle count is compared; the comparison with the RTL is made by
hand with phases.py (README, "Comparing with the RTL").

Each run's stdout and stderr go to build/regress/work/<name>/run.log; a
failure prints that path and the log's last lines. `-k SUBSTRING` runs only
the programs whose name holds it.

Needs GVSoC built for `snitch;snax_alu` and snax_cluster's runtime built
for `cfg/snax_alu_cluster_old.hjson` (README). Exit code 0 when every
program passes, 1 otherwise.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SIZES = [4, 100, 128, 1024, 4096]
STREAM_CASES = ["zero_bound", "a_alone", "ab_other_banks", "ab_same_banks", "a_stride0"]
PLAIN_DIR = ROOT / "build" / "regress" / "plain"
PLAIN_COUNT = 17  # snax_cluster's sw/tests at the pinned commit
WORK = ROOT / "build" / "regress" / "work"
TIMEOUT = 300  # seconds per program; each takes a few
TAIL = 20  # lines of a failed run's log printed


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
        if log is not None:
            print(f"  log {log.relative_to(ROOT)}, last {TAIL} lines:")
            for line in log.read_text(errors="replace").splitlines()[-TAIL:]:
                print(f"    {line}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("-k", metavar="SUBSTRING", dest="only",
                   help="run only the programs whose name holds SUBSTRING")
    check = Check(p.parse_args().only)

    print("SNAX programs on snax_alu")
    for n in SIZES:
        if check.selected(f"snax-alu-{n}"):
            make(HERE / "snax-alu", f"DATA_LEN={n}")
        check.run(f"snax-alu-{n}", "snax_alu", HERE / "snax-alu" / "build" / str(n) / "snax-alu.elf")
    for prog in ("snax-stream", "alu-timing", "dma-timing", "snax-csr"):
        if check.selected(prog):
            make(HERE / prog)
        check.run(prog, "snax_alu", HERE / prog / "build" / f"{prog}.elf")
    if any(check.selected(f"stream-timing-{case}") for case in STREAM_CASES):
        make(HERE / "stream-timing")
    for case in STREAM_CASES:
        check.run(f"stream-timing-{case}", "snax_alu",
                  HERE / "stream-timing" / "build" / f"stream-timing-{case}.elf")
    print(f"  {check.count} run")

    elfs = sorted(PLAIN_DIR.glob("*.elf"))
    if not elfs:
        print(f"plain tests: none in {PLAIN_DIR.relative_to(ROOT)}, skipped (make regress-plain)")
    else:
        print(f"plain tests on snitch ({len(elfs)} in {PLAIN_DIR.relative_to(ROOT)})")
        if len(elfs) != PLAIN_COUNT and check.only is None:
            check.fail("plain", f"{len(elfs)} ELFs, expected {PLAIN_COUNT}")
        count = check.count
        for elf in elfs:
            check.run(f"plain {elf.stem}", "snitch", elf, f"plain/{elf.stem}")
        print(f"  {check.count - count} run")

    if check.failed:
        print(f"regression FAILED: {len(check.failed)} program(s): {', '.join(check.failed)}")
        return 1
    print("regression passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
