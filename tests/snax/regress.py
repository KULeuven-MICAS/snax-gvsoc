#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""SNAX-GVSoC's regression (SG5): `make regress` from snax-gvsoc.

Builds the SNAX programs of tests/snax/, runs each on the `snax_alu` target
and compares its output exactly with the program's `expected/` folder:

- `snax-alu` at DATA_LEN 4, 100, 128, 1024, 4096: the printed lines, the
  exit code, the streamer's counter (977, from its trace) and the phase
  table (phases.py);
- `snax-stream`, `alu-timing`, the five `stream-timing` cases, `dma-timing`,
  `snax-csr` (with its two CSR-form warnings): the printed lines and the
  exit code.

For `snax-alu` it also checks SG5's error target against the RTL run in
`tests/snax/snax-alu/rtl/` (docs/plans/SG5.md, "The target"): tier 1 at
every size, tier 2 at 128, 1024 and 4096, but for the gaps in ACCEPTED.

The plain tests of snax_cluster run on the `snitch` target when their ELFs
are in build/regress/plain/ (`make regress-plain` builds them): each must
exit 0.

Needs GVSoC built for `snitch;snax_alu` and snax_cluster's runtime built
for `cfg/snax_alu_cluster_old.hjson` (README). `--update` rewrites the
`expected/` files from this run; `rtl/` is never written here. Exit code 0
when everything matches, 1 otherwise.
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
sys.path.insert(0, str(HERE))
import phases  # noqa: E402

SIZES = [4, 100, 128, 1024, 4096]
STREAM_CASES = ["zero_bound", "a_alone", "ab_other_banks", "ab_same_banks", "a_stride0"]
PLAIN_DIR = ROOT / "build" / "regress" / "plain"
PLAIN_COUNT = 17  # snax_cluster's sw/tests at the pinned commit
WORK = ROOT / "build" / "regress" / "work"

