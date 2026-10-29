/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxUnit's cycle rule and op table: when a Chisel
// block's datapath takes a start, fires and pushes, how its busy cycles are
// classed, and what a lane and a beat compute. Plain C++, so the component
// (snax_unit.cpp) and the standalone test (tests/snax/unit/) run the same
// code, as snax_sparse_arb.hpp.
//
// The arithmetic is NumPy's on integer types (SnaxUnitType: 8 to 64 bits,
// signed or not), each port with its own (PACK0). A port of W lanes of b bits
// takes W * b / 64 channel words, lane l at bits [l * b, (l + 1) * b) of them
// side by side (the wire slice). An elementwise op runs per lane at T, the
// result type of its two inputs' types (snax_unit_result_type; none for a
// signed type with uint64), each operand extended to T by its own
// signedness; the result wraps at T and is cast to the output's type (its
// low bits, or extended by T's signedness). A fold casts each lane from the
// input's type to the output's, and runs its tree and acc at the output's
// type; its output beat is one word. min and max compare by the signedness
// of the type they run at.
//
// A run (snax-forge D146, D147: the nest controller of one unit): a start
// offered in cycle s carries jobs and job_beats; the run fires jobs * job_beats
// times and gives a result on every job_beats-th firing (jobs results;
// job_beats 1, every firing). It is taken only when the unit is idle in s and
// neither is 0 (jobs or job_beats 0 is the empty run, which the shell ends
// without the unit: here it is ignored, busy stays 0); a start while busy, or
// a second one in s, is refused. The unit is busy from s + 1 to the run's last
// cycle E. step() is called once per busy cycle, in order, with whether every
// input has a beat and whether the output has room (the component probes all
// ports first); it says whether the unit fires (takes a beat from every input)
// and pushes (gives a beat to the output) then.
//
// One rule, as a BRM's timing (L, II; D103) without its drain: a join on the
// inputs, an L-stage pipeline that stalls as a whole when its head cannot be
// pushed, at most one firing per II. A firing that gives a result (every
// job_beats-th) puts it into the pipeline; the others put nothing. A result
// from a firing in t is pushed in t + L when nothing stalls. II counts cycles
// from the last firing; a stall does not restart it, and it carries over to
// the next run. With L = 0 the result is pushed in its firing cycle, and a
// firing that gives a result with no room on the output is a stall: L = 0,
// II 1 is lockstep (snax-forge's ElementwiseLanes: it fires when every input
// has a beat and the output has room, and pushes in the same cycle). E is the
// push of the last result. A firing enters slot 0 in the cycle the head is
// pushed, so with L = 1 and II 1 the next input is taken in the cycle a result
// leaves: no drain cycle (snax-forge D133, TreeAccumulate).
//
// Each busy cycle is one class, in D59's order: stall_out (the head, or for
// L = 0 a firing that gives a result, has no room) > busy (fired, or in the
// II gap after a firing) > stall_in (II allows, an input has no beat) > flush
// (results in flight after the last firing's II gap, accel.py's idle).
// So busy + stall_in + stall_out + flush is the run's busy cycles, E - s.

#pragma once

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "snax_group.hpp"
#include "snax_types.hpp"
