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


#pragma once


#include <vp/vp.hpp>
#include <vp/register.hpp>
#include <cpu/iss/include/lsu.hpp>
#include <cpu/iss/include/decode.hpp>
#include <cpu/iss/include/trace.hpp>
#include <cpu/iss/include/csr.hpp>
#include <cpu/iss/include/dbgunit.hpp>
#include <cpu/iss/include/exception.hpp>
#include <cpu/iss/include/syscalls.hpp>
#include <cpu/iss/include/timing.hpp>
#include <cpu/iss/include/cores/snitch/regfile.hpp>
#ifdef CONFIG_GVSOC_ISS_RISCV_EXCEPTIONS
#include <cpu/iss/include/irq/irq_riscv.hpp>
#else
#include <cpu/iss/include/irq/irq_external.hpp>
#endif
#include <cpu/iss/include/core.hpp>
#include <cpu/iss/include/memcheck.hpp>
#include <cpu/iss/include/insn_cache.hpp>
#include <cpu/iss/include/exec/exec_inorder.hpp>
#include <cpu/iss/include/prefetch/prefetch_single_line.hpp>
#include <cpu/iss/include/gdbserver.hpp>

#if defined(CONFIG_GVSOC_ISS_SPATZ)
#include <cpu/iss/include/spatz.hpp>
#endif

#include <cpu/iss/include/types.hpp>

#include "OffloadReq.hpp"
#include "OffloadRsp.hpp"
#include "PipeRegs.hpp"
#include <cpu/iss/include/cores/snitch/ssr.hpp>

class IssWrapper;


// snax_cluster's accelerator CSRs (hw/snitch/src/csr_snax_def.sv): the core sends
// every CSR instruction in this range out on its accelerator port.
static const iss_reg_t SNAX_CSR_FIRST = 0x3C0;
static const iss_reg_t SNAX_CSR_LAST = 0x5FF;
static const int SNAX_CSR_NB = SNAX_CSR_LAST - SNAX_CSR_FIRST + 1;

// One SNAX CSR. Its accesses go out as IO requests on the core's snax_csr port, at
// byte address 4 * CSR number. csrrw and csrrwi come through handle(), the other CSR
// instructions through the callback the core registers (Iss::snax_csr_access).
class SnaxCsr : public CsrAbtractReg
{
public:
    SnaxCsr() : CsrAbtractReg(&this->value) {}
    iss_reg_t handle(Iss *iss, iss_insn_t *insn, iss_reg_t pc, iss_reg_t reg_value) override;

    iss_reg_t address = 0;
    // Storage the base class needs; SNAX CSRs keep their value in the block behind the port.
    iss_reg_t value = 0;
};


class Iss
{
public:
    Iss(IssWrapper &top);

    Exec exec;
    InsnCache insn_cache;
    Timing timing;
    Core core;
    SnitchRegfile regfile;
    Prefetcher prefetcher;
    Decode decode;
    Irq irq;
    Gdbserver gdbserver;
    Lsu lsu;
    DbgUnit dbgunit;
    Syscalls syscalls;
    Trace trace;
    Csr csr;
    Exception exception;
    Memcheck memcheck;

    IssWrapper &top;

#if defined(CONFIG_GVSOC_ISS_SPATZ)
    Spatz spatz;
#endif

    Ssr ssr;

    bool snitch;
    bool fp_ss;


    // -----------USE MASTER AND SLAVE PORT TO HANDLE OFFLOAD REQUEST------------------

    // Handshaking interface, added to check subsystem state, busy or idle
    vp::IoMaster acc_req_ready_itf;

    // Offload request interface
    vp::WireMaster<OffloadReq *> acc_req_itf;
    // Response interface, receive result from subsystem
    vp::WireSlave<OffloadRsp *> acc_rsp_itf;
    vp::ClockEvent *event;
    // Offload request and response
    OffloadReq acc_req;
    OffloadRsp acc_rsp;

    // Handshaking signals and functions
    bool acc_req_ready;
    vp::IoReq check_req;
    bool check_state(iss_insn_t *insn);

    // Request and Response interfaces and events
    static void handle_event(vp::Block *__this, vp::ClockEvent *event);
    bool handle_req(iss_insn_t *insn, iss_reg_t pc, bool is_write);
    static void handle_result(vp::Block *__this, OffloadRsp *result);

