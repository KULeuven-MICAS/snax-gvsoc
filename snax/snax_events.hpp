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

#pragma once

#include <cstdint>
#include <string>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>


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
