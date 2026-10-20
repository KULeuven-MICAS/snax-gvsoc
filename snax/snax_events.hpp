/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The three traces a SNAX component writes what it did to (docs/EVENTS.md):
// summary (its counters, on at every level), events (once per task, level
// task) and beats (once per beat, level beat, written from FLOW3 round 2). A
// level is which of them gvrun's --trace regexes turn on. Lines are
// "<cycle> <kind> key=value ...", written at LEVEL_INFO, under GVSoC's
// default trace level.

#pragma once

#include <vp/vp.hpp>


class SnaxEvents
{
public:
    vp::Trace summary;
    vp::Trace events;
    vp::Trace beats;

    void declare(vp::Block *block)
    {
        block->traces.new_trace("summary", &this->summary, vp::INFO);
        block->traces.new_trace("events", &this->events, vp::INFO);
        block->traces.new_trace("beats", &this->beats, vp::INFO);
    }
};
