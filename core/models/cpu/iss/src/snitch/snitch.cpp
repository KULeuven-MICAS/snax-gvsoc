/*
 * Copyright (C) 2020 GreenWaves Technologies, SAS, ETH Zurich and
 *                    University of Bologna
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
 * Authors: Germain Haugou, GreenWaves Technologies (germain.haugou@greenwaves-technologies.com)
 *          Kexin Li, ETH Zurich (likexi@ethz.ch)
 */
// Modified for SNAX-GVSoC (KU Leuven MICAS), see UPSTREAM.md

#include "cpu/iss/include/iss.hpp"
#include <string.h>


Iss::Iss(IssWrapper &top)
    : prefetcher(*this), exec(top, *this), insn_cache(*this), decode(*this), timing(*this), core(*this), irq(*this),
      gdbserver(*this), lsu(top, *this), dbgunit(*this), syscalls(top, *this), trace(*this), csr(*this),
      regfile(top, *this), exception(*this), ssr(*this), memcheck(top, *this), top(top)
#if defined(CONFIG_GVSOC_ISS_SPATZ)
      , spatz(*this)
#endif
{
    this->csr.declare_csr(&this->barrier, "barrier", 0x7C2);
    this->barrier.register_callback(std::bind(&Iss::barrier_update, this, std::placeholders::_1,
        std::placeholders::_2));
    this->csr.declare_csr(&this->csr_ssr, "ssr", 0x7C0);
    this->csr_ssr.register_callback(std::bind(&Iss::ssr_access, this, std::placeholders::_1,
        std::placeholders::_2));
    this->csr.declare_csr(&this->csr_fmode, "fmode", 0x800);

    // snax_cluster's start-up code reads its cluster base address (0xBC1 low,
    // 0xBC2 high) and {core count, core index} (0xBC3) from these CSRs, which
    // the RTL makes read-only: a write mask of 0 ignores writes as it does.
    js::Config *config = this->top.get_js_config();
    iss_reg_t snax_base = (uint32_t)config->get_child_int("snax_cluster_base_addr");
    iss_reg_t snax_core_id = ((uint32_t)config->get_child_int("snax_cluster_nb_cores") << 16)
        | ((uint32_t)config->get_child_int("snax_cluster_core_idx") & 0xFFFF);
    this->csr.declare_csr(&this->snax_base_addr_l, "snax_base_addr_l", 0xBC1, snax_base, 0);
    this->csr.declare_csr(&this->snax_base_addr_h, "snax_base_addr_h", 0xBC2, 0, 0);
    this->csr.declare_csr(&this->snax_cluster_core_id, "snax_cluster_core_id", 0xBC3, snax_core_id, 0);
    this->snax_base_addr_l.value = snax_base;
    this->snax_base_addr_h.value = 0;
    this->snax_cluster_core_id.value = snax_core_id;

    // snax_cluster's accelerator CSRs 0x3C0 to 0x5FF, one object each, sent out on the
    // snax_csr port. The object carries its own number, since the callback path
    // (csrrs, csrrc) does not see the instruction.
    for (int i = 0; i < SNAX_CSR_NB; i++)
    {
        SnaxCsr *snax_csr = &this->snax_csrs[i];
        snax_csr->address = SNAX_CSR_FIRST + i;
        this->csr.declare_csr(snax_csr, "snax_csr_" + std::to_string(snax_csr->address),
            snax_csr->address);
        snax_csr->register_callback(std::bind(&Iss::snax_csr_access, this, snax_csr,
            std::placeholders::_1, std::placeholders::_2));
    }
    this->snax_csr_itf.set_resp_meth(&Iss::snax_csr_response);
    this->top.new_master_port("snax_csr", &this->snax_csr_itf, (vp::Block *)this);

    this->barrier_ack_itf.set_sync_meth(&Iss::barrier_sync);
    this->top.new_slave_port("barrier_ack", &this->barrier_ack_itf, (vp::Block *)this);

    this->top.new_master_port("barrier_req", &this->barrier_req_itf, (vp::Block *)this);

    this->waiting_barrier = false;


    this->snitch = true;
    this->fp_ss = false;
    this->top.traces.new_trace("offload", &this->trace_iss, vp::DEBUG);


    // -----------USE MASTER AND SLAVE PORT TO HANDLE OFFLOAD REQUEST------------------
    this->event = this->top.event_new((vp::Block *)this, handle_event);

    this->top.new_master_port("acc_req_ready", &this->acc_req_ready_itf);

    this->top.new_master_port("acc_req", &this->acc_req_itf, (vp::Block *)this);

    this->acc_rsp_itf.set_sync_meth(&Iss::handle_result);
    this->top.new_slave_port("acc_rsp", &this->acc_rsp_itf, (vp::Block *)this);
}