# Tier 2 (within 10% of the RTL) at these sizes, for these phases.
TIER2_SIZES = [128, 1024, 4096]
TIER2_ROWS = ["C1 barrier", "D2 DMA wait", "C3 ALU poll", "C5 check loop", "total_to_982"]
TIER2_LIMIT = 0.10
# Gaps outside tier 2 that SG5 explained and accepted: (size, row) -> reason.
ACCEPTED = {
    (128, "C1 barrier"): "the RTL core polls dmstati every 5 cycles, GVSoC every 2 (SG5 step 6)",
    (128, "D2 DMA wait"): "the RTL core polls dmstati every 5 cycles, GVSoC every 2 (SG5 step 6)",
}

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def gvrun(target, elf, workdir, traces=()):
    """Runs one ELF; returns its output (colour codes stripped) and exit code."""
    env = dict(os.environ)
    env["PATH"] = f"{ROOT / 'install' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{ROOT / 'install' / 'python'}:{env.get('PYTHONPATH', '')}"
    cmd = ["gvrun", "--target", target, "--work-dir", str(workdir),
           "--param", f"chip/soc/binary={elf}"]
    for t in traces:
        cmd.append(f"--trace={t}")
    cmd.append("run")
    p = subprocess.run(cmd, env=env, cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    return _ANSI.sub("", p.stdout), p.returncode


def make(path, *args):
    p = subprocess.run(["make", "-s", "-C", str(path), *args], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(f"build failed: make -C {path} {' '.join(args)}\n{p.stdout}")


class Check:
    """Compares a run's files with the expected ones, or writes them."""

    def __init__(self, update):
        self.update = update
        self.failed = []
        self.written = []

    def compare(self, name, path, actual):
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text() != actual:
                path.write_text(actual)
                self.written.append(path)
            return
        if not path.exists():
            self.fail(name, f"no expected file {path.relative_to(ROOT)} (run with --update)")
        elif path.read_text() != actual:
            self.fail(name, f"differs from {path.relative_to(ROOT)}")
            for a, b in zip(path.read_text().splitlines(), actual.splitlines()):
                if a != b:
                    print(f"    expected: {a}\n    got:      {b}")
                    break

    def fail(self, name, why):
        self.failed.append(name)
        print(f"  FAIL {name}: {why}")


def run_program(check, name, prog, elf):
    out, code = gvrun("snax_alu", elf, WORK / name)
    check.compare(name, HERE / prog / "expected" / f"{name}.out", f"{out}exit {code}\n")
    print(f"  {name}: exit {code}")


def run_snax_alu(check, n):
    prog = HERE / "snax-alu"
    make(prog, f"DATA_LEN={n}")
    elf = prog / "build" / str(n) / "snax-alu.elf"
    work = WORK / f"snax-alu-{n}"
    out, code = gvrun("snax_alu", elf, work,
                      ["pe0/insn:pe0.txt", "pe1/insn:pe1.txt", "streamer:streamer.txt"])
    done = [line for line in _ANSI.sub("", (work / "streamer.txt").read_text()).splitlines()
            if "Done:" in line]
    counter = done[-1].rsplit("counter", 1)[1].strip() if done else "none"
    traces = {h: phases.read_gvsoc(open(work / f"pe{h}.txt")) for h in (0, 1)}
    table = phases.phase_tables(str(elf), traces)
    name = f"snax-alu-{n}"
    check.compare(name, prog / "expected" / f"{n}.out", f"{out}exit {code}\n977 {counter}\n")
    check.compare(name, prog / "expected" / f"{n}.phases.json", json.dumps(table, indent=1) + "\n")
    print(f"  {name}: exit {code}, 977 {counter}, total up to 982 {table['total_to_982']}")
    return out, table


def against_rtl(check, runs):
    """SG5's target: tier 1 at every size, tier 2 at TIER2_SIZES."""
    rtl = HERE / "snax-alu" / "rtl"
    print("snax-alu against the RTL (tests/snax/snax-alu/rtl/)")
    for n, (out, table) in runs.items():
        rtl_out, rtl_json = rtl / f"{n}.out", rtl / f"{n}.json"
        if not rtl_out.exists() or not rtl_json.exists():
            check.fail(f"rtl-{n}", f"no {rtl_out.name} or {rtl_json.name} in {rtl.relative_to(ROOT)}")
            continue
        # The RTL's simulator may prefix printed lines with "# "
        want = [l.removeprefix("# ") for l in rtl_out.read_text().splitlines() if l.strip()]
        got = [l.strip() for l in out.splitlines() if l.strip()]
        for line in want:
            if line.strip() not in got:
                check.fail(f"rtl-{n}", f"tier 1: the RTL printed {line.strip()!r}, SNAX-GVSoC did not")
        rtl_table = json.loads(rtl_json.read_text())
        if n not in TIER2_SIZES:
            continue
        cells = []
        for row in TIER2_ROWS:
            g, r = _cycles(table, row), _cycles(rtl_table, row)
            dev = (g - r) / r
            ok = abs(dev) <= TIER2_LIMIT
            mark = "" if ok else (" accepted" if (n, row) in ACCEPTED else " FAIL")
            cells.append(f"{row} {dev:+.0%}{mark}")
            if not ok and (n, row) not in ACCEPTED:
                check.fail(f"rtl-{n}", f"tier 2: {row} {g} against {r} ({dev:+.0%})")
        print(f"  {n}: " + ", ".join(cells))


def _cycles(table, row):
    if row == "total_to_982":
        return table["total_to_982"]
    for hart in table["harts"].values():
        for r in hart:
            if r["phase"] == row:
                return r["cycles"]
    raise KeyError(row)


def run_plain(check):
    elfs = sorted(PLAIN_DIR.glob("*.elf"))
    if not elfs:
        print(f"plain tests: none in {PLAIN_DIR.relative_to(ROOT)}, skipped (make regress-plain)")
        return
    print(f"plain tests on snitch ({len(elfs)} in {PLAIN_DIR.relative_to(ROOT)})")
    if len(elfs) != PLAIN_COUNT:
        check.fail("plain", f"{len(elfs)} ELFs, expected {PLAIN_COUNT}")
    for elf in elfs:
        _, code = gvrun("snitch", elf, WORK / "plain" / elf.stem)
        if code != 0:
            check.fail(f"plain {elf.stem}", f"exit {code}")
    print(f"  {len(elfs)} run")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--update", action="store_true",
                   help="rewrite the expected/ files from this run (add a notes entry)")
    args = p.parse_args(argv)
    check = Check(args.update)

    print("snax-alu")
    runs = {n: run_snax_alu(check, n) for n in SIZES}
    print("other programs")
    for prog in ("snax-stream", "alu-timing", "dma-timing", "snax-csr"):
        make(HERE / prog)
        run_program(check, prog, prog, HERE / prog / "build" / f"{prog}.elf")
    make(HERE / "stream-timing")
    for case in STREAM_CASES:
        run_program(check, f"stream-timing-{case}", "stream-timing",
                    HERE / "stream-timing" / "build" / f"stream-timing-{case}.elf")
    if not args.update:
        against_rtl(check, runs)
    run_plain(check)

    if args.update:
        for path in check.written:
            print(f"written {path.relative_to(ROOT)}")
        print(f"{len(check.written)} expected files written; add a notes entry saying why")
        return 1 if check.failed else 0
    if check.failed:
        print(f"regression FAILED: {len(check.failed)} check(s)")
        return 1
    print("regression passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
