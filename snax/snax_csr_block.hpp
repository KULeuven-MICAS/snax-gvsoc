/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The CSRs of a SNAX block behind snax_cluster's ReqRspManager, as the
// streamer and the ALU share them: nb_rw read-write CSRs, read back as
// written and 0 after reset, then nb_ro read-only ones the block computes.
// A 32-bit access at offset 4 * index from the block's first CSR (the CSR
// mux removes it). A write to a read-only CSR, or any access past them, is
// refused: an assert in the ReqRspManager on the RTL.

#pragma once

#include <algorithm>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>


class SnaxCsrBlock
{
public:
    // Read-write CSRs, as written
    std::vector<uint32_t> regs;

    void configure(vp::Trace *trace, uint32_t csr_base, int nb_rw, int nb_ro)
    {
        this->trace = trace;
        this->csr_base = csr_base;
        this->nb_ro = nb_ro;
        this->regs.assign(nb_rw, 0);
    }

    void reset()
    {
        std::fill(this->regs.begin(), this->regs.end(), 0);
    }

    // The CSR number at index, for the block's own messages
    uint32_t csr(int index)
    {
        return this->csr_base + index;
    }

    // Answers what every block answers alike: the refusals, a read of a
    // read-write CSR, a read of read-only CSR i from read_only(i). Returns
    // -1 with *status set, or, for a write to a read-write CSR, its index:
    // the block takes it with write().
    template <typename ReadOnly>
    int access(vp::IoReq *req, vp::IoReqStatus *status, ReadOnly read_only)
    {
        uint32_t *data = (uint32_t *)req->get_data();
        bool is_write = req->get_is_write();
        *status = vp::IO_REQ_INVALID;
        if (req->get_size() != 4 || req->get_addr() % 4 != 0)
        {
            this->trace->force_warning("Unexpected access (addr: 0x%lx, size: %ld)\n",
                req->get_addr(), req->get_size());
            return -1;
        }
        int index = req->get_addr() / 4;
        int nb_rw = this->regs.size();
        uint32_t csr = this->csr(index);

        if (index < nb_rw)
        {
            if (is_write)
            {
                return index;
            }
            *data = this->regs[index];
            this->trace->msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x)\n", csr, *data);
            *status = vp::IO_REQ_OK;
            return -1;
        }

        if (index < nb_rw + this->nb_ro)
        {
            if (is_write)
            {
                this->trace->force_warning("Write to read-only CSR %d (value: 0x%x)\n", csr, *data);
                return -1;
            }
            *data = read_only(index - nb_rw);
            this->trace->msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x%x, read-only)\n",
                csr, *data);
            *status = vp::IO_REQ_OK;
            return -1;
        }

        this->trace->force_warning("CSR %d is not held by this block (is_write: %d)\n",
            csr, is_write);
        return -1;
    }

    // Takes a write to read-write CSR index; note ends its trace line
    void write(int index, uint32_t value, const char *note = "")
    {
        this->regs[index] = value;
        this->trace->msg(vp::Trace::LEVEL_DEBUG, "Write CSR %d (value: 0x%x)%s\n",
            this->csr(index), value, note);
    }

private:
    vp::Trace *trace;
    uint32_t csr_base;
    int nb_ro;
};
