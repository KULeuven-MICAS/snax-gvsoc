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

#include <vector>
#include <cinttypes>
#include <cstring>
#include <vp/vp.hpp>
#include <vp/itf/io.hpp>
#include <vp/itf/wire.hpp>
#include <pulp/snitch/snitch_cluster/cluster_periph_regfields.h>
#include <pulp/snitch/snitch_cluster/cluster_periph_gvsoc.h>


using namespace std::placeholders;


class ClusterRegisters : public vp::Component
{

public:

    ClusterRegisters(vp::ComponentConf &config);

    void reset(bool active);

    static vp::IoReqStatus req(vp::Block *__this, vp::IoReq *req);

private:
    static void barrier_sync(vp::Block *__this, bool value, int id);
    void cl_clint_set_req(uint64_t reg_offset, int size, uint8_t *value, bool is_write);
    void cl_clint_clear_req(uint64_t reg_offset, int size, uint8_t *value, bool is_write);

    vp::Trace     trace;

    vp_regmap_cluster_periph regmap;

    vp::IoSlave in;
    uint32_t bootaddr;
    uint32_t status;
    int nb_cores;
    vp::reg_32 barrier_status;

    std::vector<vp::WireSlave<bool>> barrier_req_itf;
    vp::WireMaster<bool> barrier_ack_itf;

    std::vector<vp::WireMaster<bool>> external_irq_itf;

    // SNAX: the performance counters of snitch_cluster_peripheral.sv. Each of the 16 counters
    // has an enable (one bit per event), a hart select and a 48-bit value, 8 bytes apart.
    // The RTL adds, every cycle, the event of the lowest enable bit set (its if-else chain);
    // here only CYCLE, DMA_R_DONE, DMA_W_DONE and DMA_BUSY are modelled, the other events
    // count nothing. CYCLE and DMA_BUSY are counted from timestamps, not per cycle: a
    // counter is brought up to date before any change and before a read. The one-cycle
    // register on the RTL's events is not modelled: a count only differs when an event
    // crosses the moment a counter is enabled or stopped.
    static constexpr int PERF_NB = 16;
    static constexpr uint64_t PERF_ENABLE_OFFSET = 0x000;
    static constexpr uint64_t PERF_HART_SELECT_OFFSET = 0x080;
    static constexpr uint64_t PERF_COUNTER_OFFSET = 0x100;
    static constexpr uint64_t PERF_END_OFFSET = 0x180;
    static constexpr uint64_t PERF_MASK = (1ULL << 48) - 1;
    // Event bits of PERF_COUNTER_ENABLE
    static constexpr int PERF_EV_CYCLE = 0;
    static constexpr int PERF_EV_DMA_R_DONE = 20;
    static constexpr int PERF_EV_DMA_W_DONE = 22;
    static constexpr int PERF_EV_DMA_BUSY = 25;

    struct PerfCounter
    {
        uint64_t enable;
        uint64_t hart_select;
        uint64_t value;
    };
    PerfCounter perf[PERF_NB];
    // Cycle up to which CYCLE and DMA_BUSY counters are counted
    int64_t perf_cycle;
    // Last value received on the DMA busy wire
    bool dma_busy;

    vp::WireSlave<bool> dma_busy_itf;
    vp::WireSlave<int> dma_r_beats_itf;
    vp::WireSlave<int> dma_w_beats_itf;

    bool perf_access(uint64_t offset, int size, uint8_t *data, bool is_write);
    int perf_event(int counter);
    void perf_settle();
    void perf_add(int event, uint64_t n);
    static void dma_busy_sync(vp::Block *__this, bool value);
    static void dma_r_beats_sync(vp::Block *__this, int value);
    static void dma_w_beats_sync(vp::Block *__this, int value);
};

