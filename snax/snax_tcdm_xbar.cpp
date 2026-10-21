/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// The SNAX accelerators' ports into the TCDM banks, arbitrated per bank as one
// of snax_cluster's two interconnects does, chosen by the property
// interconnect:
//   plain   snitch_tcdm_interconnect.sv (sparse_interconnect false): one
//           stream_xbar, one rr_arb_tree per bank (FairArb, LockIn, no
//           external priority: the priority bit is ignored), a winner
//           refused by its bank locked in (snax_plain_arb.hpp). common_cells
//           v1.40.0, src/rr_arb_tree.sv and src/stream_xbar.sv.
//   sparse  the Chisel SparseInterconnect (sparse_interconnect true): per
//           bank the highest priority first, then round robin from the last
//           pick, restarting after a cycle with no request, and a winner
//           refused by its bank keeps its turn (snax_sparse_arb.hpp). The
//           property sparse_config lists its ports [width, granularity]; an
//           input reaches only the banks its granularity allows, and a bank
//           orders its inputs as SparseConfig does.
// Read data comes one cycle after the grant in both.
//
// A master sends a request of 1, 2, 4 or 8 bytes inside one bank word on its
// input; the crossbar takes it (IO_REQ_PENDING) and arbitrates once per
// cycle, in an event queued for the cycle of the first request. Each bank
// grants one input: its bank access happens then and the master gets grant().
// Read data, an AMO's or an LR/SC's, comes with resp() one cycle later, plus
// the latency the request carries and any the bank adds (a DMA access to the
// same bank in that cycle).
//
// An input that loses does as its master on the RTL (property holds):
//   resends  (SNAX ports) dropped; the master sends it again the next cycle,
//            and a write gets resp() one cycle after its grant.
//   holds    (cores, AXI) kept, and in the next cycle's arbitration; a write
//            gets resp() at its grant, as a core waits for a store's grant
//            only.
//
// The priority bit of a request comes on the wire prio_<i>, set by its master
// just before it sends the request (and before each resend), and holds for
// that cycle only (a held request keeps it). A master that does not set it, as
// a core reaching the crossbar through routers, asks with priority 0; the wire
// keeps the bit out of the request's argument slots, which routers use.
//
// Inputs are numbered as on the RTL: the SNAX ports, the cores, AXI.
//
// The DMA (property superbank_banks, port dma) is not one of them: as on the
// RTL (mem_wide_narrow_mux), a DMA beat takes every bank of its superbank in
// its cycle and is answered at once, never refused, and a narrow winner on
// those banks is refused by the bank and locked by its interconnect's rule
// (bank_refuses()). A beat is a request inside one aligned superbank line; one
// that crosses a line is refused. The DMA's beat of a cycle comes before that
// cycle's arbitration, which runs after every event queued before the cycle
// (docs/plans/SG7.md); one that comes after it on a superbank already
// granted to a narrow request is fatal.
//
// Counters (docs/EVENTS.md, snax_events.hpp), over the whole simulation and
// written by stop() as summary lines: per input its grants, its stalls (cycles
// it requested and was not granted) and the part of them on a bank the DMA's
// superbank took; per bank its reads and writes (a SNAX input's grant, or a
// word of a DMA beat) and its conflicts (cycles with two or more of those
// requests on it). The banks count the SNAX inputs and the DMA only: the
// inputs that hold (the cores, AXI) have their own lines, marked whole_run,
// since their traffic starts at boot.
//
// Beat and stall lines (docs/EVENTS.md), for the inputs the property
// trace_inputs names: a grant line per grant, with the word the bank access
// read or wrote and the cycle its response comes; a stall line per input and
// cycle refused, with the input the bank granted (-1: the DMA's superbank);
// a dma line per DMA beat, with one word per bank it covers. A streamer's
// request carries its beat's b, a DMA beat its copy's id, its index and its
// other side's address, in the argument slots snax_events.hpp names.
// trace_inputs is a list joined by ',' of input names (input_names) or
// indices and dma; default (its default) is every input that resends (the
// SNAX ports) and dma.
//
// VCD signals (snax_events.hpp, gtkwave only): per input in<i>_q_valid (it
// requests), in<i>_q_ready (it is granted) and in<i>_stall (it is refused),
// the RTL's TCDM handshake names; per bank bank<b>_grant, the input it granted
// plus one (0 none, nb_inputs + 1 the DMA's beat).

