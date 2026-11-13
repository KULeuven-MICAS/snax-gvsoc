/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The rule of a shared streamer's data-side mux, plain C++
// so the component (snax_port_mux.cpp) and its testbench (tests/snax/port_mux/)
// run the same code.
//
// A streamer set whose groups share its movers: each mover serves at most one
// port of each group, a port as wide as the mover or narrower (its first
// channels). PORT_MUX_SEL holds the group whose ports are connected; the core
// writes it before STREAMER_START, while the streamer is not busy. A reader's
// beat goes to the selected group's port, its first num_channel words; a
// group's output beat goes to its writer with the mover's other words 0. The
// mux is combinational, so a beat takes no cycle.
//
// Each check returns an error, which the component turns into a fatal: a beat
// or probe from a group not selected (on the RTL its valid and ready are
// never seen, the run would hang or lose data), an access of the wrong
// direction or size, a select write while the streamer is busy, a select past
// the last group.

#pragma once

#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>


// A mover of the shared streamer
struct SnaxMuxMover
{
    bool is_reader;
    int num_channel;
};

// A group's port on a mover: num_channel words per beat, at most the mover's
struct SnaxMuxPort
{
    int group;
    int mover;
    int num_channel;
};

enum SnaxMuxError
{
    SNAX_MUX_OK,
    SNAX_MUX_NOT_SELECTED,      // a group not selected accesses its port
    SNAX_MUX_WRONG_ACCESS,      // a read on a writer's port, or a size not its beat's or 0
    SNAX_MUX_BUSY,              // PORT_MUX_SEL written while the streamer is busy
    SNAX_MUX_NO_GROUP,          // PORT_MUX_SEL past the last group
};


class SnaxPortMuxRule
{
public:
    SnaxPortMuxRule() {}

    // Throws std::invalid_argument on a configuration that cannot be: a port on no mover, wider
    // than its mover, of no group, or two ports of one group on one mover
    SnaxPortMuxRule(int nb_groups, std::vector<SnaxMuxMover> movers,
        std::vector<SnaxMuxPort> ports)
        : nb_groups(nb_groups), movers(movers), ports(ports)
    {
        if (nb_groups < 1)
        {
            throw std::invalid_argument("no group");
        }
        std::vector<std::vector<bool>> used(movers.size(), std::vector<bool>(nb_groups));
        for (size_t i = 0; i < ports.size(); i++)
        {
            const SnaxMuxPort &p = ports[i];
            std::string at = "port " + std::to_string(i) + ": ";
            if (p.group < 0 || p.group >= nb_groups)
            {
                throw std::invalid_argument(at + "group " + std::to_string(p.group)
                    + " of " + std::to_string(nb_groups));
            }
            if (p.mover < 0 || p.mover >= (int)movers.size())
            {
                throw std::invalid_argument(at + "mover " + std::to_string(p.mover)
                    + " of " + std::to_string(movers.size()));
            }
            if (p.num_channel < 1 || p.num_channel > movers[p.mover].num_channel)
            {
                throw std::invalid_argument(at + std::to_string(p.num_channel)
                    + " channels on a mover of " + std::to_string(movers[p.mover].num_channel));
            }
            if (used[p.mover][p.group])
            {
                throw std::invalid_argument(at + "a second port of group "
                    + std::to_string(p.group) + " on mover " + std::to_string(p.mover));
            }
            used[p.mover][p.group] = true;
        }
    }

    void reset() { this->sel = 0; }

    uint32_t selected() const { return this->sel; }

    // A write of PORT_MUX_SEL, the streamer busy or not
    SnaxMuxError select(uint32_t value, bool streamer_busy)
    {
        if (streamer_busy)
        {
            return SNAX_MUX_BUSY;
        }
        if (value >= (uint32_t)this->nb_groups)
        {
            return SNAX_MUX_NO_GROUP;
        }
        this->sel = value;
        return SNAX_MUX_OK;
    }

    // An access on port: a probe (size 0) or a beat of its own size, in its mover's direction
    SnaxMuxError check(int port, bool is_write, uint64_t size) const
    {
        const SnaxMuxPort &p = this->ports[port];
        if (is_write == this->movers[p.mover].is_reader
            || (size != 0 && size != 8 * (uint64_t)p.num_channel))
        {
            return SNAX_MUX_WRONG_ACCESS;
        }
        if ((uint32_t)p.group != this->sel)
        {
            return SNAX_MUX_NOT_SELECTED;
        }
        return SNAX_MUX_OK;
    }

    int mover_of(int port) const { return this->ports[port].mover; }

    // The mover's access for the port's: a probe stays one, a beat is the mover's size
    uint64_t mover_size(int port, uint64_t size) const
    {
        return size == 0 ? 0 : 8 * (uint64_t)this->movers[this->ports[port].mover].num_channel;
    }

    // A reader's beat to the port: its first words
    void to_port(int port, const uint64_t *mover_beat, uint64_t *beat) const
    {
        std::copy(mover_beat, mover_beat + this->ports[port].num_channel, beat);
    }

    // A port's beat to its writer: the mover's other words 0
    void to_mover(int port, const uint64_t *beat, uint64_t *mover_beat) const
    {
        const SnaxMuxPort &p = this->ports[port];
        std::copy(beat, beat + p.num_channel, mover_beat);
        std::fill(mover_beat + p.num_channel, mover_beat + this->movers[p.mover].num_channel, 0);
    }

    static const char *error_name(SnaxMuxError error)
    {
        switch (error)
        {
        case SNAX_MUX_OK: return "ok";
        case SNAX_MUX_NOT_SELECTED: return "its group is not selected";
        case SNAX_MUX_WRONG_ACCESS: return "not its direction or beat size";
        case SNAX_MUX_BUSY: return "the streamer is busy";
        case SNAX_MUX_NO_GROUP: return "past the last group";
        }
        return "?";
    }

private:
    int nb_groups = 1;
    std::vector<SnaxMuxMover> movers;
    std::vector<SnaxMuxPort> ports;
    uint32_t sel = 0;
};
