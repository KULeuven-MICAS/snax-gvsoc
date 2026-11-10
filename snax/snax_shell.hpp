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
// STATUS and BUSY_COUNTER. Plain C++, so the component (snax_shell.cpp) and
// the standalone test (tests/snax/shell/) run the same code, as
// snax_group.hpp.
//
// CSRs, offsets from the group's first CSR (the CSR mux removes it): START,
// JOBS, then the units' read-write CSRs (JOB_BEATS for each fold without a
// fixed T, then its scalars', K1, or K1_LO and K1_HI at 64 bits, in unit
// order), each kept at its width (accelerator.json's, D152:
// a write keeps the low bits, a read gives them with the upper bits 0);
// then STATUS and BUSY_COUNTER, read-only. START is a strobe: no register,
// it reads 0.
//
// Rules, c being the cycle of an access:
//   - while the unit is idle in c, a write to a read-write CSR other than
//     START is taken at once; one to START with bit 0 clear too, and does
//     nothing; a start (START written with bit 0 set) is accepted in c
//     (BlockGemm: ctrl.ready is idle), and the write answered at once;
//   - while the unit is busy in c, a write to any read-write CSR (START with
//     bit 0 set or clear, JOBS, a JOB_BEATS, a scalar) is held (IO_REQ_PENDING:
//     the csr's req.ready is low while busy), then taken as above and
//     answered in the cycle busy falls: E + 1, E the run's last cycle. So a
//     group's settings stay constant through its run, and the RTL's control
//     unit reads them live with no copy (snax-forge D168). Reads are never
//     held;
//   - an accepted start a goes to the group's ctrl as JOBS and every
//     JOB_BEATS in unit order, as they stand (JOBS and 1 for a group without
//     one: a start is two words at least), then every scalar CSR in CSR order
//     (any value, 0 too), unless JOBS or a JOB_BEATS is 0: the empty run,
//     which the shell ends in its own cycle (E = a) without the group, so busy
//     never rises;
//   - STATUS: bit 0 busy, the unit's busy in c (from a + 1 to E); bit 1 done,
//     sticky: set by the done pulse in E, so it reads 1 from E + 1, and
//     cleared by an accepted start, so it reads 0 from a + 1; a set wins over
//     a clear in the same cycle (an empty run: STATUS reads 2 from a + 1);
//     bit 2 and up 0;
//   - BUSY_COUNTER is reset by an accepted start and counts each busy cycle,
//     then holds after the run (BlockGemm's performance_counter): at c it is
//     the busy cycles after the accepted start and before c; 0 after an
//     empty run. At its width w it saturates at 2^w - 1. In the RTL it lives
//     in the csr's submodule <tag>_peripherals (D168).
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
        bool held;      // a write while the unit is busy: answered when release() takes it
        bool start;     // a start accepted now
        bool empty;     // ... the empty run: nothing goes to the unit
    };

    // Read-write CSRs, as kept: START (always 0), JOBS, the units'
    std::vector<uint32_t> regs;
    // The unit's busy wire: the cycles it last rose (its start) and fell (E)
    SnaxRunSpan unit_run;
    // The last accepted start and the last done pulse (-1 if none), and the
    // ones before them, which STATUS still shows in the cycle of a newer one
    int64_t accept_cycle;
    int64_t done_cycle;
    int64_t accept_before;
    int64_t done_before;
    // A write held while busy: its CSR and value
    bool held;
    int held_index;
    uint32_t held_value;

    // nb_rw read-write CSRs (START, JOBS and the units'), the JOB_BEATS ones
    // at job_beats (indices into them, in unit order; none for a group
    // without), the scalars' at scalars (in CSR order); widths, each one's
    // bits (none: all 32), and BUSY_COUNTER's
    void configure(int nb_rw, const std::vector<int> &job_beats,
        const std::vector<int> &widths = {}, int busy_counter_width = 32,
        const std::vector<int> &scalars = {})
    {
        this->job_beats_index = job_beats;
        this->scalar_index = scalars;
        this->regs.assign(nb_rw, 0);
        this->masks.assign(nb_rw, mask(32));
        for (size_t i = 0; i < widths.size() && i < this->masks.size(); i++)
        {
            this->masks[i] = mask(widths[i]);
        }
        this->busy_counter_max = mask(busy_counter_width);
        this->reset();
    }

    // The values of w bits, 1 to 32
    static uint32_t mask(int w)
    {
        return w >= 32 ? 0xffffffffu : (1u << w) - 1;
    }

    void reset()
    {
        std::fill(this->regs.begin(), this->regs.end(), 0);
        this->unit_run.reset();
        this->accept_cycle = this->done_cycle = -1;
        this->accept_before = this->done_before = -1;
        this->held = false;
        this->held_index = START;
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
    // order (JOBS and 1 without one), then every scalar CSR in CSR order
    std::vector<uint32_t> words() const
    {
        std::vector<uint32_t> w = this->config();
        for (int i : this->scalar_index)
        {
            w.push_back(this->regs[i]);
        }
        return w;
    }

    // JOBS and every JOB_BEATS (or 1): what decides the empty run
    std::vector<uint32_t> config() const
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
        for (uint32_t w : this->config())
        {
            if (w == 0)
            {
                return true;
            }
        }
        return false;
    }

    // A write of value to read-write CSR index in cycle: held while the unit
    // is busy, else taken
    Write write(int64_t cycle, int index, uint32_t value)
    {
        if (!this->unit_idle(cycle))
        {
            this->held = true;
            this->held_index = index;
            this->held_value = value;
            return {true, false, false};
        }
        return this->take(cycle, index, value);
    }

    // A read in cycle of CSR index: a read-write one as kept (START 0), then
    // STATUS and BUSY_COUNTER
    uint32_t read(int64_t cycle, int index) const
    {
        if (index < this->nb_rw())
        {
            return this->regs[index];
        }
        return index == this->nb_rw() ? this->status_at(cycle) : this->busy_counter_at(cycle);
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

    // The cycle a held write is taken, E + 1, once the run has ended; -1
    // while none is held or the unit is still busy
    int64_t release_cycle() const
    {
        return this->held && this->unit_run.ended() ? this->unit_run.end_cycle + 1 : -1;
    }

    // The held write taken in cycle and answered: a held start is accepted
    // (and may be the empty run, when nothing goes to the unit)
    Write release(int64_t cycle)
    {
        this->held = false;
        return this->take(cycle, this->held_index, this->held_value);
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

    // The busy cycles in [accept + 1, cycle - 1], saturating at BUSY_COUNTER's width
    uint32_t busy_counter_at(int64_t cycle) const
    {
        return (uint32_t)std::min<int64_t>(this->busy_cycles(cycle), this->busy_counter_max);
    }

    int64_t busy_cycles(int64_t cycle) const
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
    // A write taken in cycle, the unit idle: kept at its width, but START,
    // which only starts (bit 0 set) or does nothing (bit 0 clear)
    Write take(int64_t cycle, int index, uint32_t value)
    {
        if (index != START)
        {
            this->regs[index] = value & this->masks[index];
            return {false, false, false};
        }
        if (!(value & 1))
        {
            return {false, false, false};
        }
        return {false, true, this->accept(cycle)};
    }

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
    std::vector<int> scalar_index;
    std::vector<uint32_t> masks;    // per read-write CSR, its width's values
    uint32_t busy_counter_max = 0xffffffffu;
};
