#!/usr/bin/env python3
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Writes ports.h for tb.cpp from an elaborated SparseInterconnect.sv: its
input and bank counts, and accessors for the per-port signals, which
Verilator names one by one (io_tcdmReqs_<i>_valid, io_memReqs_<b>_ready, ...).

    python3 ports.py SparseInterconnect.sv > ports.h
"""

import re
import sys


def main():
    text = open(sys.argv[1]).read()
    start = text.index("module SparseInterconnect(")
    header = text[start:text.index(");", start)]
    nb_inp = len(set(re.findall(r"io_tcdmReqs_(\d+)_valid", header)))
    nb_out = len(set(re.findall(r"io_memReqs_(\d+)_valid", header)))

    out = [f"// Made by ports.py from {sys.argv[1]}", "#pragma once",
           f"#define NUM_INP {nb_inp}", f"#define NUM_OUT {nb_out}", ""]

    out.append("static inline void drive_req(VSparseInterconnect *t, int i, bool valid,"
               " uint32_t addr, bool priority) {\n  switch (i) {")
    for i in range(nb_inp):
        p = f"t->io_tcdmReqs_{i}_"
        out.append(f"  case {i}: {p}valid = valid; {p}bits_addr = addr; {p}bits_priority = priority;"
                   f" {p}bits_write = 0; {p}bits_amo = 0; {p}bits_data = 0; {p}bits_strb = 0xff;"
                   f" t->io_tcdmRsps_{i}_ready = 1; break;")
    out.append("  }\n}\n")

    out.append("static inline bool req_ready(VSparseInterconnect *t, int i) {\n  switch (i) {")
    for i in range(nb_inp):
        out.append(f"  case {i}: return t->io_tcdmReqs_{i}_ready;")
    out.append("  }\n  return false;\n}\n")

    out.append("static inline void drive_bank(VSparseInterconnect *t, int b, bool ready) {\n"
               "  switch (b) {")
    for b in range(nb_out):
        out.append(f"  case {b}: t->io_memReqs_{b}_ready = ready; t->io_memRsps_{b}_valid = 1;"
                   f" t->io_memRsps_{b}_bits_data = 0; break;")
    out.append("  }\n}\n")

    out.append("static inline bool bank_valid(VSparseInterconnect *t, int b) {\n  switch (b) {")
    for b in range(nb_out):
        out.append(f"  case {b}: return t->io_memReqs_{b}_valid;")
    out.append("  }\n  return false;\n}\n")

    out.append("static inline uint32_t bank_addr(VSparseInterconnect *t, int b) {\n  switch (b) {")
    for b in range(nb_out):
        out.append(f"  case {b}: return t->io_memReqs_{b}_bits_addr;")
    out.append("  }\n  return 0;\n}")

    print("\n".join(out))


if __name__ == "__main__":
    main()
