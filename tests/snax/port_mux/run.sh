#!/bin/bash
# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# SnaxPortMuxRule against its hand-worked cases (README.md), g++ only:
#   run.sh [OBJ_DIR]
# Builds tb.cpp, when stale (../build_tb.sh), with snax/snax_port_mux.hpp into
# OBJ_DIR (default build/port_mux), then runs it. Exit 1 on a difference.
set -e

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
obj=${1:-$root/build/port_mux}

mkdir -p "$obj"
"$here/../build_tb.sh" "$0" "$obj/tb" "$here/tb.cpp" -I"$root/snax"
"$obj/tb"