#include <algorithm>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include "snax_events.hpp"
#include "snax_plain_arb.hpp"
#include "snax_sparse_arb.hpp"


// A granted request waiting for its response
struct Response
{
    int64_t cycle;              // the cycle it is due
    vp::IoReq *req;
    int input;
};


class SnaxTcdmXbar : public vp::Component
{
public:
    SnaxTcdmXbar(vp::ComponentConf &config);

private:
    static vp::IoReqStatus req(vp::Block *__this, vp::IoReq *req, int id);
    static vp::IoReqStatus dma_req(vp::Block *__this, vp::IoReq *req);
    static void priority_sync(vp::Block *__this, bool value, int id);
    static void arbitrate(vp::Block *__this, vp::ClockEvent *event);
    static void held_cycle(vp::Block *__this, vp::ClockEvent *event);
    static void respond(vp::Block *__this, vp::ClockEvent *event);
    void answer(vp::IoReq *req, int input);
    void reset(bool active) override;
    void stop() override;

    // The sparse interconnect's winner on bank among the inputs in req_mask
    int sparse_pick(int bank, uint64_t req_mask, int64_t cycle);
    // Whether bank refuses this cycle's winner: the DMA took its superbank
    bool bank_refuses(int bank)
    {
        return this->superbank_banks > 0
            && this->superbank_cycle[bank / this->superbank_banks] == this->clock.get_cycles();
    }
    // The inputs requesting in req_mask but winner, for the trace
    std::string others(uint64_t req_mask, int winner);
    // An input's name for the trace; sparse, one asking with priority 1 is
    // marked with !
    std::string name(int input);
    // The inputs and the DMA the beat and stall lines are written for
    void trace_inputs_from(std::string value);
    // A request's b, as a field of its line, when its master set one
    std::string beat_field(vp::IoReq *req);

    vp::Trace trace;
    SnaxEvents ev;
    std::vector<vp::IoSlave> inputs;
    std::vector<vp::WireSlave<bool>> priority_itf;
    std::vector<vp::IoMaster> banks;
    vp::IoSlave dma;
    vp::ClockEvent arb_event;
    // Queues the arbitration of a cycle that starts with a held request
    vp::ClockEvent held_event;
    vp::ClockEvent resp_event;
    // The cycle of the last arbitration
    int64_t arb_cycle = -1;

    int nb_inputs;
    int nb_banks;
    int bank_bits;         // log2(nb_banks)
    int width_bits;        // log2 of the bank width in bytes
    bool sparse;           // the sparse interconnect, else the plain one
    int superbank_banks;   // banks per DMA beat, 0 without a DMA port

    // Per input: whether it holds a losing request (else its master resends it)
    std::vector<bool> holds;
    // Per input: the request sent in this cycle or held, NULL if none
    std::vector<vp::IoReq *> pending;
    // Per input: its bank, decoded when the request arrives
    std::vector<int> pending_bank;
    // Plain: per bank its arbitration tree
    std::vector<SnaxPlainArb> plain_arbs;
    // Per bank: the inputs requesting it in this cycle, one bit each
    std::vector<uint64_t> bank_req;
    // Per input: its owner's name for the trace, in_<i> when none is given
    std::vector<std::string> names;
    // Per input: the priority bit of its request in this cycle (sparse only)
    std::vector<bool> priority;

    // Sparse: the ports, and per bank its arbiter and its inputs in local order
    SnaxSparseConfig sparse_config;
    std::vector<SnaxSparseArb> sparse_arbs;
    std::vector<std::vector<int>> bank_inputs;

    // Granted requests waiting for their response, in grant order
    std::vector<Response> responses;

    // Per superbank: the cycle the DMA last took it, and the address of that beat
    std::vector<int64_t> superbank_cycle;
    std::vector<uint64_t> superbank_addr;

    // Per input: whether its beat and stall lines are written; the DMA's
    std::vector<bool> trace_input;
    bool trace_dma;

    SnaxSignals sigs;
    std::vector<std::unique_ptr<SnaxSignal>> sig_valid, sig_ready, sig_stall;  // per input
    std::vector<std::unique_ptr<SnaxSignal>> sig_bank;                         // per bank
    // bank's signal: value in this cycle only
    void bank_signal(int bank, uint64_t value)
    {
        this->sigs.set(*this->sig_bank[bank], value);
        this->sigs.set_from(*this->sig_bank[bank], 0, this->clock.get_cycles() + 1);
    }
    // Per bank: the cycle of its last narrow grant, and to whom
    std::vector<int64_t> grant_cycle;
    std::vector<int> grant_input;

