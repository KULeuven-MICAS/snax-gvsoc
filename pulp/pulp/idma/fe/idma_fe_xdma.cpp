/*
 * Copyright (C) 2024 ETH Zurich and University of Bologna
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/*
 * Authors: Germain Haugou, ETH Zurich (germain.haugou@iis.ee.ethz.ch)
 */

#include <vp/vp.hpp>
#include "idma_fe_xdma.hpp"



IDmaFeXdma::IDmaFeXdma(vp::Component *idma, IdmaTransferConsumer *me)
    : Block(idma, "fe"),
    src(*this, "src", 64),
    dst(*this, "dst", 64),
    src_stride(*this, "src_stride", 32),
    dst_stride(*this, "dst_stride", 32),
    reps(*this, "reps", 32),
    next_transfer_id(*this, "next_transfer_id", 32, true, 2),
    completed_id(*this, "completed_id", 32, true, 1),
    do_transfer_grant(*this, "do_transfer_grant", 1)
{
    // Middle-end will be used later for interaction
    this->me = me;

    // Declare our own trace so that we can individually activate traces
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    // Declare offload slave interface where instructions will be offloaded
    this->offload_itf.set_sync_meth(&IDmaFeXdma::offload_sync);
    idma->new_slave_port("offload", &this->offload_itf, this);

    // Declare offload master interface for granting blocked transfers
    idma->new_master_port("offload_grant", &this->offload_grant_itf, this);

    // SNAX: perf event wires and the beat size they count in
    idma->new_master_port("busy", &this->busy_itf, this);
    idma->new_master_port("r_beats", &this->r_beats_itf, this);
    idma->new_master_port("w_beats", &this->w_beats_itf, this);
    js::Config *beat_size = idma->get_js_config()->get("beat_size");
    this->beat_size = beat_size ? beat_size->get_int() : 64;
    this->busy = false;

    // SNAX, FLOW3's events
    this->idma = idma;
    this->traces.new_trace("summary", &this->ev_summary, vp::INFO);
    this->traces.new_trace("events", &this->ev_events, vp::INFO);
    this->traces.new_trace("beats", &this->ev_beats, vp::INFO);
    this->loc_base = idma->get_js_config()->get_child_int("loc_base");
    this->loc_size = idma->get_js_config()->get_child_int("loc_size");
    this->transfers = this->busy_cycles = this->busy_since = 0;
    this->r_beats_total = this->w_beats_total = 0;
    this->bytes_to_l1 = this->bytes_from_l1 = 0;
}



// Called by core to offload xdma instructions
void IDmaFeXdma::offload_sync(vp::Block *__this, IssOffloadInsn<uint32_t> *insn)
{
    IDmaFeXdma *_this = (IDmaFeXdma *)__this;
    uint32_t func7 = insn->opcode >> 25;

    insn->granted = true;

    switch (func7)
    {
        case 0b0000000:
        {
            uint64_t addr = (((uint64_t)insn->arg_b) << 32) | insn->arg_a;
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmsrc operation (addr: 0x%llx)\n",
                addr);
            _this->src.set(addr);
            break;
        }
        case 0b0000001:
        {
            uint64_t addr = (((uint64_t)insn->arg_b) << 32) | insn->arg_a;
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmdst operation (addr: 0x%llx)\n",
                addr);
            _this->dst.set(addr);
            break;
        }
        case 0b0000110:
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmstr operation (src_stride: 0x%lx, dst_stride: 0x%lx)\n",
                insn->arg_a, insn->arg_b);
            _this->src_stride.set(insn->arg_a);
            _this->dst_stride.set(insn->arg_b);
            break;
        case 0b0000111:
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmrep operation (reps: 0x%lx)\n", insn->arg_a);
            _this->reps.set(insn->arg_a);
            break;
        case 0b0000011:
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmcpy operation (config: 0x%lx, size: 0x%lx)\n",
                insn->arg_b, insn->arg_a);
            insn->result = _this->enqueue_copy(insn->arg_b, insn->arg_a, insn->granted);
            break;
        case 0b0000101:
            // _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmstat operation (status: 0x%lx)\n",
            //     insn->arg_b);
            insn->result = _this->get_status(insn->arg_b);
            break;
        case 0b0000010:
            _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmcpy operation (config: 0x%lx, size: 0x%lx)\n",
                insn->arg_b, insn->arg_a);
            insn->result = _this->enqueue_copy(insn->arg_b, insn->arg_a, insn->granted);
            break;
        case 0b0000100:
            // _this->trace.msg(vp::Trace::LEVEL_TRACE, "Received dmstat operation (status: 0x%lx)\n",
            //     insn->arg_b);
            insn->result = _this->get_status(insn->arg_b);
            break;
    }
}