ClusterRegisters::ClusterRegisters(vp::ComponentConf &config)
: vp::Component(config), regmap(*this, "regmap")
{
    this->traces.new_trace("trace", &trace, vp::DEBUG);

    this->in.set_req_meth(&ClusterRegisters::req);
    this->new_slave_port("input", &this->in);

    this->bootaddr = this->get_js_config()->get("boot_addr")->get_int();
    this->nb_cores = this->get_js_config()->get("nb_cores")->get_int();

    this->barrier_req_itf.resize(this->nb_cores);
    for (int i=0; i<this->nb_cores; i++)
    {
        this->barrier_req_itf[i].set_sync_meth_muxed(&ClusterRegisters::barrier_sync, i);
        this->new_slave_port("barrier_req_" + std::to_string(i), &this->barrier_req_itf[i]);
    }

    this->external_irq_itf.resize(this->nb_cores);
    for (int i=0; i<this->nb_cores; i++)
    {
        this->new_master_port("external_irq_" + std::to_string(i), &this->external_irq_itf[i]);
    }

    this->new_master_port("barrier_ack", &this->barrier_ack_itf);

    this->dma_busy_itf.set_sync_meth(&ClusterRegisters::dma_busy_sync);
    this->new_slave_port("dma_busy", &this->dma_busy_itf);
    this->dma_r_beats_itf.set_sync_meth(&ClusterRegisters::dma_r_beats_sync);
    this->new_slave_port("dma_r_beats", &this->dma_r_beats_itf);
    this->dma_w_beats_itf.set_sync_meth(&ClusterRegisters::dma_w_beats_sync);
    this->new_slave_port("dma_w_beats", &this->dma_w_beats_itf);

    this->regmap.build(this, &this->trace, "regmap");
    this->regmap.cl_clint_set.register_callback(std::bind(&ClusterRegisters::cl_clint_set_req, this, _1, _2, _3, _4));
    this->regmap.cl_clint_clear.register_callback(std::bind(&ClusterRegisters::cl_clint_clear_req, this, _1, _2, _3, _4));
}

vp::IoReqStatus ClusterRegisters::req(vp::Block *__this, vp::IoReq *req)
{
    ClusterRegisters *_this = (ClusterRegisters *)__this;
    uint64_t offset = req->get_addr();
    bool is_write = req->get_is_write();
    uint64_t size = req->get_size();
    uint8_t *data = req->get_data();

    _this->trace.msg("Received IO req (offset: 0x%llx, size: 0x%llx, is_write: %d)\n", offset, size, is_write);

    if (!_this->perf_access(offset, size, data, is_write))
    {
        _this->regmap.access(offset, size, data, is_write);
    }

    return vp::IO_REQ_OK;
}

// Handles an access to the performance counter registers, returns false for any other offset.
bool ClusterRegisters::perf_access(uint64_t offset, int size, uint8_t *data, bool is_write)
{
    if (offset >= PERF_END_OFFSET)
    {
        return false;
    }

    uint64_t index = (offset & 0x7f) / 8;
    uint64_t byte = offset % 8;
    if (byte + size > 8)
    {
        this->trace.force_warning("Perf counter access across registers (offset: 0x%" PRIx64
            ", size: %d)\n", offset, size);
        return true;
    }

    // Bring CYCLE and DMA_BUSY up to date before the access reads or changes them
    this->perf_settle();

    PerfCounter &counter = this->perf[index];
    uint64_t *reg = offset < PERF_HART_SELECT_OFFSET ? &counter.enable :
        offset < PERF_COUNTER_OFFSET ? &counter.hart_select : &counter.value;

    uint8_t bytes[8];
    memcpy(bytes, reg, 8);
    if (is_write)
    {
        memcpy(bytes + byte, data, size);
        memcpy(reg, bytes, 8);
        counter.value &= PERF_MASK;
    }
    else
    {
        memcpy(data, bytes + byte, size);
    }

    this->trace.msg(vp::Trace::LEVEL_DEBUG, "Perf counter %d %s (enable: 0x%" PRIx64
        ", value: %" PRIu64 ")\n", (int)index, is_write ? "written" : "read", counter.enable,
        counter.value);
    return true;
}

