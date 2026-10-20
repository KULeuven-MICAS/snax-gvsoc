/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The per-bank pick of snax_cluster's plain interconnect: common_cells
// v1.40.0 rr_arb_tree with FairArb and LockIn, as stream_xbar instantiates it
// in snitch_tcdm_interconnect.sv. Plain C++, so the crossbar
// (snax_tcdm_xbar.cpp) and the winner check against the RTL
// (tests/snax/plain_arb/) run the same code. docs/plans/SG7.md has the
// reading.

#pragma once

#include <cstdint>


// One bank's arbitration tree. pick() is called only in cycles where the
// bank has a request, then granted() or refused() for its winner.
class SnaxPlainArb
{
public:
    explicit SnaxPlainArb(int nb_inputs = 1)
        : nb_inputs(nb_inputs),
          nb_levels(nb_inputs > 1 ? 32 - __builtin_clz(nb_inputs - 1) : 0)
    {
        this->reset();
    }

    void reset()
    {
        this->rr_q = 0;
        this->lock = false;
        this->lock_cycle = -2;
    }

    // The winner among the inputs in req (one bit each, nonzero). Locked by a
    // refusal in the last cycle, the tree arbitrates the vector it arbitrated
    // then, of which only the inputs still asking: the same winner, while it
    // still asks.
    int pick(int64_t cycle, uint64_t req)
    {
        uint64_t req_d = req;
        if (this->lock && this->lock_cycle == cycle - 1 && ((req >> this->locked) & 1))
        {
            req_d = this->lock_req & req;
        }
        this->lock = false;
        this->req_d = req_d;
        this->cycle = cycle;

        bool has_req;
        this->winner = this->nb_levels == 0 ? 0 : this->tree_pick(req_d, 0, 0, has_req);
        return this->winner;
    }

    // The winner was granted: rr_q moves over the vector arbitrated (FairArb)
    void granted()
    {
        if (this->nb_levels != 0)
        {
            this->rr_q = this->next_rr(this->req_d);
        }
    }

    // The winner was refused by its bank: rr_q stays, the decision is locked
    void refused()
    {
        this->lock = true;
        this->lock_req = this->req_d;
        this->locked = this->winner;
        this->lock_cycle = this->cycle;
    }

private:
    // One node: level 0 is the root, nb_levels - 1 the level fed by the
    // inputs. Returns the index of the input the node passes on.
    int tree_pick(uint64_t req, int level, int node, bool &has_req)
    {
        bool rr_bit = (this->rr_q >> (this->nb_levels - 1 - level)) & 1;

        if (level == this->nb_levels - 1)
        {
            int left = 2 * node, right = 2 * node + 1;
            bool req_left = left < this->nb_inputs && ((req >> left) & 1);
            bool req_right = right < this->nb_inputs && ((req >> right) & 1);
            has_req = req_left || req_right;
            // sel = ~req_d[l*2] | req_d[l*2+1] & rr_q[NumLevels-1-level]
            bool sel = !req_left || (req_right && rr_bit);
            return sel ? right : left;
        }

        bool req_left, req_right;
        int left = this->tree_pick(req, level + 1, 2 * node, req_left);
        int right = this->tree_pick(req, level + 1, 2 * node + 1, req_right);
        has_req = req_left || req_right;
        // sel = ~req_nodes[Idx1] | req_nodes[Idx1+1] & rr_q[NumLevels-1-level]
        bool sel = !req_left || (req_right && rr_bit);
        return sel ? right : left;
    }

    // FairArb: the first requesting input above rr_q, or, if there is none,
    // the first at or below it
    int next_rr(uint64_t req)
    {
        uint64_t upper = req & ~((2ULL << this->rr_q) - 1);
        uint64_t lower = req & ((2ULL << this->rr_q) - 1);
        return upper ? __builtin_ctzll(upper) : __builtin_ctzll(lower);
    }

    int nb_inputs;
    int nb_levels;          // clog2(nb_inputs)
    int rr_q;               // the round-robin state
    bool lock;              // the last cycle's winner was refused
    uint64_t lock_req;      // the vector arbitrated then (req_q)
    int locked;             // its winner
    int64_t lock_cycle;     // that cycle
    uint64_t req_d;         // this cycle's vector arbitrated
    int winner;             // and its winner
    int64_t cycle;          // this cycle
};