    // The counters: per input, per bank
    std::vector<int64_t> input_grants;
    std::vector<int64_t> input_stalls;
    std::vector<int64_t> input_stalls_dma;
    std::vector<int64_t> bank_reads;
    std::vector<int64_t> bank_writes;
    std::vector<int64_t> bank_conflicts;
};


SnaxTcdmXbar::SnaxTcdmXbar(vp::ComponentConf &config)
    : vp::Component(config),
      arb_event(this, &SnaxTcdmXbar::arbitrate),
      held_event(this, &SnaxTcdmXbar::held_cycle),
      resp_event(this, &SnaxTcdmXbar::respond),
      sigs(this)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->ev.declare(this);

    this->nb_inputs = this->get_js_config()->get_child_int("nb_inputs");
    this->nb_banks = this->get_js_config()->get_child_int("nb_banks");
    int bank_width = this->get_js_config()->get_child_int("bank_width");

    vp_assert_always(this->nb_inputs > 0 && this->nb_inputs <= 64, &this->trace,
        "nb_inputs must be in (0, 64], got %d\n", this->nb_inputs);

    this->bank_bits = __builtin_ctz(this->nb_banks);
    std::string interconnect = this->get_js_config()->get_child_str("interconnect");
    vp_assert_always(interconnect == "plain" || interconnect == "sparse", &this->trace,
        "interconnect must be plain or sparse, got %s\n", interconnect.c_str());
    this->sparse = interconnect == "sparse";
    this->width_bits = __builtin_ctz(bank_width);
    js::Config *superbank = this->get_js_config()->get("superbank_banks");
    this->superbank_banks = superbank != NULL ? superbank->get_int() : 0;
    vp_assert_always(this->superbank_banks >= 0 && (this->superbank_banks == 0
        || this->nb_banks % this->superbank_banks == 0), &this->trace,
        "superbank_banks must divide nb_banks, got %d\n", this->superbank_banks);

    js::Config *names = this->get_js_config()->get("input_names");
    std::vector<js::Config *> given;
    if (names != NULL)
    {
        given = names->get_elems();
    }
    for (int i = 0; i < this->nb_inputs; i++)
    {
        this->names.push_back(i < (int)given.size() ? given[i]->get_str()
            : "in_" + std::to_string(i));
    }

    js::Config *holds = this->get_js_config()->get("holds");
    std::vector<js::Config *> holding;
    if (holds != NULL)
    {
        holding = holds->get_elems();
    }
    for (int i = 0; i < this->nb_inputs; i++)
    {
        this->holds.push_back(i < (int)holding.size() && holding[i]->get_bool());
    }

    // Sized once, before any port is registered: never resized after
    this->inputs.resize(this->nb_inputs);
    this->priority_itf.resize(this->nb_inputs);
    this->banks.resize(this->nb_banks);
    this->pending.assign(this->nb_inputs, NULL);
    this->pending_bank.assign(this->nb_inputs, 0);
    this->bank_req.assign(this->nb_banks, 0);
    this->priority.assign(this->nb_inputs, false);
    this->grant_cycle.assign(this->nb_banks, -1);
    this->grant_input.assign(this->nb_banks, 0);
    if (this->superbank_banks > 0)
    {
        this->superbank_cycle.assign(this->nb_banks / this->superbank_banks, -1);
        this->superbank_addr.assign(this->nb_banks / this->superbank_banks, 0);
    }
    js::Config *trace_inputs = this->get_js_config()->get("trace_inputs");
    this->trace_inputs_from(trace_inputs != NULL ? trace_inputs->get_str() : "default");

    if (this->sparse)
    {
        std::vector<SnaxSparsePort> ports;
        for (js::Config *port : this->get_js_config()->get("sparse_config")->get_elems())
        {
            std::vector<js::Config *> pair = port->get_elems();
            ports.push_back({(int)pair[0]->get_int(), (int)pair[1]->get_int()});
        }
        this->sparse_config = SnaxSparseConfig(ports, this->nb_banks);
        vp_assert_always(this->sparse_config.nb_inputs() == this->nb_inputs, &this->trace,
            "sparse_config has %d inputs, the crossbar %d\n",
            this->sparse_config.nb_inputs(), this->nb_inputs);
        for (int bank = 0; bank < this->nb_banks; bank++)
        {
            this->bank_inputs.push_back(this->sparse_config.bank_inputs(bank));
            this->sparse_arbs.push_back(SnaxSparseArb(this->sparse_config.inputs_per_bank()));
        }
    }
    else
    {
        this->plain_arbs.assign(this->nb_banks, SnaxPlainArb(this->nb_inputs));
    }

    for (int i = 0; i < this->nb_inputs; i++)
    {
        this->inputs[i].set_req_meth_muxed(&SnaxTcdmXbar::req, i);
        this->new_slave_port("in_" + std::to_string(i), &this->inputs[i]);
        this->priority_itf[i].set_sync_meth_muxed(&SnaxTcdmXbar::priority_sync, i);
        this->new_slave_port("prio_" + std::to_string(i), &this->priority_itf[i]);
    }
    for (int i = 0; i < this->nb_banks; i++)
    {
        this->new_master_port("out_" + std::to_string(i), &this->banks[i]);
        this->sig_bank.emplace_back(new SnaxSignal(*this, "bank" + std::to_string(i) + "_grant",
            8));
    }
    for (int i = 0; i < this->nb_inputs; i++)
    {
        std::string in = "in" + std::to_string(i);
        this->sig_valid.emplace_back(new SnaxSignal(*this, in + "_q_valid", 1));
        this->sig_ready.emplace_back(new SnaxSignal(*this, in + "_q_ready", 1));
        this->sig_stall.emplace_back(new SnaxSignal(*this, in + "_stall", 1));
    }
    if (this->superbank_banks > 0)
    {
        this->dma.set_req_meth(&SnaxTcdmXbar::dma_req);
        this->new_slave_port("dma", &this->dma);
    }
}


