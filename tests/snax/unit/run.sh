#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# SnaxUnit's rule against the hand-worked cases (README.md), g++ only:
#   run.sh [OBJ_DIR]
# Builds tb.cpp with snax/snax_unit.hpp into OBJ_DIR (default
# build/unit), then runs it on every case in cases/. Exit 1 on a difference.
set -e

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
obj=${1:-$root/build/unit}

mkdir -p "$obj"
g++ -std=c++17 -O2 -Wall -Werror -I"$root/snax" "$here/tb.cpp" -o "$obj/tb"
"$obj/tb" "$here"/cases/*.txt
