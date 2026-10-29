/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell's rule: the CSRs of one group of an accelerator (snax-forge
// C§17, D146), GeMMX's shell contract as snax_cluster gives it (05615e4): the
// ReqRspManager (hw/chisel/.../reqRspManager/ReqRspManager.scala) holding the
// read-write CSRs, BlockGemm's ctrl handshake, busy and performance counter
// (hw/chisel_acc/.../gemm/BlockGemm.scala), with the group's START, JOBS,
// STATUS and COUNTER. Plain C++, so the component (snax_shell.cpp) and the
// standalone test (tests/snax/shell/) run the same code, as snax_group.hpp.
//
// CSRs, offsets from the group's first CSR (the CSR mux removes it): START,
// JOBS, then the units' read-write CSRs (JOB_BEATS for each fold without a
// fixed T, in unit order), read back as written; then STATUS and COUNTER,
// read-only.
//
// Rules, c being the cycle of an access:
//   - a write to a read-write CSR other than START, or to START with bit 0
//     clear, is taken at once;
//   - a start (START written with bit 0 set) is accepted in c when the unit
//     is idle in c (BlockGemm: ctrl.ready is idle), and the write answered at
//     once. While the unit is busy in c the write is held (IO_REQ_PENDING:
//     the ReqRspManager's req.ready is ctrl.ready), and accepted, then
//     answered, in the cycle busy falls: E + 1, E the run's last cycle;
//   - an accepted start a goes to the group's ctrl as JOBS and every
//     JOB_BEATS in unit order, as they stand (JOBS and 1 for a group without
//     one: a start is two words at least), unless one of them is 0: the empty run,
//     which the shell ends in its own cycle (E = a) without the group, so busy
//     never rises;
//   - STATUS: bit 0 busy, the unit's busy in c (from a + 1 to E); bit 1 done,
//     sticky: set by the done pulse in E, so it reads 1 from E + 1, and
//     cleared by an accepted start, so it reads 0 from a + 1; a set wins over
//     a clear in the same cycle (an empty run: STATUS reads 2 from a + 1);
//     bit 2 and up 0;
//   - COUNTER is reset by an accepted start and counts each busy cycle, then
//     holds after the run (BlockGemm's performance_counter): at c it is the
//     busy cycles after the accepted start and before c; 0 after an empty run.
// Busy and the counter are computed when read, from the cycles the unit's
// busy wire rose (busy from the next cycle) and fell (idle from the next).
// The unit sets the wire synchronously in the ctrl write that starts it, so a
// start sent in c sees its rise in c; it clears it in E.

#pragma once

#include <algorithm>
#include <cstdint>
#include <vector>

#include "snax_run_span.hpp"


class SnaxShellRule
{
public:
    // The fixed read-write CSRs: START, then JOBS
    static const int START = 0;
    static const int JOBS = 1;

    // What a write to a read-write CSR does in its cycle
    struct Write
    {
        bool held;      // a start while the unit is busy: answered when release() takes it
        bool start;     // a start accepted now
        bool empty;     // ... the empty run: nothing goes to the unit
    };

    // Read-write CSRs, as written: START, JOBS, the units'
    std::vector<uint32_t> regs;
    // The unit's busy wire: the cycles it last rose (its start) and fell (E)
    SnaxRunSpan unit_run;
    // The last accepted start and the last done pulse (-1 if none), and the
    // ones before them, which STATUS still shows in the cycle of a newer one
    int64_t accept_cycle;
    int64_t done_cycle;
    int64_t accept_before;
    int64_t done_before;
    // A start held while busy, and the value it writes to START
    bool held;
    uint32_t held_value;

    // nb_rw read-write CSRs (START, JOBS and the units'), the JOB_BEATS ones
    // at job_beats (indices into them, in unit order; none for a group without)
    void configure(int nb_rw, const std::vector<int> &job_beats)
    {
        this->job_beats_index = job_beats;
        this->regs.assign(nb_rw, 0);
        this->reset();
    }

    void reset()
    {
        std::fill(this->regs.begin(), this->regs.end(), 0);
        this->unit_run.reset();
        this->accept_cycle = this->done_cycle = -1;
        this->accept_before = this->done_before = -1;
        this->held = false;
        this->held_value = 0;
    }

    int nb_rw() const
    {
        return this->regs.size();
    }