void SnaxTcdmXbar::reset(bool active)
{
    if (active)
    {
        this->pending.assign(this->nb_inputs, NULL);
        for (SnaxPlainArb &arb : this->plain_arbs)
        {
            arb.reset();
        }
        this->priority.assign(this->nb_inputs, false);
        this->arb_cycle = -1;
        for (SnaxSparseArb &arb : this->sparse_arbs)
        {
            arb.reset();
        }
        this->responses.clear();
        std::fill(this->superbank_cycle.begin(), this->superbank_cycle.end(), -1);
        std::fill(this->grant_cycle.begin(), this->grant_cycle.end(), -1);
        this->input_grants.assign(this->nb_inputs, 0);
        this->input_stalls.assign(this->nb_inputs, 0);
        this->input_stalls_dma.assign(this->nb_inputs, 0);
        this->bank_reads.assign(this->nb_banks, 0);
        this->bank_writes.assign(this->nb_banks, 0);
        this->bank_conflicts.assign(this->nb_banks, 0);
    }
}


// The counters, as summary lines (docs/EVENTS.md)
void SnaxTcdmXbar::stop()
{
    long cycle = (long)this->clock.get_cycles();
    for (int i = 0; i < this->nb_inputs; i++)
    {
        this->ev.summary.msg(vp::Trace::LEVEL_INFO,
            "%ld input index=%d name=%s grants=%ld stalls=%ld stalls_dma=%ld whole_run=%d\n",
            cycle, i, this->names[i].c_str(), (long)this->input_grants[i],
            (long)this->input_stalls[i], (long)this->input_stalls_dma[i], (int)this->holds[i]);
    }
    for (int bank = 0; bank < this->nb_banks; bank++)
    {
        this->ev.summary.msg(vp::Trace::LEVEL_INFO,
            "%ld bank index=%d reads=%ld writes=%ld conflicts=%ld\n", cycle, bank,
            (long)this->bank_reads[bank], (long)this->bank_writes[bank],
            (long)this->bank_conflicts[bank]);
    }
}


