/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// A stand-in for the CSR side of a SNAX accelerator, bound to a Snitch core's
// snax_csr port. It holds the accelerator's CSRs as snax_cluster's CSR manager
// (hw/chisel/.../reqRspManager/ReqRspManager.scala) sees them: read-write
// registers that read back what was written, and read-only registers that the
// accelerator drives, here always 0 (so busy reads 0). Nothing is started.
//
// The core sends each CSR access as a 32-bit IO request at byte address
// 4 * CSR number. An access to a CSR the stub does not hold, or a write to a
// read-only one, is refused: the RTL's manager asserts on both.

#include <map>
#include <set>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>


class SnaxCsrStub : public vp::Component
{
public:
    SnaxCsrStub(vp::ComponentConf &config);

private:
    static vp::IoReqStatus req(vp::Block *__this, vp::IoReq *req);
    void reset(bool active) override;

    vp::Trace trace;
    vp::IoSlave input_itf;

    // CSR number -> value of each read-write CSR
    std::map<uint32_t, uint32_t> rw_regs;
    // Numbers of the read-only CSRs
    std::set<uint32_t> ro_regs;
};


SnaxCsrStub::SnaxCsrStub(vp::ComponentConf &config)
    : vp::Component(config)
{
    this->traces.new_trace("trace", &this->trace, vp::DEBUG);
    this->input_itf.set_req_meth(&SnaxCsrStub::req);
    this->new_slave_port("input", &this->input_itf);

    for (auto x : this->get_js_config()->get("rw_csrs")->get_elems())
    {
        this->rw_regs[x->get_int()] = 0;
    }
    for (auto x : this->get_js_config()->get("ro_csrs")->get_elems())
    {
        this->ro_regs.insert(x->get_int());
    }
}


// Reset clears the read-write CSRs, as the RTL's RegInit does.
void SnaxCsrStub::reset(bool active)
{
    if (active)
    {
        for (auto &reg : this->rw_regs)
        {
            reg.second = 0;
        }
    }
}


vp::IoReqStatus SnaxCsrStub::req(vp::Block *__this, vp::IoReq *req)
{
    SnaxCsrStub *_this = (SnaxCsrStub *)__this;

    uint32_t csr = req->get_addr() / 4;
    uint32_t *data = (uint32_t *)req->get_data();
    bool is_write = req->get_is_write();

    if (req->get_size() != 4 || req->get_addr() % 4 != 0)
    {
        _this->trace.force_warning("Unexpected access (addr: 0x%lx, size: %ld)\n",
            req->get_addr(), req->get_size());
        return vp::IO_REQ_INVALID;
    }

    auto rw = _this->rw_regs.find(csr);
    if (rw != _this->rw_regs.end())
    {
        if (is_write)
        {
            rw->second = *data;
        }
        else
        {
            *data = rw->second;
        }
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "%s CSR %d (value: 0x%x)\n",
            is_write ? "Write" : "Read", csr, *data);
        return vp::IO_REQ_OK;
    }

    if (_this->ro_regs.count(csr))
    {
        if (is_write)
        {
            _this->trace.force_warning("Write to read-only CSR %d (value: 0x%x)\n", csr, *data);
            return vp::IO_REQ_INVALID;
        }
        *data = 0;
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Read CSR %d (value: 0x0, read-only)\n", csr);
        return vp::IO_REQ_OK;
    }

    _this->trace.force_warning("CSR %d is not held by this block (is_write: %d)\n",
        csr, is_write);
    return vp::IO_REQ_INVALID;
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new SnaxCsrStub(config);
}
