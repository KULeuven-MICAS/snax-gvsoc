#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Builds a testbench with g++ when it is stale, for tests/snax/<name>/run.sh:
#   build_tb.sh RUN_SH BIN SRC [FLAGS...]
# BIN is rebuilt when it is missing, or older than SRC, a header SRC includes
# (BIN.d, g++'s list from the last build) or RUN_SH (the flags).
set -e

script=$1 bin=$2 src=$3
shift 3
dep=$bin.d
if [ -x "$bin" ] && [ -f "$dep" ]; then
    stale=
    for f in $(sed -e 's/^[^:]*://' -e 's/\\$//' "$dep") "$script"; do
        if [ ! -e "$f" ] || [ "$f" -nt "$bin" ]; then
            stale=1
            break
        fi
    done
    [ -z "$stale" ] && exit 0
fi
g++ -std=c++17 -O2 -Wall -Werror "$@" -MMD -MF "$dep" "$src" -o "$bin"