vp::IoReqStatus SnaxTcdmXbar::req(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;

    uint64_t addr = req->get_addr();
    uint64_t size = req->get_size();
    uint64_t width = 1ULL << _this->width_bits;
    if ((size != 1 && size != 2 && size != 4 && size != 8) || size > width)
    {
        _this->trace.force_warning("Unexpected access on %s (addr: 0x%lx, size: %ld)\n",
            _this->names[id].c_str(), addr, size);
        return vp::IO_REQ_INVALID;
    }
    if ((addr & (width - 1)) + size > width)
    {
        _this->trace.force_warning("%s crosses a bank word (addr: 0x%lx, size: %ld); refused\n",
            _this->names[id].c_str(), addr, size);
        return vp::IO_REQ_INVALID;
    }
    if (_this->pending[id] != NULL && _this->pending[id] != req)
    {
        _this->trace.force_warning("Two requests on %s in one cycle\n",
            _this->names[id].c_str());
        return vp::IO_REQ_INVALID;
    }
    if (_this->arb_cycle == _this->clock.get_cycles())
    {
        // It would be arbitrated twice in one cycle
        _this->trace.fatal("Request on %s after this cycle's arbitration\n",
            _this->names[id].c_str());
        return vp::IO_REQ_INVALID;
    }

    int bank = (addr >> _this->width_bits) & (_this->nb_banks - 1);
    if (_this->sparse && !_this->sparse_config.reaches(id, bank))
    {
        // The RTL asserts on it
        _this->trace.force_warning("%s may not reach bank %d (its granularity); refused\n",
            _this->names[id].c_str(), bank);
        return vp::IO_REQ_INVALID;
    }

    _this->pending[id] = req;
    _this->pending_bank[id] = bank;

    // Arbitrate once in this cycle, after every master has sent its requests:
    // the event goes after the events already queued for this cycle.
    if (!_this->arb_event.is_enqueued())
    {
        _this->arb_event.enqueue(0);
    }
    return vp::IO_REQ_PENDING;
}


void SnaxTcdmXbar::priority_sync(vp::Block *__this, bool value, int id)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;
    _this->priority[id] = value;
}


// A DMA beat: its superbank is taken in this cycle, its bank words accessed
// at once
vp::IoReqStatus SnaxTcdmXbar::dma_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;
    int64_t cycle = _this->clock.get_cycles();
    uint64_t addr = req->get_addr();
    uint64_t size = req->get_size();
    uint64_t line = (uint64_t)_this->superbank_banks << _this->width_bits;
    if (size == 0 || (addr & ~(line - 1)) != ((addr + size - 1) & ~(line - 1)))
    {
        _this->trace.force_warning("DMA request crosses a superbank line (addr: 0x%lx, "
            "size: %ld); refused\n", addr, size);
        return vp::IO_REQ_INVALID;
    }

    int first_bank = (addr >> _this->width_bits) & (_this->nb_banks - 1);
    int superbank = first_bank / _this->superbank_banks;
    if (_this->arb_cycle == cycle)
    {
        for (int bank = superbank * _this->superbank_banks;
            bank < (superbank + 1) * _this->superbank_banks; bank++)
        {
            if (_this->grant_cycle[bank] == cycle)
            {
                _this->trace.fatal("DMA beat on superbank %d after this cycle's arbitration "
                    "granted bank %d to %s\n", superbank, bank,
                    _this->names[_this->grant_input[bank]].c_str());
                return vp::IO_REQ_INVALID;
            }
        }
    }
    _this->superbank_cycle[superbank] = cycle;
    _this->superbank_addr[superbank] = addr;
    for (int bank = superbank * _this->superbank_banks;
        bank < (superbank + 1) * _this->superbank_banks; bank++)
    {
        _this->bank_signal(bank, _this->nb_inputs + 1);
    }
    _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Superbank %d: grant dma (%s 0x%lx, %ld B)\n",
        superbank, req->get_is_write() ? "write" : "read", addr, size);

    // Each bank word it covers, as DmaInterleaver did: the largest bank
    // latency is the answer's
    uint64_t width = 1ULL << _this->width_bits;
    uint8_t *data = req->get_data();
    int64_t latency = 0;
    uint64_t beat_addr = addr, beat_size = size;
    std::string values;
    while (size > 0)
    {
        uint64_t chunk = std::min(width - (addr & (width - 1)), size);
        int bank = (addr >> _this->width_bits) & (_this->nb_banks - 1);
        vp::IoReq bank_req;
        bank_req.init();
        bank_req.set_addr(((addr >> (_this->width_bits + _this->bank_bits)) << _this->width_bits)
            | (addr & (width - 1)));
        bank_req.set_size(chunk);
        bank_req.set_data(data);
        bank_req.set_is_write(req->get_is_write());
        bank_req.set_opcode(req->get_opcode());
        (req->get_is_write() ? _this->bank_writes : _this->bank_reads)[bank]++;
        vp::IoReqStatus status = _this->banks[bank].req(&bank_req);
        if (status != vp::IO_REQ_OK)
        {
            _this->trace.fatal("Bank %d did not answer the DMA at once (status: %d)\n", bank,
                status);
            return vp::IO_REQ_INVALID;
        }
        latency = std::max(latency, (int64_t)bank_req.get_latency());
        values += (values.empty() ? "" : ",") + snax_word(data, chunk);
        addr += chunk;
        data += chunk;
        size -= chunk;
    }
    req->inc_latency(latency);

    if (_this->trace_dma && _this->ev.beats.get_active())
    {
        // A beat the iDMA's TCDM backend did not tag has no copy: -1
        bool tagged = snax_arg_get(req, SNAX_ARG_TAG) == SNAX_TAG_DMA;
        std::string back = req->get_is_write() ? ""
            : " back=" + std::to_string((long)(cycle + latency));
        _this->ev.beats.msg(vp::Trace::LEVEL_INFO,
            "%ld dma id=%ld i=%ld op=%s addr=0x%lx size=%ld bank=%d row=%ld value=%s l2=0x%lx%s\n",
            (long)cycle, tagged ? (long)snax_arg_get(req, SNAX_ARG_ID) : -1L,
            tagged ? (long)snax_arg_get(req, SNAX_ARG_INDEX) : -1L,
            req->get_is_write() ? "w" : "r", (unsigned long)beat_addr, (long)beat_size,
            first_bank, (long)(beat_addr >> (_this->width_bits + _this->bank_bits)),
            values.c_str(), tagged ? (unsigned long)snax_arg_get(req, SNAX_ARG_L2) : ~0UL,
            back.c_str());
    }
    return vp::IO_REQ_OK;
}


