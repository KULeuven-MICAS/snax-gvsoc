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
// Modified for SNAX-GVSoC (KU Leuven MICAS), see UPSTREAM.md

#pragma once

#include <vp/vp.hpp>
#include <cpu/iss/include/offload.hpp>
#include <vp/register.hpp>
#include <vp/signal.hpp>
#include "../idma.hpp"

/**
 * @brief XDma front-end
 *
 * This front-end can be used to connect a core to the iDMA through the custom XDMa instructions
 */
class IDmaFeXdma : public vp::Block, public IdmaTransferProducer
{
public:
    /**
     * @brief Construct a new IDmaFeXdma frontend
     *
     * @param idma The top iDMA block.
     * @param me The middle end.
     */
    IDmaFeXdma(vp::Component *idma, IdmaTransferConsumer *me);

    void reset(bool active) override;
    void stop() override;

    void update() override;
    void ack_transfer(IdmaTransfer *transfer) override;

private:
    // Method for offload interface, called when the core is offloading an xdma instruction
    static void offload_sync(vp::Block *__this, IssOffloadInsn<uint32_t> *insn);
    // Enqueue a transfer using the current values of the registers
    uint32_t enqueue_copy(uint32_t config, uint32_t size, bool &granted);
    // Return status
    uint32_t get_status(uint32_t status);
    // Drive the busy wire from the transfer IDs, the state dmstat 2 returns (SNAX)
    void update_busy();
    // Send the beats a copy reads and writes on the beat wires (SNAX)
    void send_beats(IdmaTransfer *transfer);
    // Number of AXI beats the byte range [base, base + size) touches (SNAX)
    uint64_t beats(uint64_t base, uint64_t size);

    // Pointer to middle-end
    IdmaTransferConsumer *me;
    // Trace for this block, messages will be displayed with this block's name
    vp::Trace trace;
    // Interface from which the instructions are received from the core
    vp::WireSlave<IssOffloadInsn<uint32_t> *> offload_itf;
    // Interface for granting previously stalled xdma offload
    vp::WireMaster<IssOffloadInsnGrant<uint32_t> *> offload_grant_itf;
    // Register holding source address
    vp::Register<uint64_t> src;
    // Register holding destination address
    vp::Register<uint64_t> dst;
    // Register holding source stride
    vp::Register<uint64_t> src_stride;
    // Register holding destination stride
    vp::Register<uint64_t> dst_stride;
    // Register holding replication
    vp::Register<uint32_t> reps;
    // Transfer ID of the next transfer
    vp::Register<uint32_t> next_transfer_id;
    // Transfer ID of the last completed ID
    vp::Register<uint32_t> completed_id;
    // When a transfer is blocked, once the middle-end is ready to accept transfer,
    // send a grant to the core to unblock it
    vp::Signal<bool> do_transfer_grant;
    // In case a transfer was blocked, gives the transfer which was blocked
    IdmaTransfer *stalled_transfer;
    // SNAX: the cluster's DMA perf events (snitch_cluster_peripheral.sv). The busy wire
    // follows dmstat 2; the beat wires carry the beats of a copy when it is queued, the
    // sum of what the RTL's R and W handshakes count. Unbound wires are not driven.
    vp::WireMaster<bool> busy_itf;
    vp::WireMaster<int> r_beats_itf;
    vp::WireMaster<int> w_beats_itf;
    // Last value sent on the busy wire
    bool busy;
    // SNAX: the busy wire as a VCD signal (snitch_cc.sv's dma_busy), for gtkwave
    vp::Signal<bool> dma_busy;
    // Bytes per AXI beat (64 for the 512-bit DMA)
    uint64_t beat_size;
    // SNAX events (docs/EVENTS.md): the summary, events and beats
    // traces, and the counts the summary gives at stop. A copy's bytes go to L1 when its
    // destination is in the local area (loc_base, loc_size), from L1 when its source is.
    vp::Component *idma;
    vp::Trace ev_summary;
    vp::Trace ev_events;
    vp::Trace ev_beats;
    uint64_t loc_base;
    uint64_t loc_size;
    int64_t transfers;
    int64_t busy_cycles;
    int64_t busy_since;
    int64_t r_beats_total;
    int64_t w_beats_total;
    int64_t bytes_to_l1;
    int64_t bytes_from_l1;
    bool is_local(uint64_t addr);
};
