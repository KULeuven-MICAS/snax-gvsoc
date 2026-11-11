/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// A shared streamer's data-side mux (snax-forge D169): between the movers'
// beat ports and the groups' ports, selected by PORT_MUX_SEL. The rule is
// SnaxPortMuxRule (snax_port_mux.hpp); here its ports, its CSR and its fatals.
//
// Ports: port_<i>, an io slave per group port (properties.users[i]), the one
// its group's outer port binds; mover_<k>, an io master to the streamer's
// reader or writer k (properties.movers[k]); input, the CSR PORT_MUX_SEL at
// offset 0, R/W, 0 after reset, its width the property sel_width; busy, a
// wire<bool> slave from the streamer.
//
// A beat (or a probe, size 0) on port_<i> is passed on to its mover in the same
// call, so it takes no cycle: a reader's answer and its first words come back,
// a writer's beat goes on with the mover's other words 0. The streamer's
// answer (OK, DENIED) is the port's; a reader's beat id (SNAX_ARG_TAG,
// SNAX_ARG_ID) comes back with it. Every error of the rule is a fatal.

#include <string>
#include <vector>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include "snax_csr_block.hpp"
#include "snax_events.hpp"
#include "snax_port_mux.hpp"
#include "snax_props.hpp"


class SnaxPortMux : public vp::Component
{
public:
    SnaxPortMux(vp::ComponentConf &config);

private:
    static vp::IoReqStatus csr_req(vp::Block *__this, vp::IoReq *req);
    static vp::IoReqStatus port_req(vp::Block *__this, vp::IoReq *req, int id);
    static void busy_sync(vp::Block *__this, bool value);
    void reset(bool active) override;

    vp::Trace trace;
    vp::IoSlave csr_itf;
    vp::WireSlave<bool> busy_itf;
    std::vector<vp::IoSlave> port_itf;
    std::vector<vp::IoMaster> mover_itf;
    SnaxCsrBlock csrs;
    SnaxPortMuxRule rule;
    uint32_t sel_mask;

    std::vector<std::string> groups;
    std::vector<std::string> port_names;
    std::vector<std::string> mover_names;
    bool streamer_busy;
    vp::IoReq mover_req;
    std::vector<uint64_t> mover_beat;   // the widest mover's words
};


SnaxPortMux::SnaxPortMux(vp::ComponentConf &config) : vp::Component(config)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);

    js::Config *cfg = this->get_js_config();
    SnaxProps props(&this->trace);
    int sel_width = props.int_prop(cfg, "sel_width", "");
    if (sel_width < 1 || sel_width > 32)
    {
        this->trace.fatal("Property sel_width: %d, must be 1 to 32\n", sel_width);
    }
    this->sel_mask = sel_width == 32 ? 0xFFFFFFFF : (1U << sel_width) - 1;

    std::vector<js::Config *> groups = props.list_prop(cfg, "groups", "");
    for (js::Config *g : groups)
    {
        this->groups.push_back(g->get_str());
    }

    std::vector<SnaxMuxMover> movers;
    std::vector<js::Config *> mover_list = props.list_prop(cfg, "movers", "");
    size_t widest = 0;
    for (size_t k = 0; k < mover_list.size(); k++)
    {
        std::string w = "movers[" + std::to_string(k) + "]";
        js::Config *m = mover_list[k];
        this->mover_names.push_back(props.str_prop(m, "name", w));
        movers.push_back({props.bool_prop(m, "is_reader", w), props.int_prop(m, "num_channel", w)});
        widest = std::max(widest, (size_t)movers.back().num_channel);
    }

    std::vector<SnaxMuxPort> ports;
    std::vector<js::Config *> port_list = props.list_prop(cfg, "users", "");
    for (size_t i = 0; i < port_list.size(); i++)
    {
        std::string w = "users[" + std::to_string(i) + "]";
        js::Config *p = port_list[i];
        this->port_names.push_back(props.str_prop(p, "name", w));
        ports.push_back({props.int_prop(p, "group", w), props.int_prop(p, "mover", w),
            props.int_prop(p, "num_channel", w)});
    }
    try
    {
        this->rule = SnaxPortMuxRule(this->groups.size(), movers, ports);
    }
    catch (const std::invalid_argument &e)
    {
        this->trace.fatal("Port mux: %s\n", e.what());
    }
    this->mover_beat.assign(widest, 0);

    this->csrs.configure(&this->trace, props.int_prop(cfg, "csr_base", ""), 1, 0);
    this->csr_itf.set_req_meth(&SnaxPortMux::csr_req);
    this->new_slave_port("input", &this->csr_itf);
    this->busy_itf.set_sync_meth(&SnaxPortMux::busy_sync);
    this->new_slave_port("busy", &this->busy_itf);

    // Sized once, before any port is registered
    this->port_itf.resize(ports.size());
    this->mover_itf.resize(movers.size());
    for (size_t i = 0; i < ports.size(); i++)
    {
        this->port_itf[i].set_req_meth_muxed(&SnaxPortMux::port_req, i);
        this->new_slave_port("port_" + std::to_string(i), &this->port_itf[i]);
    }
    for (size_t k = 0; k < movers.size(); k++)
    {
        this->new_master_port("mover_" + std::to_string(k), &this->mover_itf[k]);
    }

    this->trace.msg(vp::Trace::LEVEL_DEBUG, "CSR %d: PORT_MUX_SEL, %zu groups\n",
        this->csrs.csr(0), this->groups.size());
}