std::string SnaxTcdmXbar::name(int input)
{
    return this->names[input] + (this->sparse && this->priority[input] ? "!" : "");
}


void SnaxTcdmXbar::trace_inputs_from(std::string value)
{
    this->trace_input.assign(this->nb_inputs, false);
    this->trace_dma = false;
    std::stringstream tokens(value);
    std::string token;
    while (std::getline(tokens, token, ','))
    {
        if (token.empty())
        {
            continue;
        }
        if (token == "default")
        {
            for (int i = 0; i < this->nb_inputs; i++)
            {
                this->trace_input[i] = this->trace_input[i] || !this->holds[i];
            }
            this->trace_dma = true;
            continue;
        }
        if (token == "dma")
        {
            this->trace_dma = true;
            continue;
        }
        int input = -1;
        for (int i = 0; i < this->nb_inputs; i++)
        {
            if (this->names[i] == token || std::to_string(i) == token)
            {
                input = i;
            }
        }
        if (input == -1)
        {
            this->trace.fatal("Property trace_inputs: %s is not an input (input_names, an index "
                "or dma)\n", token.c_str());
            return;
        }
        this->trace_input[input] = true;
    }
}


std::string SnaxTcdmXbar::beat_field(vp::IoReq *req)
{
    if (snax_arg_get(req, SNAX_ARG_TAG) != SNAX_TAG_BEAT)
    {
        return "";
    }
    return " b=" + std::to_string((long)snax_arg_get(req, SNAX_ARG_ID));
}


std::string SnaxTcdmXbar::others(uint64_t req_mask, int winner)
{
    std::string held;
    for (int i = 0; i < this->nb_inputs; i++)
    {
        if (i != winner && ((req_mask >> i) & 1))
        {
            held += " " + this->name(i);
        }
    }
    return held.empty() ? "" : ", held:" + held;
}


int SnaxTcdmXbar::sparse_pick(int bank, uint64_t req_mask, int64_t cycle)
{
    std::vector<int> &inputs = this->bank_inputs[bank];
    uint64_t valid = 0, high = 0;
    for (size_t local = 0; local < inputs.size(); local++)
    {
        if ((req_mask >> inputs[local]) & 1)
        {
            valid |= 1ULL << local;
            if (this->priority[inputs[local]])
            {
                high |= 1ULL << local;
            }
        }
    }
    return inputs[this->sparse_arbs[bank].pick(cycle, valid, high)];
}