    // What an accepted start sends the unit
    uint32_t jobs() const
    {
        return this->regs[JOBS];
    }

    // The words an accepted start sends: JOBS, then every JOB_BEATS in unit
    // order (JOBS and 1 without one)
    std::vector<uint32_t> words() const
    {
        std::vector<uint32_t> w = {this->jobs()};
        for (int i : this->job_beats_index)
        {
            w.push_back(this->regs[i]);
        }
        if (this->job_beats_index.empty())
        {
            w.push_back(1);
        }
        return w;
    }

    bool empty() const
    {
        for (uint32_t w : this->words())
        {
            if (w == 0)
            {
                return true;
            }
        }
        return false;
    }

    // A write of value to read-write CSR index in cycle
    Write write(int64_t cycle, int index, uint32_t value)
    {
        if (index != START || !(value & 1))
        {
            this->regs[index] = value;
            return {false, false, false};
        }
        if (this->unit_idle(cycle))
        {
            this->regs[START] = value;
            return {false, true, this->accept(cycle)};
        }
        this->held = true;
        this->held_value = value;
        return {true, false, false};
    }

    // A read in cycle of CSR index: a read-write one as written, then STATUS and COUNTER
    uint32_t read(int64_t cycle, int index) const
    {
        if (index < this->nb_rw())
        {
            return this->regs[index];
        }
        return index == this->nb_rw() ? this->status_at(cycle) : this->counter_at(cycle);
    }

    // The unit's busy wire set to busy in cycle; its fall is the done pulse
    void busy(int64_t cycle, bool busy)
    {
        if (busy)
        {
            this->unit_run.start(cycle);
        }
        else
        {
            this->unit_run.end(cycle);
            this->done(cycle);
        }
    }

    // The cycle a held start is taken, E + 1, once the run has ended; -1
    // while none is held or the unit is still busy
    int64_t release_cycle() const
    {
        return this->held && this->unit_run.ended() ? this->unit_run.end_cycle + 1 : -1;
    }

    // The held start taken in cycle: written and accepted, its write answered.
    // Whether it is the empty run (nothing goes to the unit)
    bool release(int64_t cycle)
    {
        this->held = false;
        this->regs[START] = this->held_value;
        return this->accept(cycle);
    }

    // Idle in cycle: never started, or the last run ended before it
    bool unit_idle(int64_t cycle) const { return this->unit_run.idle(cycle); }

    bool busy_at(int64_t cycle) const { return this->unit_run.busy(cycle); }

    // Done in cycle, a register: the last done pulse before cycle, not
    // cleared by a start accepted after it and before cycle (a start in the
    // pulse's own cycle loses: the set wins)
    bool done_at(int64_t cycle) const
    {
        int64_t done = this->done_cycle < cycle ? this->done_cycle : this->done_before;
        int64_t accept = this->accept_cycle < cycle ? this->accept_cycle : this->accept_before;
        return done != -1 && !(accept > done);
    }

    uint32_t status_at(int64_t cycle) const
    {
        return (uint32_t)this->busy_at(cycle) | (uint32_t)this->done_at(cycle) << 1;
    }

    // The busy cycles in [accept + 1, cycle - 1]
    uint32_t counter_at(int64_t cycle) const
    {
        if (this->accept_cycle == -1 || !this->unit_run.started)
        {
            return 0;
        }
        int64_t first = std::max(this->accept_cycle, this->unit_run.start_cycle) + 1;
        int64_t last = cycle - 1;
        if (this->unit_run.ended() && this->unit_run.end_cycle < last)
        {
            last = this->unit_run.end_cycle;
        }
        return last >= first ? last - first + 1 : 0;
    }

private:
    // An accepted start in cycle; the empty run ends here (E = a): true
    bool accept(int64_t cycle)
    {
        if (this->accept_cycle < cycle)
        {
            this->accept_before = this->accept_cycle;
        }
        this->accept_cycle = cycle;
        if (this->empty())
        {
            this->done(cycle);
            return true;
        }
        return false;
    }

    // The done pulse in cycle
    void done(int64_t cycle)
    {
        if (this->done_cycle < cycle)
        {
            this->done_before = this->done_cycle;
        }
        this->done_cycle = cycle;
    }

    std::vector<int> job_beats_index;
};
