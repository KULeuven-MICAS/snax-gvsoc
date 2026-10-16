#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# The plain winner check (README.md), in snax_cluster's image (Verilator):
#   run.sh COMMON_CELLS NUM_IN OBJ_DIR [CYCLES [SEED]]
# Builds the testbench into OBJ_DIR, then runs it. MODEL_DIR, if set, is a
# folder whose snax_plain_arb.hpp replaces snax/'s (a broken copy, README).
set -e

here=$(cd "$(dirname "$0")" && pwd)
model=${MODEL_DIR:-$(cd "$here/../../../snax" && pwd)}
cc=$(realpath "$1")
num_in=$2
obj=$3
cycles=${4:-20000}
seed=${5:-1}

mkdir -p "$obj"
obj=$(realpath "$obj")
verilator --cc --exe --build -j 0 -Wno-fatal -Wno-lint -Wno-style --assert \
    --top-module plain_arb_top -GNumIn=$num_in -Mdir "$obj" -o tb \
    +incdir+"$cc/include" "$cc/src/cf_math_pkg.sv" "$cc/src/lzc.sv" "$cc/src/rr_arb_tree.sv" "$here/plain_arb_top.sv" \
    -CFLAGS "-O2 -DNUM_IN=$num_in -I$model" "$here/tb.cpp" > "$obj/build.log" 2>&1 \
    || { tail -20 "$obj/build.log"; exit 1; }
"$obj/tb" "$cycles" "$seed"