// This gets called when the barrier csr is accessed
bool Iss::barrier_update(bool is_write, iss_reg_t &value)
{
    if (!is_write)
    {
        // Since syncing the barrier can immediatly trigger it, we need
        // to flag that we are waiting fro the barrier.
        this->waiting_barrier = true;

        // Notify the global barrier
        if (this->barrier_req_itf.is_bound())
        {
            this->barrier_req_itf.sync(1);
        }

        // Now we have to check if the barrier was already reached and the barrier
        // sync function already called.
        if (this->waiting_barrier)
        {
            // If not, stall the core, this will get unstalled when the barrier sync is called
            this->exec.insn_stall();
        }
    }

    return false;
}


// Sends one access to a SNAX CSR out on the snax_csr port: a 32-bit IO request at byte
// address 4 * CSR number. The block behind the port answers at once (IO_REQ_OK); its
// latency is counted as stall cycles. A block refuses an access with IO_REQ_INVALID, after
// a warning in its own trace. A write may be held (IO_REQ_PENDING, a start while the
// accelerator is busy, GEN3): the core stalls until the block's response, as the LSU does
// for a pending access (Lsu::data_req_aligned, Lsu::data_response). Reads are answered at
// once; a pending read is not supported.
bool Iss::snax_csr_request(iss_reg_t address, bool is_write, iss_reg_t &value)
{
    if (!this->snax_csr_itf.is_bound())
    {
        // Nothing behind the port: the CSR is unsupported, as without this model
        this->csr.trace.force_warning("Accessing unsupported CSR (id: 0x%x, name: %s)\n",
            address, iss_csr_name(this, address));
        return false;
    }

    // A member, not a local: a pending write's block may read it later
    this->snax_csr_data = is_write ? (uint32_t)value : 0;
    vp::IoReq *req = &this->snax_csr_req;
    req->init();
    req->set_addr(address * 4);
    req->set_size(4);
    req->set_is_write(is_write);
    req->set_data((uint8_t *)&this->snax_csr_data);

    int err = this->snax_csr_itf.req(req);
    if (err == vp::IO_REQ_INVALID)
    {
        this->csr.trace.fatal("SNAX CSR access refused by the block (id: 0x%x, is_write: %d); "
            "see its trace\n", address, is_write);
        return false;
    }
    if (err == vp::IO_REQ_PENDING && is_write)
    {
        this->csr.trace.msg(vp::Trace::LEVEL_TRACE, "SNAX CSR write held by the block (id: 0x%x), "
            "core stalled\n", address);
        this->exec.insn_stall();
        return true;
    }
    if (err != vp::IO_REQ_OK)
    {
        this->csr.trace.fatal("SNAX CSR access not answered at once (id: 0x%x, is_write: %d, "
            "status: %d); pending reads and denied answers are not supported\n",
            address, is_write, err);
        return false;
    }

    if (!is_write)
    {
        value = this->snax_csr_data;
    }
    if (req->get_latency() > 0)
    {
        this->timing.stall_cycles_account(req->get_latency());
    }
    return true;
}


// The response to a held SNAX CSR write: the core goes on, as after a pending store
void Iss::snax_csr_response(vp::Block *__this, vp::IoReq *req)
{
    Iss *_this = (Iss *)__this;
    if (req->status == vp::IO_REQ_INVALID)
    {
        _this->csr.trace.fatal("Held SNAX CSR write refused by the block (addr: 0x%lx); "
            "see its trace\n", req->get_addr());
        return;
    }
    _this->csr.trace.msg(vp::Trace::LEVEL_TRACE, "SNAX CSR write answered, core resumed\n");
    _this->exec.stalled_dec();
    _this->exec.insn_terminate();
}


// Callback of every SNAX CSR: csrrs, csrrc and their immediate forms read through here,
// and write through here when they set or clear bits; with rs1 = x0 or uimm = 0 they only
// read (priv.hpp). Zicsr, as snax_cluster since 9fbf35d (#657;
// snax_intf_translator.sv reads, then writes).
bool Iss::snax_csr_access(SnaxCsr *csr, bool is_write, iss_reg_t &value)
{
    this->snax_csr_request(csr->address, is_write, value);
    // false: the value lives behind the port, not in the CSR object
    return false;
}


