#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# The datapath classes against NumPy's vectors (README.md), g++ only:
#   run.sh [OBJ_DIR]
# Builds tb.cpp, when stale (../build_tb.sh), with snax/snax_datapath.hpp into
# OBJ_DIR (default build/datapath), then runs it on vectors.txt. Exit 1 on a
# difference.
set -e

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
obj=${1:-$root/build/datapath}

mkdir -p "$obj"
"$here/../build_tb.sh" "$0" "$obj/tb" "$here/tb.cpp" -I"$root/snax"
"$obj/tb" "$here/vectors.txt"
