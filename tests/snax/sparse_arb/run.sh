#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# The winner check (README.md), in snax_cluster's image (Verilator):
#   run.sh MODULE_SV MODULE_CONFIG [MODEL_CONFIG [CYCLES [SEED]]]
# Builds the testbench beside the module (<module dir>/check/), then runs it.
set -e

here=$(cd "$(dirname "$0")" && pwd)
snax=$(cd "$here/../../../snax" && pwd)
sv=$(realpath "$1")
module_cfg=$2
model_cfg=${3:-$2}
cycles=${4:-20000}
seed=${5:-1}
obj=$(dirname "$sv")/check

mkdir -p "$obj"
python3 "$here/ports.py" "$sv" > "$obj/ports.h"
verilator --cc --exe --build -j 0 -Wno-fatal -Wno-lint -Wno-style \
    --top-module SparseInterconnect -Mdir "$obj" -o tb \
    -CFLAGS "-O2 -I$obj -I$snax" "$sv" "$here/tb.cpp" > "$obj/build.log" 2>&1 \
    || { tail -20 "$obj/build.log"; exit 1; }
"$obj/tb" "$module_cfg" "$model_cfg" "$cycles" "$seed"
