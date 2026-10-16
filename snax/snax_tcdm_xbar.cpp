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
// Inputs are numbered as on the RTL: the SNAX ports, the cores, AXI. The DMA
// does not go through this crossbar; it reaches the same banks on its own
// path.

#include <algorithm>
#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
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
    static void priority_sync(vp::Block *__this, bool value, int id);
    static void arbitrate(vp::Block *__this, vp::ClockEvent *event);
    static void held_cycle(vp::Block *__this, vp::ClockEvent *event);
    static void respond(vp::Block *__this, vp::ClockEvent *event);
    void answer(vp::IoReq *req, int input);
    void reset(bool active) override;

    // The sparse interconnect's winner on bank among the inputs in req_mask
    int sparse_pick(int bank, uint64_t req_mask, int64_t cycle);
    // Whether bank refuses this cycle's winner. Nothing refuses yet; the
    // DMA's superbank will (SG7 round 4).
    bool bank_refuses(int bank) { return false; }

    vp::Trace trace;
    std::vector<vp::IoSlave> inputs;
    std::vector<vp::WireSlave<bool>> priority_itf;
    std::vector<vp::IoMaster> banks;
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
};


SnaxTcdmXbar::SnaxTcdmXbar(vp::ComponentConf &config)
    : vp::Component(config),
      arb_event(this, &SnaxTcdmXbar::arbitrate),
      held_event(this, &SnaxTcdmXbar::held_cycle),
      resp_event(this, &SnaxTcdmXbar::respond)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

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
        if (_this->bank_refuses(bank))
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
            _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Bank %d: refused %s\n", bank,
                _this->names[winner].c_str());
            continue;
        }
        if (!_this->sparse)
        {
            _this->plain_arbs[bank].granted();
        }

        vp::IoReq *req = _this->pending[winner];
        uint64_t addr = req->get_addr();

        if (_this->trace.get_active(vp::Trace::LEVEL_DEBUG))
        {
            // Sparse: an input asking with priority 1 is marked with !
            auto name = [&](int i) {
                return _this->names[i] + (_this->sparse && _this->priority[i] ? "!" : "");
            };
            std::string held;
            for (int i = 0; i < _this->nb_inputs; i++)
            {
                if (i != winner && ((req_mask >> i) & 1))
                {
                    held += " " + name(i);
                }
            }
            // The size only when it is less than a bank word
            vp::IoReqOpcode opcode = req->get_opcode();
            std::string size = req->get_size() < (1ULL << _this->width_bits)
                ? ", " + std::to_string(req->get_size()) + " B" : "";
            _this->trace.msg(vp::Trace::LEVEL_DEBUG,
                "Bank %d: grant %s (%s 0x%lx%s)%s%s\n", bank, name(winner).c_str(),
                opcode == vp::IoReqOpcode::READ ? "read"
                    : opcode == vp::IoReqOpcode::WRITE ? "write" : "amo",
                addr, size.c_str(), held.empty() ? "" : ", held:", held.c_str());
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

        _this->pending[winner] = NULL;
        resp_port->grant(req);
        if (_this->holds[winner] && req->get_opcode() == vp::IoReqOpcode::WRITE)
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