// csrrw and csrrwi on a SNAX CSR: one write request, after a read only when rd is not x0
// (a csrw sends no read, as in the RISC-V spec). The decoder gives rd = x0 the index
// ISS_NB_REGS, a register nothing reads, not 0. Zicsr, as snax_cluster since 9fbf35d
// (#657; snitch.sv, snax_intf_translator.sv).
iss_reg_t SnaxCsr::handle(Iss *iss, iss_insn_t *insn, iss_reg_t pc, iss_reg_t reg_value)
{
    if (insn->out_regs[0] != ISS_NB_REGS)
    {
        iss_reg_t value = 0;
        if (iss->snax_csr_request(this->address, false, value))
        {
            iss->regfile.memcheck_set_valid(insn->out_regs[0], true);
            iss->regfile.set_reg(insn->out_regs[0], value);
        }
    }

    iss->snax_csr_request(this->address, true, reg_value);

    return iss_insn_next(iss, insn, pc);
}


// This gets called when the barrier is reached
void Iss::barrier_sync(vp::Block *__this, bool value)
{
    Iss *_this = (Iss *)__this;

    // Clear the flag
    _this->waiting_barrier = false;

    // In case the barrier is reached as soon as we notify it, we are not yet stalled
    // and should not to anything
    if (_this->exec.is_stalled())
    {
        // Otherwise unstall the core
        _this->exec.stalled_dec();
        _this->exec.insn_terminate();
    }
}


// -----------USE MASTER AND SLAVE PORT TO HANDLE OFFLOAD REQUEST------------------
// Check whether the subsystem is busy or idle.
bool Iss::check_state(iss_insn_t *insn)
{
    // Hierarchical instruction scoreboard,
    // only stall the current floating point instruction if the previous one is waiting for offloading.
    // 1. fp instruction: get successful handshaking and continue.
    // 2. int instruction: continue without check, except data dependency, some int operands depend on previous fp result.
    // And also int instruction will be stalled if previous fp is still waiting to be offloaded.

    this->check_req.init();

    // Set the request is_write bit to differentiate whether it's a sequenceable instruction.
    // This is important because the handshaking methods and instruction lanes in the sequencer are different.
    if (insn->desc->tags[ISA_TAG_NSEQ_ID])
    {
        // Instructions in bypass lane
        this->check_req.set_is_write(false);
    }
    else
    {
        // Sequencable instructions
        this->check_req.set_is_write(true);
    }

    int idle = this->acc_req_ready_itf.req(&this->check_req);

    if (idle == vp::IO_REQ_OK)
    {
        return true;
    }
    else if (idle == vp::IO_REQ_INVALID)
    {
        return false;
    }

    return false;
}


// This get called when there is floating-point instruction detected in decode stage.
// Maybe change output type from void to bool later if inserting scoreboard.
bool Iss::handle_req(iss_insn_t *insn, iss_reg_t pc, bool is_write)
{
    iss_opcode_t opcode = insn->opcode;
    this->trace_iss.msg("Send offload request (opcode: 0x%lx, pc: 0x%lx)\n", opcode, pc);

    // Assign arguments to request.
    this->insn = *((iss_insn_t *)insn);
    this->pc = pc;
    this->is_write=is_write;
    this->frm = this->csr.fcsr.frm;

    // Assign arguments to request.
    this->acc_req = { .pc=pc, .insn=this->insn, .is_write=is_write, .frm =frm, .fmode=this->csr_fmode.value };

    // Offload request if the port is connected
    if (this->acc_req_itf.is_bound())
    {
        this->acc_req_itf.sync(&this->acc_req);
    }
    // Todo: Increment the latency going through i_spill_register_acc_demux_req.

    // If the output register of fp instruction is integer type, set timestamp of scoreboard at integer regfile in integer core.
    // And the following instruction with data dependency will execute scoreboard_reg_check when loading the operands,
    // which will call stall_load_dependency_account.
    // Assign timestamp as the lower bound of latency, which will be updated to the exact value after the instruction is executed.
    if (!this->insn.out_regs_fp[0] & this->insn.out_regs[0] != 0xFF)
    {
    #if defined(CONFIG_GVSOC_ISS_SCOREBOARD)
        this->regfile.scoreboard_reg_set_timestamp(insn->out_regs[0], insn->latency, -1);
    #endif
    }

    return false;
}


