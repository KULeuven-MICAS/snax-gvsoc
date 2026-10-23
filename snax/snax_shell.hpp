/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxShell's rule (D130 in snax-forge): the CSR manager in front of a
// SnaxUnit, GeMMX's shell contract as snax_cluster gives it (05615e4): the
// ReqRspManager (hw/chisel/.../reqRspManager/ReqRspManager.scala) holding the
// read-write CSRs, BlockGemm's ctrl handshake, busy and performance counter
// (hw/chisel_acc/.../gemm/BlockGemm.scala), and snax-forge's CsrManager and
// CtrlAdapter, which build it in Chisel. Plain C++, so the component
// (snax_shell.cpp) and the standalone test (tests/snax/shell/) run the same
// code, as snax_unit.hpp.
//
// CSRs, offsets from its first CSR (the CSR mux removes it): the fields
// (property `fields`, in order), then start: read-write, read back as
// written; then busy and the counter: read-only.
//
// Rules, c being the cycle of an access:
//   - a write to a field, or to start with bit 0 clear, is taken at once;
//   - a start (bit 0 of the start CSR written 1) goes to the unit's ctrl as
//     the fields as they stand, in CSR order, when the unit is idle in c
//     (BlockGemm: ctrl.ready is idle); the start is then accepted in c and
//     the write answered at once. While the unit is busy in c the write is
//     held (IO_REQ_PENDING: the ReqRspManager's req.ready is ctrl.ready), and
//     sent, then answered, in the cycle busy falls: E + 1, E the run's last
//     cycle;
//   - busy reads the unit's busy in c;
//   - the counter is reset by an accepted start and counts each busy cycle,
//     then holds after the run (BlockGemm's performance_counter): at c it is
//     the busy cycles after the accepted start and before c. A start the unit
//     ignores (count 0) still resets it.
// Busy and the counter are computed when read, from the cycles the unit's
// busy wire rose (busy from the next cycle) and fell (idle from the next).
// The unit sets the wire synchronously in the ctrl write that starts it, so a
// start sent in c sees its rise in c; it clears it in E.

#pragma once

#include <algorithm>
#include <cstdint>
#include <vector>


class SnaxShellRule
{
public:
    // What a write to a read-write CSR does in its cycle
    struct Write
    {
        bool held;      // a start while the unit is busy: answered when release() takes it
        bool start;     // a start accepted now: the fields go to the unit's ctrl in this cycle
    };

    // Read-write CSRs, as written: the fields, then start
    std::vector<uint32_t> regs;
    // The unit's busy wire: the cycles it last rose and fell (-1 if not)
    int64_t rise_cycle;
    int64_t fall_cycle;
    // The last accepted start (-1 if none)
    int64_t accept_cycle;
    // A start held while busy, and the value it writes to the start CSR
    bool held;
    uint32_t held_value;

    void configure(int nb_fields)
    {
        this->nb_fields = nb_fields;
        this->regs.assign(nb_fields + 1, 0);
        this->reset();
    }

    void reset()
    {
        std::fill(this->regs.begin(), this->regs.end(), 0);
        this->rise_cycle = this->fall_cycle = -1;
        this->accept_cycle = -1;
        this->held = false;
        this->held_value = 0;
    }

    // The start CSR: the last read-write one
    int start_index() const
    {
        return this->nb_fields;
    }

    // A write of value to read-write CSR index in cycle
    Write write(int64_t cycle, int index, uint32_t value)
    {
        if (index != this->start_index() || !(value & 1))
        {
            this->regs[index] = value;
            return {false, false};
        }
        if (this->unit_idle(cycle))
        {
            this->regs[index] = value;
            this->accept_cycle = cycle;
            return {false, true};
        }
        this->held = true;
        this->held_value = value;
        return {true, false};
    }

    // A read in cycle of CSR index: a read-write one as written, then busy and the counter
    uint32_t read(int64_t cycle, int index) const
    {
        if (index < (int)this->regs.size())
        {
            return this->regs[index];
        }
        return index == (int)this->regs.size() ? this->busy_at(cycle) : this->counter_at(cycle);
    }

    // The unit's busy wire set to busy in cycle
    void busy(int64_t cycle, bool busy)
    {
        if (busy)
        {
            this->rise_cycle = cycle;
            this->fall_cycle = -1;
        }
        else
        {
            this->fall_cycle = cycle;
        }
    }

    // The cycle a held start is taken, E + 1, once the run has ended; -1
    // while none is held or the unit is still busy
    int64_t release_cycle() const
    {
        return this->held && this->fall_cycle != -1 ? this->fall_cycle + 1 : -1;
    }

    // The held start taken in cycle: written, accepted (its fields go to the
    // unit's ctrl), and its write answered
    void release(int64_t cycle)
    {
        this->held = false;
        this->regs[this->start_index()] = this->held_value;
        this->accept_cycle = cycle;
    }

    // Idle in cycle: never started, or the last run ended before it
    bool unit_idle(int64_t cycle) const
    {
        return this->rise_cycle == -1 || (this->fall_cycle != -1 && this->fall_cycle < cycle);
    }

    bool busy_at(int64_t cycle) const
    {
        return this->rise_cycle != -1 && cycle > this->rise_cycle &&
            (this->fall_cycle == -1 || cycle <= this->fall_cycle);
    }

    // The busy cycles in [accept + 1, cycle - 1]
    uint32_t counter_at(int64_t cycle) const
    {
        if (this->accept_cycle == -1 || this->rise_cycle == -1)
        {
            return 0;
        }
        int64_t first = std::max(this->accept_cycle, this->rise_cycle) + 1;
        int64_t last = cycle - 1;
        if (this->fall_cycle != -1 && this->fall_cycle < last)
        {
            last = this->fall_cycle;
        }
        return last >= first ? last - first + 1 : 0;
    }

private:
    int nb_fields;
};