void SnaxTcdmXbar::arbitrate(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;
    int64_t cycle = _this->clock.get_cycles();
    _this->arb_cycle = cycle;

    // The requests of this cycle, per bank
    std::fill(_this->bank_req.begin(), _this->bank_req.end(), 0);
    for (int i = 0; i < _this->nb_inputs; i++)
    {
        if (_this->pending[i] != NULL)
        {
            _this->bank_req[_this->pending_bank[i]] |= 1ULL << i;
        }
    }

    for (int bank = 0; bank < _this->nb_banks; bank++)
    {
        uint64_t req_mask = _this->bank_req[bank];
        if (req_mask == 0)
        {
            continue;
        }

        int winner = _this->sparse ? _this->sparse_pick(bank, req_mask, cycle)
            : _this->plain_arbs[bank].pick(cycle, req_mask);
        bool refuses = _this->bank_refuses(bank);
        for (int i = 0; i < _this->nb_inputs; i++)
        {
            if ((req_mask >> i) & 1)
            {
                _this->sigs.pulse(*_this->sig_valid[i]);
                _this->sigs.pulse(*(i != winner || refuses ? _this->sig_stall : _this->sig_ready)[i]);
            }
        }
        if (!refuses)
        {
            _this->bank_signal(bank, winner + 1);
        }
        if (_this->ev.stalls.get_active())
        {
            // Every requester refused here: the losers, and the winner too when the
            // DMA's superbank took the bank
            int by = refuses ? -1 : winner;
            uint64_t by_addr = refuses
                ? _this->superbank_addr[bank / _this->superbank_banks]
                : _this->pending[winner]->get_addr();
            for (int i = 0; i < _this->nb_inputs; i++)
            {
                if (((req_mask >> i) & 1) && (i != winner || refuses) && _this->trace_input[i])
                {
                    uint64_t addr = _this->pending[i]->get_addr();
                    _this->ev.stalls.msg(vp::Trace::LEVEL_INFO,
                        "%ld stall in=%d addr=0x%lx bank=%d row=%ld by=%d by_addr=0x%lx%s\n",
                        (long)cycle, i, (unsigned long)addr, bank,
                        (long)(addr >> (_this->width_bits + _this->bank_bits)), by,
                        (unsigned long)by_addr, _this->beat_field(_this->pending[i]).c_str());
                }
            }
        }
        int requests = refuses;
        for (int i = 0; i < _this->nb_inputs; i++)
        {
            if ((req_mask >> i) & 1)
            {
                requests += !_this->holds[i];
                if (i != winner || refuses)
                {
                    _this->input_stalls[i]++;
                    _this->input_stalls_dma[i] += refuses;
                }
            }
        }
        if (requests >= 2)
        {
            _this->bank_conflicts[bank]++;
        }
        if (refuses)
        {
            // Dropped with the losers; locked in, it wins again next cycle if
            // it still competes
            if (_this->sparse)
            {
                _this->sparse_arbs[bank].refused();
            }
            else
            {
                _this->plain_arbs[bank].refused();
            }
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Bank %d: refused %s (dma)%s\n", bank,
                _this->name(winner).c_str(), _this->others(req_mask, winner).c_str());
            continue;
        }
        if (!_this->sparse)
        {
            _this->plain_arbs[bank].granted();
        }

        vp::IoReq *req = _this->pending[winner];
        uint64_t addr = req->get_addr();

        _this->grant_cycle[bank] = cycle;
        _this->grant_input[bank] = winner;
        _this->input_grants[winner]++;
        if (!_this->holds[winner])
        {
            (req->get_is_write() ? _this->bank_writes : _this->bank_reads)[bank]++;
        }

        if (_this->trace.get_active(vp::Trace::LEVEL_DEBUG))
        {
            // The size only when it is less than a bank word
            vp::IoReqOpcode opcode = req->get_opcode();
            std::string size = req->get_size() < (1ULL << _this->width_bits)
                ? ", " + std::to_string(req->get_size()) + " B" : "";
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Bank %d: grant %s (%s 0x%lx%s)%s\n", bank, _this->name(winner).c_str(),
                opcode == vp::IoReqOpcode::READ ? "read"
                    : opcode == vp::IoReqOpcode::WRITE ? "write" : "amo",
                addr, size.c_str(), _this->others(req_mask, winner).c_str());
        }

        // The bank access, at the bank-local address: the memory answers at
        // once and adds latency if it is already busy in this cycle. The
        // latency the request carries (a core's router) comes on top.
        vp::IoSlave *resp_port = req->get_resp_port();
        uint64_t bank_addr = ((addr >> (_this->width_bits + _this->bank_bits)) << _this->width_bits)
            | (addr & ((1 << _this->width_bits) - 1));
        int64_t carried = req->get_latency();
        req->prepare();
        req->set_addr(bank_addr);
        vp::IoReqStatus status = _this->banks[bank].req(req);
        if (status != vp::IO_REQ_OK)
        {
            _this->trace.fatal("Bank %d did not answer at once (status: %d)\n", bank, status);
            return;
        }
        int64_t latency = carried + req->get_latency();
        req->set_addr(addr);
        req->resp_port = resp_port;

        // Answered at the grant (a held write), else one cycle after it
        bool at_grant = _this->holds[winner] && req->get_opcode() == vp::IoReqOpcode::WRITE;
        if (_this->trace_input[winner] && _this->ev.beats.get_active())
        {
            vp::IoReqOpcode opcode = req->get_opcode();
            std::string size = req->get_size() < (1ULL << _this->width_bits)
                ? " size=" + std::to_string(req->get_size()) : "";
            _this->ev.beats.msg(vp::Trace::LEVEL_INFO,
                "%ld grant in=%d op=%s addr=0x%lx bank=%d row=%ld value=%s back=%ld%s%s\n",
                (long)cycle, winner, opcode == vp::IoReqOpcode::READ ? "r"
                    : opcode == vp::IoReqOpcode::WRITE ? "w" : "a",
                (unsigned long)addr, bank, (long)(addr >> (_this->width_bits + _this->bank_bits)),
                snax_word(req->get_data(), req->get_size()).c_str(),
                (long)(at_grant ? cycle : cycle + 1 + latency),
                _this->beat_field(req).c_str(), size.c_str());
        }

        _this->pending[winner] = NULL;
        resp_port->grant(req);
        if (at_grant)
        {
            _this->answer(req, winner);
        }
        else
        {
            _this->responses.push_back({cycle + 1 + latency, req, winner});
        }
    }

    // The losers of inputs that resend are dropped; their masters send them
    // again next cycle, with their priority bit. Those of inputs that hold
    // stay, with theirs.
    bool any_held = false;
    for (int i = 0; i < _this->nb_inputs; i++)
    {
        if (_this->holds[i] && _this->pending[i] != NULL)
        {
            any_held = true;
            continue;
        }
        _this->pending[i] = NULL;
        _this->priority[i] = false;
    }
    if (any_held)
    {
        _this->held_event.enqueue(1);
    }

    // Keeps the earlier cycle if the event is already queued for a later one
    if (!_this->responses.empty())
    {
        _this->resp_event.enqueue(1);
    }
}