uint32_t IDmaFeXdma::get_status(uint32_t status)
{
    switch (status)
    {
        case 0: return this->completed_id.get();
        case 1: return this->next_transfer_id.get() + 1;
        case 2: return this->next_transfer_id.get() - this->completed_id.get() != 1;
        case 3: return !this->me->can_accept_transfer();
    }

    return 0;
}



uint32_t IDmaFeXdma::enqueue_copy(uint32_t config, uint32_t size, bool &granted)
{
    // Allocate transfer ID
    uint32_t transfer_id = this->next_transfer_id.get();
    this->next_transfer_id.set(transfer_id + 1);
    this->update_busy();

    this->trace.msg(vp::Trace::LEVEL_TRACE, "Allocated transfer ID (id: %d)\n", transfer_id);

    // Allocate a new transfer and fill it from registers
    IdmaTransfer *transfer = new IdmaTransfer();
    transfer->src = this->src.get();
    transfer->dst = this->dst.get();
    transfer->size = size;
    transfer->src_stride = this->src_stride.get();
    transfer->dst_stride = this->dst_stride.get();
    transfer->reps = this->reps.get();
    transfer->config = config;

    this->trace.msg(vp::Trace::LEVEL_INFO, "Enqueuing transfer (id: %d, src: %llx, dst: %llx, "
        "size: %llx, src_stride: %llx, dst_stride: %llx, reps: %llx, config: %llx)\n",
        transfer_id, transfer->src, transfer->dst, transfer->size, transfer->src_stride,
        transfer->dst_stride, transfer->reps, transfer->config);

    // SNAX, FLOW3's events: the copy as the core issued it, its rows 1 for a 1D copy
    uint64_t rows = (transfer->config >> 1) & 1 ? transfer->reps : 1;
    this->transfers++;
    if (this->is_local(transfer->dst))
    {
        this->bytes_to_l1 += rows * transfer->size;
    }
    if (this->is_local(transfer->src))
    {
        this->bytes_from_l1 += rows * transfer->size;
    }
    this->ev_events.msg(vp::Trace::LEVEL_INFO, "%ld issue id=%u src=0x%lx dst=0x%lx size=%lu "
        "src_stride=%lu dst_stride=%lu reps=%lu\n", (long)this->idma->clock.get_cycles(),
        transfer_id, (unsigned long)transfer->src, (unsigned long)transfer->dst,
        (unsigned long)transfer->size, (unsigned long)transfer->src_stride,
        (unsigned long)transfer->dst_stride, (unsigned long)rows);

    this->send_beats(transfer);

    // In case size is 0 or reps is 0 with 2d transfer, directly terminate the transfer.
    // This could be done few cycles after to better match HW.
    if (size == 0 || ((transfer->config >> 1) & 1) && transfer->reps == 0)
    {
        this->ack_transfer(transfer);
        return transfer_id;
    }

    // Check if middle end can accept a new transfer
    if (this->me->can_accept_transfer())
    {
        // If no enqueue the burst
        granted = true;
        this->me->enqueue_transfer(transfer);
    }
    else
    {
        // Otherwise, stall the core and keep the transfer until we can grant it
        this->trace.msg(vp::Trace::LEVEL_TRACE, "Middle-end not ready, blocking transfer\n");
        this->stalled_transfer = transfer;
        granted = false;

        this->do_transfer_grant.set(true);
    }

    return transfer_id;
}