void SnaxPortMux::reset(bool active)
{
    if (active)
    {
        this->csrs.reset();
        this->rule.reset();
        this->streamer_busy = false;
    }
}


void SnaxPortMux::busy_sync(vp::Block *__this, bool value)
{
    ((SnaxPortMux *)__this)->streamer_busy = value;
}


vp::IoReqStatus SnaxPortMux::csr_req(vp::Block *__this, vp::IoReq *req)
{
    SnaxPortMux *_this = (SnaxPortMux *)__this;
    vp::IoReqStatus status;
    int index = _this->csrs.access(req, &status, [](int) -> uint32_t { return 0; });
    if (index < 0)
    {
        return status;
    }
    uint32_t value = *(uint32_t *)req->get_data() & _this->sel_mask;
    SnaxMuxError error = _this->rule.select(value, _this->streamer_busy);
    if (error != SNAX_MUX_OK)
    {
        _this->trace.fatal("PORT_MUX_SEL (CSR %d) written with %u: %s\n", _this->csrs.csr(0),
            value, SnaxPortMuxRule::error_name(error));
        return vp::IO_REQ_INVALID;
    }
    _this->csrs.write(0, value, (", " + _this->groups[value]).c_str());
    return vp::IO_REQ_OK;
}


vp::IoReqStatus SnaxPortMux::port_req(vp::Block *__this, vp::IoReq *req, int id)
{
    SnaxPortMux *_this = (SnaxPortMux *)__this;
    uint64_t size = req->get_size();
    bool is_write = req->get_is_write();
    SnaxMuxError error = _this->rule.check(id, is_write, size);
    if (error != SNAX_MUX_OK)
    {
        _this->trace.fatal("%s (%s, size %ld) while %s is selected: %s\n",
            _this->port_names[id].c_str(), is_write ? "write" : "read", (long)size,
            _this->groups[_this->rule.selected()].c_str(), SnaxPortMuxRule::error_name(error));
        return vp::IO_REQ_INVALID;
    }

    int k = _this->rule.mover_of(id);
    vp::IoReq *out = &_this->mover_req;
    out->init();
    out->set_size(_this->rule.mover_size(id, size));
    out->set_is_write(is_write);
    out->set_data((uint8_t *)_this->mover_beat.data());
    if (is_write && size != 0)
    {
        _this->rule.to_mover(id, (const uint64_t *)req->get_data(), _this->mover_beat.data());
    }

    vp::IoReqStatus status = _this->mover_itf[k].req(out);
    if (status == vp::IO_REQ_OK && size != 0 && !is_write)
    {
        _this->rule.to_port(id, _this->mover_beat.data(), (uint64_t *)req->get_data());
        snax_arg_set(req, SNAX_ARG_TAG, snax_arg_get(out, SNAX_ARG_TAG));
        snax_arg_set(req, SNAX_ARG_ID, snax_arg_get(out, SNAX_ARG_ID));
    }
    return status;
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxPortMux(config);
}
