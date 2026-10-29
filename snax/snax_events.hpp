/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The four traces a SNAX component writes what it did to (docs/EVENTS.md):
// summary (its counters, on at every level), events (once per task, level
// task), beats (once per beat, level beat) and stalls (once per refused
// request or queue count, level stall). A level is which of them gvrun's
// --trace regexes turn on. Lines are "<cycle> <kind> key=value ...", written
// at LEVEL_INFO, under GVSoC's default trace level.
//
// The ids that link a beat's lines travel with its request in IoReq argument
// slots at the top of args, out of the way of the routers (they push from
// slot 0): SNAX_ARG_TAG says which ids the others hold. The iDMA's TCDM
// backend (pulp/pulp/idma/idma.hpp, IDMA_SNAX_ARG_*) uses the same slots.
//
// VCD signals (SnaxSignal, SnaxSignals) are for gtkwave only: vp::Signals a
// component sets, grouped under the tag snax in its gen_gtkw, dumped with
// gvrun's --vcd. GVSoC dumps a signal when it is set, so a value known ahead
// (a pulse that falls, a busy that ends, a queue's count from the next cycle)
// is queued and set by SnaxSignals' event in its own cycle. vp::Signal dumps
// only where CONFIG_GVSOC_EVENT_ACTIVE is defined (the profile and debug
// models, upstream's Event::dump_value); elsewhere SnaxSignals does nothing,
// queues nothing and enqueues no event.

#pragma once

#include <algorithm>
#include <cstdint>
#include <deque>
#include <string>
#include <utility>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/signal.hpp>


// The slots: the tag, then the ids it names
#define SNAX_ARG_TAG (IO_REQ_NB_ARGS - 1)
#define SNAX_ARG_ID (IO_REQ_NB_ARGS - 2)    // a streamer beat's b, a DMA copy's id
#define SNAX_ARG_INDEX (IO_REQ_NB_ARGS - 3) // a DMA beat's index within its copy
#define SNAX_ARG_L2 (IO_REQ_NB_ARGS - 4)    // a DMA beat's address on the copy's other side

// The tags: a streamer's beat (b), a DMA beat (id, i, l2)
#define SNAX_TAG_BEAT ((uintptr_t)0x534e4231)
#define SNAX_TAG_DMA ((uintptr_t)0x534e4432)


class SnaxEvents
{
public:
    vp::Trace summary;
    vp::Trace events;
    vp::Trace beats;
    vp::Trace stalls;

    void declare(vp::Block *block)
    {
        block->traces.new_trace("summary", &this->summary, vp::INFO);
        block->traces.new_trace("events", &this->events, vp::INFO);
        block->traces.new_trace("beats", &this->beats, vp::INFO);
        block->traces.new_trace("stalls", &this->stalls, vp::INFO);
    }
};


// A request's ids, set by its master and read by the crossbar
inline void snax_arg_set(vp::IoReq *req, int slot, uint64_t value)
{
    *req->arg_get(slot) = (void *)(uintptr_t)value;
}

inline uint64_t snax_arg_get(vp::IoReq *req, int slot)
{
    return (uint64_t)(uintptr_t)*req->arg_get(slot);
}


// size bytes from data, little-endian, as a 0x word (at most 8 bytes)
inline std::string snax_word(const uint8_t *data, uint64_t size)
{
    uint64_t value = 0;
    for (uint64_t i = 0; i < size && i < 8; i++)
    {
        value |= (uint64_t)data[i] << (8 * i);
    }
    char text[24];
    snprintf(text, sizeof(text), "0x%lx", (unsigned long)value);
    return text;
}


// One VCD signal, and the values it takes from later cycles, in cycle order
class SnaxSignal
{
public:
    SnaxSignal(vp::Block &block, std::string name, int width)
        : signal(block, name, width) {}

    vp::Signal<uint64_t> signal;
    std::deque<std::pair<int64_t, uint64_t>> pending;
    bool queued = false;        // in SnaxSignals' list
};


// A component's signals' changes from later cycles, set by its own event
class SnaxSignals
{
public:
    SnaxSignals(vp::Block *block)
        : block(block), event(block, &SnaxSignals::handler)
    {
        this->event.get_args()[0] = this;
    }

    // value from this cycle on, in place of the changes queued up to it
    void set(SnaxSignal &s, uint64_t value)
    {
#ifdef CONFIG_GVSOC_EVENT_ACTIVE
        int64_t now = this->now();
        while (!s.pending.empty() && s.pending.front().first <= now)
        {
            s.pending.pop_front();
        }
        this->apply(s, value);
#else
        (void)s;
        (void)value;
#endif
    }

    // value from cycle on, in place of the changes queued from it on
    void set_from(SnaxSignal &s, uint64_t value, int64_t cycle)
    {
#ifdef CONFIG_GVSOC_EVENT_ACTIVE
        int64_t now = this->now();
        if (cycle <= now)
        {
            this->set(s, value);
            return;
        }
        while (!s.pending.empty() && s.pending.back().first >= cycle)
        {
            s.pending.pop_back();
        }
        s.pending.push_back({cycle, value});
        if (!s.queued)
        {
            this->pending.push_back(&s);
            s.queued = true;
        }
        this->event.enqueue(cycle - now);
#else
        (void)s;
        (void)value;
        (void)cycle;
#endif
    }

    // 1 in this cycle only
    void pulse(SnaxSignal &s)
    {
#ifdef CONFIG_GVSOC_EVENT_ACTIVE
        this->set(s, 1);
        this->set_from(s, 0, this->now() + 1);
#else
        (void)s;
#endif
    }

private:
    int64_t now() { return this->block->clock.get_cycles(); }

    void apply(SnaxSignal &s, uint64_t value)
    {
        if (s.signal.get() != value)
        {
            s.signal.set(value);
        }
    }

    static void handler(vp::Block *, vp::ClockEvent *event)
    {
        SnaxSignals *_this = (SnaxSignals *)event->get_args()[0];
        int64_t now = _this->now();
        int64_t next = -1;
        size_t kept = 0;
        for (SnaxSignal *s : _this->pending)
        {
            while (!s->pending.empty() && s->pending.front().first <= now)
            {
                _this->apply(*s, s->pending.front().second);
                s->pending.pop_front();
            }
            if (s->pending.empty())
            {
                s->queued = false;
                continue;
            }
            int64_t cycle = s->pending.front().first;
            next = next == -1 ? cycle : std::min(next, cycle);
            _this->pending[kept++] = s;
        }
        _this->pending.resize(kept);
        if (next != -1)
        {
            _this->event.enqueue(next - now);
        }
    }

    vp::Block *block;
    vp::ClockEvent event;
    std::vector<SnaxSignal *> pending;
};