// The first event of a cycle that starts with a held request. Queued in the
// cycle before, it may come before the events of this cycle's other masters;
// the arbitration it queues comes after every event already queued for the
// cycle, as one queued by a master's request.
void SnaxTcdmXbar::held_cycle(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;
    if (!_this->arb_event.is_enqueued())
    {
        _this->arb_event.enqueue(0);
    }
}


// The response: the cycle it comes in holds every latency, so it carries none
void SnaxTcdmXbar::answer(vp::IoReq *req, int input)
{
    this->trace.msg(vp::Trace::LEVEL_TRACE, "Resp %s (%s 0x%lx)\n", this->names[input].c_str(),
        req->get_is_write() ? "write" : "read", req->get_addr());
    req->prepare();
    req->get_resp_port()->resp(req);
}


void SnaxTcdmXbar::respond(vp::Block *__this, vp::ClockEvent *event)
{
    SnaxTcdmXbar *_this = (SnaxTcdmXbar *)__this;
    int64_t cycle = _this->clock.get_cycles();
    int64_t next = -1;

    // In grant order, the ones due now; the others stay, in order
    size_t kept = 0;
    for (size_t i = 0; i < _this->responses.size(); i++)
    {
        Response &entry = _this->responses[i];
        if (entry.cycle <= cycle)
        {
            _this->answer(entry.req, entry.input);
        }
        else
        {
            if (next == -1 || entry.cycle < next)
            {
                next = entry.cycle;
            }
            _this->responses[kept++] = entry;
        }
    }
    _this->responses.resize(kept);

    if (next != -1)
    {
        _this->resp_event.enqueue(next - cycle);
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxTcdmXbar(config);
}
