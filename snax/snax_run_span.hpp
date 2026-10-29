/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxRunSpan: when a run is busy, for the group (snax_group.hpp), the shell's
// view of its unit (snax_shell.hpp) and the streamer: started in cycle s, busy
// from s + 1 to its last cycle E, idle before its first start and after E.
// Plain C++ (no GVSoC include), as the rules that use it, so the standalone
// tests build it with g++ only.

#pragma once

#include <cstdint>


struct SnaxRunSpan
{
    bool started = false;       // a start was taken since reset
    int64_t start_cycle = 0;    // s
    int64_t end_cycle = -1;     // E, -1 until known

    void reset() { *this = SnaxRunSpan(); }

    void start(int64_t cycle)
    {
        this->started = true;
        this->start_cycle = cycle;
        this->end_cycle = -1;
    }

    void end(int64_t cycle) { this->end_cycle = cycle; }

    bool ended() const { return this->end_cycle != -1; }

    // Busy in cycle: from s + 1 to E
    bool busy(int64_t cycle) const
    {
        return this->started && cycle > this->start_cycle &&
            (this->end_cycle == -1 || cycle <= this->end_cycle);
    }

    // Idle in cycle: never started, or the run ended before it
    bool idle(int64_t cycle) const
    {
        return !this->started || (this->end_cycle != -1 && this->end_cycle < cycle);
    }
};
