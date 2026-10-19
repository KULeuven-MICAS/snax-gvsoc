#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Refreshes sw/ from a snax_cluster checkout: `make sync-snax-cluster
SNAX_CLUSTER=<path>` (CI1, sw/README.md).

1. Refuses a checkout with tracked changes in what sync reads (CHECKED);
   reads the old pin from sw/README.md.
2. Removes the copied files (COPIED, MATH) from sw/ and copies them again
   from the checkout, so a file deleted upstream disappears. Nothing else
   under sw/ is touched.
3. Regenerates the generated files with upstream's own rules: per cluster
   (CLUSTERS), snitch_cluster_cfg.h and snitch_cluster_addrmap.h into
   sw/generated/<cluster>/ and snitch_cluster_peripheral.h (the same for
   every cluster) into sw/runtime/common/, made in the checkout by
   `make -C target/snitch_cluster`; for the clusters of SAME_HEADERS, the
   same headers, only compared with another cluster's (a difference fails
   the sync); sw/math/include/bits/alltypes.h with the sed rule of
   snax_cluster's sw/math/Makefile.
4. Writes the new pin (snax_cluster HEAD, the printf and riscv-opcodes
   submodule commits) into sw/README.md.
5. Reports what changed in sw/, what changed upstream in the build files
   sw/'s Makefiles mirror (MIRRORED), and whether the checkout's
   streamer_csr_addr_map.h (written by the Chisel streamer in rtl-gen)
   equals sw/generated/'s hand copy, which sync never writes.

Paths: sw/X -> sw/X, target/snitch_cluster/sw/X -> sw/X,
target/snitch_cluster/cfg/X -> sw/cfg/X, util/sim/X -> sw/util/X,
LICENSE -> sw/LICENSE, docs/schema/X -> sw/docs/schema/X. Run it in snax-forge's image (clustergen, regtool,
clang-format, bender).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SW = Path(__file__).resolve().parent
REPO = SW.parent
README = SW / "README.md"

# The files a build reads (traced with clang -MD), by their path in snax_cluster.
TSW = "target/snitch_cluster/sw"
COPIED = [
    "LICENSE",
    "sw/snRuntime/base.ld",
    *(f"sw/snRuntime/api/{n}_decls.h" for n in ("alloc", "cls", "riscv", "start", "sync", "team")),
    "sw/snRuntime/api/omp/eu_decls.h",
    *(f"sw/snRuntime/src/{n}.{e}" for n in ("alloc", "cls", "cluster_interrupts", "dma", "sync", "team")
      for e in ("c", "h")),
    *(f"sw/snRuntime/src/{n}.h" for n in ("csr", "dump", "perf_cnt", "riscv")),
    "sw/snRuntime/src/printf.c",
    "sw/snRuntime/src/printf.h",
    "sw/snRuntime/src/start.c",
    "sw/snRuntime/src/start.S",
    "sw/snRuntime/src/omp/eu.c",
    "sw/snRuntime/src/omp/eu.h",
    "sw/deps/printf/printf.c",
    "sw/deps/printf/printf.h",
    "sw/deps/printf/LICENSE",
    "sw/deps/riscv-opcodes/encoding.h",
    "sw/deps/riscv-opcodes/LICENSE",
    # The 17 plain tests of target/snitch_cluster/sw/runtime.yaml and standard-fp.yaml
    *(f"sw/tests/{t}.c" for t in (
        "atomics", "barrier", "dma_simple", "fence_i", "interrupt_local", "multi_cluster",
        "perf_cnt", "printf_simple", "printf_fmtint", "simple", "tls", "varargs_1", "varargs_2",
        "fp16_comparison_scalar", "fp16_computation_scalar", "fp32_comparison_scalar",
        "fp32_computation_scalar")),
    f"{TSW}/toolchain.mk",
    f"{TSW}/runtime/common/snitch_cluster_defs.h",
    f"{TSW}/runtime/common/snitch_cluster_global_interrupts.h",
    f"{TSW}/runtime/common/snitch_cluster_memory.h",
    f"{TSW}/runtime/rtl-generic/memory.ld",
    *(f"{TSW}/runtime/rtl-generic/src/{n}" for n in (
        "putchar.c", "snitch_cluster_start.S", "snitch_cluster_start.c", "snrt.c", "snrt.h")),
    *(f"{TSW}/runtime/rtl/src/{n}" for n in (
        "putchar.c", "snitch_cluster_start.S", "snitch_cluster_start.c")),
    f"{TSW}/apps/snax-alu/src/snax-alu.c",
    f"{TSW}/apps/snax-alu/data/datagen.py",
    f"{TSW}/snax/snax-alu/src/snax-alu-lib.c",
    f"{TSW}/snax/snax-alu/include/snax-alu-lib.h",
    "target/snitch_cluster/cfg/snax_alu_cluster.hjson",
    "target/snitch_cluster/cfg/snax_alu_cluster_old.hjson",
    "target/snitch_cluster/cfg/snitch_cluster.hjson",
    # The cluster hjson's schema, clustergen's check of it (LNK2a round 2)
    "docs/schema/snitch_cluster.schema.json",
    "util/sim/data_utils.py",
]
# sw/math/ whole, but for these (paths relative to sw/math/)
MATH = "sw/math"
MATH_SKIP = ("Makefile", ".gitignore", "include/bits/")

CLUSTERS = ["snitch_cluster", "snax_alu_cluster_old"]
# Clusters whose headers must equal another's, so they share its generated/
# folder and runtime: made and compared, not kept. The checkout is left on
# the last one made.
SAME_HEADERS = {"snax_alu_cluster": "snax_alu_cluster_old"}
COMMON = f"{TSW}/runtime/common"
CLUSTER_GEN = ["snitch_cluster_cfg.h", "snitch_cluster_addrmap.h"]
PERIPHERAL = "snitch_cluster_peripheral.h"
ALLTYPES = SW / "math/include/bits/alltypes.h"
STREAMER_H = f"{TSW}/snax/snax-alu/include/streamer_csr_addr_map.h"
STREAMER_COPY = SW / "generated/snax_alu_cluster_old/streamer_csr_addr_map.h"

SUBMODULES = ["sw/deps/printf", "sw/deps/riscv-opcodes"]
# Upstream paths sync reads: a tracked change there is refused.
CHECKED = ["LICENSE", "sw/snRuntime", "sw/math", "sw/deps", "sw/tests", "target/common",
           "target/snitch_cluster", "util", "hw/snitch_cluster", "docs/schema"]
# Upstream build files that sw/Makefile, sw/common.mk and the app Makefiles mirror
MIRRORED = [
    f"{TSW}/Makefile", f"{TSW}/runtime/common/common.mk", f"{TSW}/runtime/rtl-generic/Makefile",
    "sw/math/Makefile", f"{TSW}/math/Makefile", f"{TSW}/tests/Makefile", f"{TSW}/runtime.yaml",
    f"{TSW}/standard-fp.yaml", f"{TSW}/apps/snax-alu/Makefile", f"{TSW}/snax/snax-alu/Makefile",
]

PIN_ROW = re.compile(r"^\| `(?P<what>[^`]+)` \| `(?P<commit>[0-9a-f]{40})` \|.*$", re.M)


def local(upstream):
    """Where an upstream path goes in sw/."""
    for prefix, to in ((f"{TSW}/", ""), ("target/snitch_cluster/cfg/", "cfg/"),
                       ("util/sim/", "util/"), ("sw/", "")):
        if upstream.startswith(prefix):
            return SW / (to + upstream[len(prefix):])
    return SW / upstream


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def math_upstream(checkout):
    files = git(checkout, "ls-files", "--", MATH).split()
    return [f for f in files if not f[len(MATH) + 1:].startswith(MATH_SKIP)]


def math_local():
    root = SW / "math"
    return [p for p in root.rglob("*") if p.is_file()
            and not p.relative_to(root).as_posix().startswith(MATH_SKIP)]


def read_pin():
    pins = {m["what"]: m["commit"] for m in PIN_ROW.finditer(README.read_text())}
    if "snax_cluster" not in pins:
        raise SystemExit(f"no snax_cluster pin row in {README.relative_to(REPO)}")
    return pins


def write_pin(checkout):
    text = README.read_text()
    for what, repo in [("snax_cluster", checkout)] + [(s, checkout / s) for s in SUBMODULES]:
        commit, date, subject = git(repo, "log", "-1", "--format=%H%n%cs%n%s").splitlines()
        row = f"| `{what}` | `{commit}` | {date}, {subject} |"
        text, n = re.subn(rf"^\| `{re.escape(what)}` \| `[0-9a-f]{{40}}` \|.*$", row, text,
                          flags=re.M)
        if n != 1:
            raise SystemExit(f"no pin row for {what} in {README.relative_to(REPO)}")
    README.write_text(text)


def copy(checkout):
    gone = []
    for p in [local(f) for f in COPIED] + math_local():
        p.unlink(missing_ok=True)
    for f in COPIED + math_upstream(checkout):
        src = checkout / f
        if not src.is_file():
            gone.append(f)
            continue
        dst = local(f)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # Folders left empty by a file gone upstream
    for d in sorted({local(f).parent for f in COPIED + math_upstream(checkout)}, reverse=True):
        while d != SW and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    return gone


def make_headers(checkout, cluster):
    """Makes the cluster's headers in the checkout; returns their text by name."""
    common = checkout / COMMON
    names = CLUSTER_GEN + [PERIPHERAL]
    for n in names:
        (common / n).unlink(missing_ok=True)
    targets = [f"sw/runtime/common/{n}" for n in names]
    p = subprocess.run(["make", "-C", str(checkout / "target/snitch_cluster"),
                        f"CFG_OVERRIDE=cfg/{cluster}.hjson", *targets],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise SystemExit(f"header generation failed for {cluster}:\n{p.stdout}")
    return {n: (common / n).read_text() for n in names}


def generate(checkout):
    common = checkout / COMMON
    peripheral = None
    made = {}
    for cluster in CLUSTERS:
        made[cluster] = make_headers(checkout, cluster)
        out = SW / "generated" / cluster
        out.mkdir(parents=True, exist_ok=True)
        for n in CLUSTER_GEN:
            shutil.copy2(common / n, out / n)
        text = (common / PERIPHERAL).read_text()
        if peripheral is not None and text != peripheral:
            raise SystemExit(f"{PERIPHERAL} differs between {CLUSTERS[0]} and {cluster}")
        peripheral = text
    for cluster, same in SAME_HEADERS.items():
        headers = make_headers(checkout, cluster)
        differ = [n for n in headers if headers[n] != made[same][n]]
        if differ:
            raise SystemExit(f"{cluster}: {', '.join(differ)} not equal to {same}'s")
    (SW / "runtime/common" / PERIPHERAL).write_text(peripheral)
    # sw/math/Makefile's rule for $(ALLTYPES_H)
    math = SW / "math"
    ALLTYPES.parent.mkdir(parents=True, exist_ok=True)
    with open(ALLTYPES, "w") as out:
        subprocess.run(["sed", "-f", str(math / "tools/mkalltypes.sed"),
                        str(math / "arch/riscv64/bits/alltypes.h.in"),
                        str(math / "include/alltypes.h.in")], check=True, stdout=out)


def streamer_lines(path):
    """The header without the line that holds the time rtl-gen made it."""
    return [x for x in path.read_text().splitlines() if not x.startswith("// Generated at")]


def report(checkout, old, new):
    print("\n== sw/ in snax-gvsoc (git diff --stat, then untracked files)")
    print(git(REPO, "diff", "--stat", "--", "sw").rstrip() or "  no change to tracked files")
    for f in git(REPO, "ls-files", "--others", "--exclude-standard", "--", "sw").split():
        print(f"  new: {f}")
    print(f"\n== upstream build files mirrored here, {old[:8]}..{new[:8]}")
    stat = git(checkout, "diff", "--stat", f"{old}..{new}", "--", *MIRRORED).rstrip()
    print(stat or "  no change")
    if stat:
        print("  Review sw/Makefile, sw/common.mk and sw/apps/*/Makefile against these.")
    print("\n== streamer_csr_addr_map.h")
    up = checkout / STREAMER_H
    ours = STREAMER_COPY.relative_to(REPO)
    if not up.is_file():
        print(f"  the checkout has none (made by rtl-gen); {ours} not compared")
    elif streamer_lines(up) == streamer_lines(STREAMER_COPY):
        print(f"  the checkout's (from its last rtl-gen) equals {ours}, but for the"
              " 'Generated at' line")
    else:
        print(f"  the checkout's (from its last rtl-gen, for the hjson it ran on) differs from"
              f" {ours}:\n  diff {up} {STREAMER_COPY}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("checkout", type=Path, help="the snax_cluster checkout")
    checkout = p.parse_args().checkout.resolve()

    dirty = git(checkout, "status", "--porcelain", "--untracked-files=no", "--", *CHECKED)
    if dirty:
        raise SystemExit(f"{checkout} has tracked changes in what sync reads:\n{dirty}")
    for s in SUBMODULES:
        if not (checkout / s / "LICENSE").is_file():
            raise SystemExit(f"{checkout / s} is not initialised (git submodule update --init)")
    old = read_pin()["snax_cluster"]
    new = git(checkout, "rev-parse", "HEAD").strip()

    gone = copy(checkout)
    generate(checkout)
    write_pin(checkout)

    print(f"sync from {checkout}: {old[:8]} -> {new[:8]}")
    for f in gone:
        print(f"  gone upstream, removed here: {f}")
    report(checkout, old, new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
