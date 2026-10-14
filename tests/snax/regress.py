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

Needs GVSoC built for `snitch;snax_alu` and snax_cluster's runtime built
for `cfg/snax_alu_cluster_old.hjson` (README). Exit code 0 when every
program passes, 1 otherwise.
"""

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


def gvrun(target, elf, workdir):
    """Runs one ELF; returns its exit code, or None when it does not finish."""
    env = dict(os.environ)
    env["PATH"] = f"{ROOT / 'install' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{ROOT / 'install' / 'python'}:{env.get('PYTHONPATH', '')}"
    cmd = ["gvrun", "--target", target, "--work-dir", str(workdir),
           "--param", f"chip/soc/binary={elf}", "run"]
    try:
        p = subprocess.run(cmd, env=env, cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    return p.returncode


def make(path, *args):
    p = subprocess.run(["make", "-s", "-C", str(path), *args], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(f"build failed: make -C {path} {' '.join(args)}\n{p.stdout}")


class Check:
    """Collects the programs that did not exit 0."""

    def __init__(self):
        self.failed = []

    def run(self, name, target, elf, work=None):
        code = gvrun(target, elf, WORK / (work or name))
        if code == 0:
            return
        why = f"did not finish within {TIMEOUT} s" if code is None else f"exit {code}"
        self.fail(name, why)

    def fail(self, name, why):
        self.failed.append(name)
        print(f"  FAIL {name}: {why}")


def main():
    check = Check()

    print("SNAX programs on snax_alu")
    for n in SIZES:
        make(HERE / "snax-alu", f"DATA_LEN={n}")
        check.run(f"snax-alu-{n}", "snax_alu", HERE / "snax-alu" / "build" / str(n) / "snax-alu.elf")
    for prog in ("snax-stream", "alu-timing", "dma-timing", "snax-csr"):
        make(HERE / prog)
        check.run(prog, "snax_alu", HERE / prog / "build" / f"{prog}.elf")
    make(HERE / "stream-timing")
    for case in STREAM_CASES:
        check.run(f"stream-timing-{case}", "snax_alu",
                  HERE / "stream-timing" / "build" / f"stream-timing-{case}.elf")
    print(f"  {len(SIZES) + 4 + len(STREAM_CASES)} run")

    elfs = sorted(PLAIN_DIR.glob("*.elf"))
    if not elfs:
        print(f"plain tests: none in {PLAIN_DIR.relative_to(ROOT)}, skipped (make regress-plain)")
    else:
        print(f"plain tests on snitch ({len(elfs)} in {PLAIN_DIR.relative_to(ROOT)})")
        if len(elfs) != PLAIN_COUNT:
            check.fail("plain", f"{len(elfs)} ELFs, expected {PLAIN_COUNT}")
        for elf in elfs:
            check.run(f"plain {elf.stem}", "snitch", elf, f"plain/{elf.stem}")
        print(f"  {len(elfs)} run")

    if check.failed:
        print(f"regression FAILED: {len(check.failed)} program(s): {', '.join(check.failed)}")
        return 1
    print("regression passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
