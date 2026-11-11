#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# The crossbar's pick at up to 128 inputs (README.md), g++ only:
#   run.sh [OBJ_DIR]
# Builds tb.cpp, when stale (../build_tb.sh), with snax/snax_sparse_arb.hpp into
# OBJ_DIR (default build/sparse_pick), then runs it. Exit 1 on a difference.
set -e

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
obj=${1:-$root/build/sparse_pick}

mkdir -p "$obj"
"$here/../build_tb.sh" "$0" "$obj/tb" "$here/tb.cpp" -I"$root/snax"
"$obj/tb"