// Called by middle-end when a transfer is done
void IDmaFeXdma::ack_transfer(IdmaTransfer *transfer)
{
    // Copies complete in order: this one's ID is the next after the last completed
    this->ev_events.msg(vp::Trace::LEVEL_INFO, "%ld done id=%u\n",
        (long)this->idma->clock.get_cycles(), this->completed_id.get() + 1);
    this->completed_id.inc(1);
    this->update_busy();
    delete transfer;
}

void IDmaFeXdma::update_busy()
{
    bool busy = this->next_transfer_id.get() - this->completed_id.get() != 1;
    if (busy != this->busy)
    {
        // SNAX, FLOW3's events: the busy cycles, as DMA_BUSY counts them
        int64_t cycle = this->idma->clock.get_cycles();
        if (busy)
        {
            this->busy_since = cycle;
        }
        else
        {
            this->busy_cycles += cycle - this->busy_since;
        }
        this->busy = busy;
        if (this->busy_itf.is_bound())
        {
            this->busy_itf.sync(busy);
        }
    }
}

uint64_t IDmaFeXdma::beats(uint64_t base, uint64_t size)
{
    if (size == 0)
    {
        return 0;
    }
    return (base + size - 1) / this->beat_size - base / this->beat_size + 1;
}

void IDmaFeXdma::send_beats(IdmaTransfer *transfer)
{
    // A 2D copy is reps rows of size bytes; a 1D copy is one row. Beats never straddle a
    // 4 KiB page, so the sum over rows equals the sum over the bursts the RTL emits.
    bool is_2d = (transfer->config >> 1) & 1;
    uint64_t rows = is_2d ? transfer->reps : 1;
    uint64_t r_beats = 0, w_beats = 0;
    for (uint64_t i = 0; i < rows; i++)
    {
        r_beats += this->beats(transfer->src + i * transfer->src_stride, transfer->size);
        w_beats += this->beats(transfer->dst + i * transfer->dst_stride, transfer->size);
    }
    this->r_beats_total += r_beats;
    this->w_beats_total += w_beats;
    if (r_beats > 0 && this->r_beats_itf.is_bound())
    {
        this->r_beats_itf.sync((int)r_beats);
    }
    if (w_beats > 0 && this->w_beats_itf.is_bound())
    {
        this->w_beats_itf.sync((int)w_beats);
    }
}



// Called by middle-end when something has been updated to check if we must take any action
void IDmaFeXdma::update()
{
    // In case a transfer is blocked and the middle-end is now ready, unblock it and grant it
    // to unstall the core
    if (this->do_transfer_grant.get() && this->me->can_accept_transfer())
    {
        this->do_transfer_grant.set(false);

        this->trace.msg(vp::Trace::LEVEL_TRACE, "Middle-end got ready, unblocking transfer\n");

        IdmaTransfer *transfer = this->stalled_transfer;

        IssOffloadInsnGrant<uint32_t> offload_grant = {
            .result=this->next_transfer_id.get() - 1
        };
        this->offload_grant_itf.sync(&offload_grant);
        this->me->enqueue_transfer(transfer);
    }
}



void IDmaFeXdma::reset(bool active)
{
    if (active)
    {
        this->busy = false;
    }
}



// SNAX: whether addr is in the cluster's local area (its L1)
bool IDmaFeXdma::is_local(uint64_t addr)
{
    return addr >= this->loc_base && addr < this->loc_base + this->loc_size;
}



// SNAX, FLOW3's events: the counts at the end of the simulation, a copy still running
// counted up to now
void IDmaFeXdma::stop()
{
    int64_t cycle = this->idma->clock.get_cycles();
    int64_t busy = this->busy_cycles + (this->busy ? cycle - this->busy_since : 0);
    this->ev_summary.msg(vp::Trace::LEVEL_INFO, "%ld dma transfers=%ld busy=%ld r_beats=%ld "
        "w_beats=%ld bytes_to_l1=%ld bytes_from_l1=%ld\n", (long)cycle, (long)this->transfers,
        (long)busy, (long)this->r_beats_total, (long)this->w_beats_total,
        (long)this->bytes_to_l1, (long)this->bytes_from_l1);
}