// This gets called when the offloaded instruction go through spill register.
void Iss::handle_event(vp::Block *__this, vp::ClockEvent *event)
{
    Iss *_this = (Iss *)__this;

    // Assign arguments to request.
    _this->acc_req = { .pc=_this->pc, .insn=_this->insn, .is_write=_this->is_write, .frm =_this->frm, .fmode=_this->csr_fmode.value };

    // Offload request if the port is connected
    if (_this->acc_req_itf.is_bound())
    {
        _this->acc_req_itf.sync(&_this->acc_req);
    }
}


// This get called when it receives result from subsystem.
void Iss::handle_result(vp::Block *__this, OffloadRsp *result)
{
    Iss *_this = (Iss *)__this;

    // Store dependent input integer register value when we receive the response from fp subsystem.
    if (!result->insn.out_regs_fp[0] & result->insn.out_regs[0] != 0xFF)
    {
        _this->regfile.set_reg(result->rd, result->data);
    }

    // Set scoreboard valid when the instruction finishes execution.
    if (!result->insn.out_regs_fp[0] && result->insn.out_regs[0] != 0xFF)
    {
        #if defined(CONFIG_GVSOC_ISS_SCOREBOARD)
        _this->regfile.scoreboard_reg_valid[result->insn.out_regs[0]] = true;
        #endif
    }
    // Reset memory address when the instruction finishes execution.
    bool lsu_label = strstr(result->insn.decoder_item->u.insn.label, "flw")
                    || strstr(result->insn.decoder_item->u.insn.label, "fsw")
                    || strstr(result->insn.decoder_item->u.insn.label, "fld")
                    || strstr(result->insn.decoder_item->u.insn.label, "fsd");
    if (lsu_label & result->pc==_this->mem_pc)
    {
        _this->mem_map = 0x0;
    }

    // Post-processing of result.
    // Update fflags in integer core after fp instruction.
    // Hardward doesn't stall CSR_FFLAGS when the fp instruction hasn't responded correct status value.
    _this->csr.fcsr.fflags = result->fflags;

    // for (int i=0; i<3; i++)
    // {
    //     if (result->insn.out_regs_fp[0])
    //     {
    //         int reg = result->insn.out_regs[i];
    //         _this->regfile.set_freg(reg, *((iss_freg_t *)(result->insn.freg_addr)+reg));
    //     }
    // }

    // Pass values of floating point registers from subsystem to core side.
    // Assign results here because we use fp register value only for trace, not for later computation.
    for (int i=0; i<ISS_NB_REGS; i++)
    {
        _this->regfile.set_freg(i, *((iss_freg_t *)(result->insn.freg_addr)+i));
    }

    // Output instruction trace for debugging.
    _this->trace_iss.msg("Get accelerator response (opcode: 0x%lx, pc: 0x%lx)\n", result->insn.opcode, result->pc);

}


bool Iss::ssr_access(bool is_write, iss_reg_t &value)
{
    if (is_write)
    {
        iss_reg_t index;
        iss_reg_t pc = this->exec.current_insn;
        iss_insn_t *insn = this->insn_cache.get_insn(pc, index);

        // Instruction to set ssr register at 0x7C0 (enable/disable SSR): csrrsi ssr, value;
        // csr_ssr needs to be offloaded to subsystem

        // Send an IO request to check whether the subsystem is ready for offloading.
        bool acc_req_ready = this->check_state(insn);
        this->exec.trace.msg(vp::Trace::LEVEL_TRACE, "Integer side receives acceleration request handshaking signal: %d\n", acc_req_ready);

        // If not ready, stay at current PC and fetch the same instruction next cycle.
        if (!acc_req_ready)
        {
            this->exec.trace.msg("Stall at current instruction\n");

            this->exec.insn_hold(&Iss::handle_wait_acc_ready);
        }
        else
        {
            // If ready, send offload request.
            insn->reg_addr = &this->regfile.regs[0];
            #ifdef CONFIG_GVSOC_ISS_SCOREBOARD
            insn->scoreboard_reg_timestamp_addr = &this->regfile.scoreboard_reg_timestamp[0];
            #endif
            int stall = this->handle_req(insn, pc, false);
        }
    }

    return false;
}

void Iss::handle_wait_acc_ready(vp::Block *__this, vp::ClockEvent *event)
{
    Iss *_this = (Iss *)__this;
    iss_reg_t index;
    iss_reg_t pc = _this->exec.stall_insn;
    iss_insn_t *insn = _this->insn_cache.get_insn(pc, index);
    if (_this->check_state(insn))
    {
        _this->trace.dump_trace_enabled = true;
        _this->exec.current_insn = _this->exec.stall_insn;
        _this->exec.insn_resume();
    }
}