    // Temporary request information
    iss_insn_t insn;
    iss_reg_t pc;
    bool is_write;
    unsigned int frm;
    // SNAX CSRs: one object per CSR number, the port and the one request they share.
    // Returns false when the port is not bound (the CSR is then unsupported, as before).
    bool snax_csr_request(iss_reg_t address, bool is_write, iss_reg_t &value);
    SnaxCsr snax_csrs[SNAX_CSR_NB];
    vp::IoMaster snax_csr_itf;
    vp::IoReq snax_csr_req;
    // The two forms where SNAX-GVSoC (Zicsr, D120) and snax_cluster's RTL differ are
    // warned about once per run each (snitch.cpp)
    bool snax_csr_rw_rd_warned = false;
    bool snax_csr_set_clear_warned = false;

    // Temporary variable to process RAW caused by SSR and accessing stack pointer,
    // for result is written to memory directly.
    iss_addr_t mem_map;
    iss_reg_t mem_pc;
    CsrReg csr_fmode;

private:
    bool barrier_update(bool is_write, iss_reg_t &value);
    static void barrier_sync(vp::Block *__this, bool value);
    bool ssr_access(bool is_write, iss_reg_t &value);
    bool snax_csr_access(SnaxCsr *csr, bool is_write, iss_reg_t &value);
    static void handle_wait_acc_ready(vp::Block *__this, vp::ClockEvent *event);

    vp::WireMaster<bool> barrier_req_itf;
    vp::WireSlave<bool> barrier_ack_itf;
    CsrReg barrier;
    bool waiting_barrier;

    vp::Trace trace_iss;
    CsrReg csr_ssr;

    // snax_cluster's cluster CSRs 0xBC1 to 0xBC3 (hw/snitch/src/snitch_pkg.sv)
    CsrReg snax_base_addr_l;
    CsrReg snax_base_addr_h;
    CsrReg snax_cluster_core_id;
};


class IssWrapper : public vp::Component
{

public:
    IssWrapper(vp::ComponentConf &config);

    void start();
    void reset(bool active);
    void stop();

    Iss iss;

private:
    vp::Trace trace;
};

static inline iss_reg_t fmode_get(Iss *iss, iss_insn_t *insn)
{
    return insn->fmode;
}


#include "cpu/iss/include/isa/rv64i.hpp"
#include "cpu/iss/include/isa/rv32i.hpp"
#if defined(CONFIG_GVSOC_ISS_SPATZ)
#include "cpu/iss/include/isa/rv32v.hpp"
#endif
#include "cpu/iss/include/isa/rv32c.hpp"
#include "cpu/iss/include/isa/zcmp.hpp"
#include "cpu/iss/include/isa/rv32a.hpp"

#if ISS_REG_WIDTH == 64
#include "cpu/iss/include/isa/rv64c.hpp"
#endif
#include "cpu/iss/include/isa/rv32m.hpp"
#include "cpu/iss/include/isa/rv64m.hpp"
#include "cpu/iss/include/isa/rv64a.hpp"
#include "cpu/iss/include/isa/rvd.hpp"
#include "cpu/iss/include/isa/rvf.hpp"
#include "cpu/iss/include/isa/rvXf16.hpp"
#include "cpu/iss/include/isa/rvXf16alt.hpp"
#include "cpu/iss/include/isa/rvXf16_switch.hpp"
#include "cpu/iss/include/isa/rvXf8.hpp"
#include "cpu/iss/include/isa/rvXf8alt.hpp"
#include "cpu/iss/include/isa/rvXf8_switch.hpp"
#include "cpu/iss/include/isa/rv32Xfvec.hpp"
#include "cpu/iss/include/isa/rv32Xfaux.hpp"
#include "cpu/iss/include/isa/priv.hpp"
#ifdef CONFIG_GVSOC_ISS_SNITCH_PULP_V2
#include "cpu/iss/include/isa/pulp_v2.hpp"
#else
#include <cpu/iss/include/isa/xdma.hpp>
#include "cpu/iss/include/isa/rv32frep.hpp"
#include "cpu/iss/include/isa/rv32ssr.hpp"
#endif

#include <cpu/iss/include/cores/snitch/regfile_implem.hpp>
#include <cpu/iss/include/exec/exec_inorder_implem.hpp>