// The event a counter counts: the lowest enable bit set, as the RTL's if-else chain picks it.
int ClusterRegisters::perf_event(int counter)
{
    uint64_t enable = this->perf[counter].enable;
    return enable == 0 ? -1 : __builtin_ctzll(enable);
}

// Adds the cycles since the last update to the counters of CYCLE, and of DMA_BUSY while busy.
void ClusterRegisters::perf_settle()
{
    int64_t now = this->clock.get_cycles();
    uint64_t cycles = now - this->perf_cycle;
    this->perf_cycle = now;
    if (cycles == 0)
    {
        return;
    }
    for (int i = 0; i < PERF_NB; i++)
    {
        int event = this->perf_event(i);
        if (event == PERF_EV_CYCLE || (event == PERF_EV_DMA_BUSY && this->dma_busy))
        {
            this->perf[i].value = (this->perf[i].value + cycles) & PERF_MASK;
        }
    }
}

// Adds n to every counter counting a discrete event.
void ClusterRegisters::perf_add(int event, uint64_t n)
{
    for (int i = 0; i < PERF_NB; i++)
    {
        if (this->perf_event(i) == event)
        {
            this->perf[i].value = (this->perf[i].value + n) & PERF_MASK;
        }
    }
}

void ClusterRegisters::dma_busy_sync(vp::Block *__this, bool value)
{
    ClusterRegisters *_this = (ClusterRegisters *)__this;
    _this->perf_settle();
    _this->dma_busy = value;
}

void ClusterRegisters::dma_r_beats_sync(vp::Block *__this, int value)
{
    ClusterRegisters *_this = (ClusterRegisters *)__this;
    _this->perf_add(PERF_EV_DMA_R_DONE, value);
}

void ClusterRegisters::dma_w_beats_sync(vp::Block *__this, int value)
{
    ClusterRegisters *_this = (ClusterRegisters *)__this;
    _this->perf_add(PERF_EV_DMA_W_DONE, value);
}

void ClusterRegisters::barrier_sync(vp::Block *__this, bool value, int id)
{
    ClusterRegisters *_this = (ClusterRegisters *)__this;
    _this->barrier_status.set(_this->barrier_status.get() | (value << id));

    _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Barrier sync (id: %d, status: 0x%x)\n", id, _this->barrier_status.get());

    if (_this->barrier_status.get() == (1ULL << _this->nb_cores) - 1)
    {
        _this->trace.msg(vp::Trace::LEVEL_DEBUG, "Barrier reached\n");

        _this->barrier_status.set(0);
        _this->barrier_ack_itf.sync(1);
    }
}

void ClusterRegisters::reset(bool active)
{
    this->new_reg("barrier_status", &this->barrier_status, 0, true);

    if (active)
    {
        memset(this->perf, 0, sizeof(this->perf));
        this->perf_cycle = this->clock.get_cycles();
        this->dma_busy = false;
    }
}


void ClusterRegisters::cl_clint_set_req(uint64_t reg_offset, int size, uint8_t *value, bool is_write)
{
    this->regmap.cl_clint_set.update(reg_offset, size, value, is_write);
    for (int i=0; i<this->nb_cores; i++)
    {
        int irq_status = (this->regmap.cl_clint_set.get() >> i) & 1;
        if (irq_status == 1)
        {
            this->external_irq_itf[i].sync(true);
        }
    }
}

void ClusterRegisters::cl_clint_clear_req(uint64_t reg_offset, int size, uint8_t *value, bool is_write)
{
    this->regmap.cl_clint_clear.update(reg_offset, size, value, is_write);
    for (int i=0; i<this->nb_cores; i++)
    {
        int irq_status = (this->regmap.cl_clint_clear.get() >> i) & 1;
        if (irq_status == 1)
        {
            this->external_irq_itf[i].sync(false);
        }
    }
}


extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new ClusterRegisters(config);
}
