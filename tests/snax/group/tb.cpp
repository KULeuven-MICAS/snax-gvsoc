// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxGroupRule (snax/snax_group.hpp) against the shared group cases
// (README.md): each case gives the group (its units, head first, with their
// datapath, L, II, span, T and outer inputs; its links, the edges the rule
// takes, each into the input after its consumer's outer ones, as SnaxGroup
// numbers a unit's inputs; JOBS), the
// start and, per cycle, the outer inputs' valid and the outer output's
// ready, then per unit whether it fires and gives (pushes a result into its
// link or the outer output), per buffer its occupancy after the cycle, and
// whether the group is busy. The tb steps the rule with them and compares
// every cycle and the run line at the end of each run, whose classes must add
// up to the run's busy cycles in the file. It also runs the group's datapaths
// with the rule's enables (snax_group.hpp's SnaxGroupDatapaths, as the
// component does) on a dot product of int64, beat i of a and b the head's i-th
// firing's, and checks each result the last unit pushes against its job's sum:
// the case's own data when it has some (lanes, data a, data b, sums), else 4
// lanes of a_of and b_of and the sum of each job's products. A case with dout
// D packs the outer output D to a word (snax_group.hpp's SnaxPacker): the
// rule's outer room is the packer's, each cycle's word sent is compared, and
// the words sent against the case's words, push n's result taken as -(n + 1).
// A case with din I D slices outer input I D to a word (snax_group.hpp's
// SnaxSlicer): its V column is its reader's valid, the rule sees the slicer's
// full, each cycle's word taken is compared, and the slices popped from each
// whole word, put back low first, must give that word. A seeded Mac alone
// (D187) runs its datapath too: 4 lanes of int8 a and b into int32, its seed
// of 4 int32 lanes, each job's result seed + its products; a or b sliced to one
// lane a pop is a broadcast (D186), each slice given to the 4 lanes by
// snax_broadcast, as SnaxGroup does.
//
//   tb CASE...
//
// Exit 1 on any difference.

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "snax_datapath.hpp"
#include "snax_group.hpp"
#include "../tb_common.hpp"


struct UnitLine
{
    std::string name, datapath;
    SnaxGroupRule::UnitCfg cfg;
    uint32_t t = 1;
    int inputs = 0;     // outer inputs
    bool seed = false;  // the last of them is a fold's seed, one beat per job
};

struct CycleLine
{
    std::vector<int> valid;     // the outer inputs', unit by unit
    int ready = 1;
    std::vector<int> fire, give;    // per unit
    std::vector<int> occupancy;     // per buffer
    std::vector<int> took;          // with din: per sliced input, a word taken from its reader
    int sent = 0;                   // with dout: a word went to the writer
    int busy = 0;
    int lineno = 0;
};

struct Case
{
    std::string name;
    std::vector<UnitLine> units;
    std::vector<SnaxGroupRule::Link> links;
    uint32_t jobs = 1;
    int64_t start_cycle = -1;
    std::string start_result;
    std::vector<std::string> expects;
    std::vector<CycleLine> cycles;
    int lanes = 0;                      // 0: no data of its own
    std::vector<int64_t> a, b, sums;    // a and b element i * lanes + l, a job's sum each
    int dout = 1;                       // the outer output's results per word (packer)
    std::vector<uint64_t> words;        // with dout: the words the packer sends
    std::vector<std::pair<int, int>> din;   // per sliced input: its index and its pops a word
};

static std::vector<std::string> fields(const std::string &line, char sep)
{
    std::vector<std::string> out;
    std::string part;
    std::istringstream ss(line);
    while (std::getline(ss, part, sep))
    {
        out.push_back(part);
    }
    return out;
}

static bool int64s(std::istringstream &ss, std::vector<int64_t> &v)
{
    long long x;
    while (ss >> x)
    {
        v.push_back(x);
    }
    return ss.eof() && !v.empty();
}

static std::vector<int> ints(const std::string &text)
{
    std::istringstream ss(text);
    std::vector<int> v;
    int x;
    while (ss >> x)
    {
        v.push_back(x);
    }
    return v;
}

static bool parse(const std::string &path, Case &c)
{
    std::ifstream in(path);
    if (!in)
    {
        fprintf(stderr, "%s: cannot open\n", path.c_str());
        return false;
    }
    c.name = tb_base_of(path);
    bool in_cycles = false;
    std::string raw;
    int lineno = 0;
    while (std::getline(in, raw))
    {
        lineno++;
        std::string line = raw.substr(0, raw.find('#'));
        std::istringstream ss(line);
        std::string key;
        if (!(ss >> key))
        {
            continue;
        }
        bool ok = true;
        if (in_cycles)
        {
            // V... READY | F G | F G ... | OCC... | BUSY
            std::vector<std::string> cols = fields(line, '|');
            size_t buffers = 0;
            for (const SnaxGroupRule::Link &e : c.links)
            {
                buffers += e.depth > 0;
            }
            size_t want = 2 + c.units.size() + (buffers ? 1 : 0) + (c.din.empty() ? 0 : 1) +
                (c.dout > 1 ? 1 : 0);
            CycleLine l;
            l.lineno = lineno;
            ok = cols.size() == want;
            if (ok)
            {
                std::vector<int> head = ints(cols[0]);
                int nb_in = 0;
                for (const UnitLine &u : c.units)
                {
                    nb_in += u.inputs;
                }
                ok = (int)head.size() == nb_in + 1;
                if (ok)
                {
                    l.valid.assign(head.begin(), head.end() - 1);
                    l.ready = head.back();
                }
                for (size_t k = 0; ok && k < c.units.size(); k++)
                {
                    std::vector<int> fg = ints(cols[1 + k]);
                    ok = fg.size() == 2;
                    if (ok)
                    {
                        l.fire.push_back(fg[0]);
                        l.give.push_back(fg[1]);
                    }
                }
                if (ok && buffers)
                {
                    l.occupancy = ints(cols[1 + c.units.size()]);
                    ok = l.occupancy.size() == buffers;
                }
                if (ok && !c.din.empty())
                {
                    l.took = ints(cols[1 + c.units.size() + (buffers ? 1 : 0)]);
                    ok = l.took.size() == c.din.size();
                }
                if (ok && c.dout > 1)
                {
                    std::vector<int> sent = ints(cols[cols.size() - 2]);
                    ok = sent.size() == 1;
                    l.sent = ok ? sent[0] : 0;
                }
                std::vector<int> busy = ints(cols.back());
                ok = ok && busy.size() == 1;
                l.busy = ok ? busy[0] : 0;
            }
            c.cycles.push_back(l);
        }
        else if (key == "unit")
        {
            // unit NAME DATAPATH latency L ii N span S t T inputs I [seed 1]
            UnitLine u;
            std::string k1, k2, k3, k4, k5, k6;
            ok = (bool)(ss >> u.name >> u.datapath >> k1 >> u.cfg.latency >> k2 >> u.cfg.ii >> k3
                >> u.cfg.span >> k4 >> u.t >> k5 >> u.inputs) && k1 == "latency" && k2 == "ii" &&
                k3 == "span" && k4 == "t" && k5 == "inputs" && snax_datapaths().count(u.datapath);
            int seeded = 0;
            if (ok && ss >> k6)
            {
                ok = k6 == "seed" && (bool)(ss >> seeded) && (seeded == 0 || seeded == 1) &&
                    (!seeded || u.inputs >= 1);
            }
            u.seed = seeded;
            u.cfg.seeded = seeded;
            c.units.push_back(u);
        }
        else if (key == "link")
        {
            // link FROM TO depth D
            std::string from, to, k1;
            int depth;
            SnaxGroupRule::Link e;
            e.from = e.to = -1;
            ok = (bool)(ss >> from >> to >> k1 >> depth) && k1 == "depth" && depth >= 0;
            for (size_t k = 0; k < c.units.size(); k++)
            {
                e.from = c.units[k].name == from ? (int)k : e.from;
                e.to = c.units[k].name == to ? (int)k : e.to;
            }
            ok = ok && e.from != -1 && e.to != -1;
            if (ok)
            {
                e.to_input = c.units[e.to].inputs;
                e.depth = depth;
                c.links.push_back(e);
            }
        }
        else if (key == "jobs") { ok = (bool)(ss >> c.jobs); }
        else if (key == "start")
        {
            ok = (bool)(ss >> c.start_cycle >> c.start_result) &&
                (c.start_result == "taken" || c.start_result == "ignored" ||
                 c.start_result == "refused");
        }
        else if (key == "expect")
        {
            std::string rest;
            std::getline(ss, rest);
            size_t first = rest.find_first_not_of(' ');
            size_t last = rest.find_last_not_of(" \t\r");
            c.expects.push_back(first == std::string::npos ? "" : rest.substr(first, last - first + 1));
        }
        else if (key == "lanes") { ok = (bool)(ss >> c.lanes) && c.lanes > 0; }
        else if (key == "data")
        {
            std::string name;
            ok = (bool)(ss >> name) && (name == "a" || name == "b") &&
                int64s(ss, name == "a" ? c.a : c.b);
        }
        else if (key == "sums") { ok = int64s(ss, c.sums); }
        else if (key == "dout") { ok = (bool)(ss >> c.dout) && (c.dout == 2 || c.dout == 4 || c.dout == 8); }
        else if (key == "din")
        {
            // din I D, I an outer input in the V columns' order
            int i, d, nb_in = 0;
            for (const UnitLine &u : c.units)
            {
                nb_in += u.inputs;
            }
            ok = (bool)(ss >> i >> d) && i >= 0 && i < nb_in && (d == 2 || d == 4 || d == 8) &&
                (c.din.empty() || c.din.back().first < i);
            if (ok)
            {
                c.din.push_back({i, d});
            }
        }
        else if (key == "words")
        {
            std::string w;
            while (ok && ss >> w)
            {
                c.words.push_back(std::stoull(w, nullptr, 0));
            }
        }
        else if (key == "cycles") { in_cycles = true; }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    if (c.units.empty())
    {
        fprintf(stderr, "%s: no unit\n", path.c_str());
        return false;
    }
    if ((c.lanes || !c.a.empty() || !c.b.empty() || !c.sums.empty()) &&
        (!c.lanes || c.a.size() != c.b.size() || c.a.size() % c.lanes || c.sums.size() != c.jobs))
    {
        fprintf(stderr, "%s: lanes, data a, data b and sums do not fit (a JOBS of sums)\n",
            path.c_str());
        return false;
    }
    return true;
}

// The dot product the data check runs without data of the case's own: 4 lanes of int64, a
// head of two outer inputs
static const int LANES = 4;

static int64_t a_of(int i) { return (i * 7) % 13 - 6; }
static int64_t b_of(int i) { return (i * 5) % 11 - 5; }

// The group's datapaths for the dot shape: the head's two inputs a and b, the next unit's
// one the link; nullptr when the case is not a dot (no data check then)
static std::unique_ptr<SnaxGroupDatapaths> dot_datapaths(const Case &c, const SnaxGroupRule &rule)
{
    const SnaxType i64 = {64, true};
    if (c.units.size() != 2 || c.units[0].inputs != 2 || c.units[1].inputs != 0 ||
        c.links.size() != 1 || c.links[0].from != 0)
    {
        return nullptr;
    }
    auto g = std::unique_ptr<SnaxGroupDatapaths>(new SnaxGroupDatapaths());
    for (size_t k = 0; k < c.units.size(); k++)
    {
        SnaxDatapathParams p;
        p.in_types.assign(k == 0 ? 2 : 1, i64);
        p.lanes = c.lanes ? c.lanes : LANES;
        p.op = c.units[k].datapath == "SimdLanes" ? SNAX_OP_MUL : SNAX_OP_ADD;
        std::string why;
        g->units.push_back(snax_datapath_new(c.units[k].datapath, p, &why));
        if (!g->units.back())
        {
            return nullptr;
        }
    }
    SnaxDatapathParams p;
    p.in_types = {i64};
    p.lanes = c.lanes ? c.lanes : LANES;
    p.depth = c.links[0].depth;
    std::string why;
    g->buffers.push_back(c.links[0].depth ? snax_datapath_new("LinkBuffer", p, &why) : nullptr);
    g->wire(rule);
    return g;
}

// The seeded Mac's check: lanes of int8 a and b, its seed and its output int32, a seed per job
static const SnaxType MAC_IN = {8, true}, MAC_OUT = {32, true};

static int64_t seed_of(int i) { return (i * 37) % 101 - 50; }

// A seeded Mac alone, a its first input, b its second, the seed its third: its datapath;
// nullptr when the case is not one, or slices its seed or an input to more than one lane (a
// sliced a or b is a broadcast)
static std::unique_ptr<SnaxGroupDatapaths> mac_datapaths(const Case &c, const SnaxGroupRule &rule)
{
    if (c.units.size() != 1 || c.units[0].datapath != "Mac" || !c.units[0].seed ||
        c.units[0].inputs != 3 || !c.links.empty() || c.lanes)
    {
        return nullptr;
    }
    for (const std::pair<int, int> &x : c.din)
    {
        if (x.first == 2 || 64 / x.second != MAC_IN.width)
        {
            return nullptr;
        }
    }
    SnaxDatapathParams p;
    p.in_types = {MAC_IN, MAC_IN, MAC_OUT};
    p.op_type = p.out_type = MAC_OUT;
    p.lanes = LANES;
    p.seed = true;
    std::string why;
    auto g = std::unique_ptr<SnaxGroupDatapaths>(new SnaxGroupDatapaths());
    g->units.push_back(snax_datapath_new("Mac", p, &why));
    if (!g->units.back())
    {
        return nullptr;
    }
    g->wire(rule);
    return g;
}

// The rule of the case's group; "" or why it refuses the graph
static std::string configure(const Case &c, SnaxGroupRule &rule)
{
    std::vector<SnaxGroupRule::UnitCfg> cfgs;
    for (const UnitLine &u : c.units)
    {
        cfgs.push_back(u.cfg);
    }
    return rule.configure(cfgs, c.links);
}

static int run(const Case &c)
{
    SnaxGroupRule rule;
    std::vector<uint32_t> ts;
    for (const UnitLine &u : c.units)
    {
        ts.push_back(u.t);
    }
    std::string refused = configure(c, rule);
    if (!refused.empty())
    {
        printf("%s: the group is refused: %s\n", c.name.c_str(), refused.c_str());
        return 1;
    }
    size_t output = rule.output_unit();

    int errors = 0;
    size_t next_expect = 0;
    long run_busy = 0;
    std::unique_ptr<SnaxGroupDatapaths> data = dot_datapaths(c, rule);
    std::unique_ptr<SnaxGroupDatapaths> mac = mac_datapaths(c, rule);
    // the seeded Mac's: per lane its job's sum so far, and each job's sums when done
    std::vector<int64_t> job_sum(LANES, 0);
    std::vector<std::vector<int64_t>> job_sums;
    int head_fired = 0, pushed = 0;
    // Each job's sum: the head fires n / JOBS beats a job
    uint32_t per_job = c.jobs && ts.size() > 1 ? ts[0] * ts[1] : 0;
    const int lanes = c.lanes ? c.lanes : LANES;
    SnaxPacker packer;
    packer.d_out = c.dout;
    uint32_t results = 0, packed = 0;   // the run's results and the pushes into the packer
    std::vector<uint64_t> words;
    // Per sliced input: its unit, whether it is the unit's seed, its slicer, the words taken
    // from its reader, the slices popped from the word it holds, put back, and the last slice
    struct Sliced
    {
        size_t unit;
        bool seed;
        SnaxSlicer slicer;
        uint32_t taken = 0;
        uint64_t popped = 0;
        uint64_t slice = 0;
    };
    std::vector<Sliced> sliced;
    for (const std::pair<int, int> &x : c.din)
    {
        Sliced s;
        int at = 0;
        for (size_t k = 0; k < c.units.size(); k++)
        {
            if (x.first < at + c.units[k].inputs)
            {
                s.unit = k;
                s.seed = c.units[k].seed && x.first == at + c.units[k].inputs - 1;
                break;
            }
            at += c.units[k].inputs;
        }
        s.slicer.d_in = x.second;
        sliced.push_back(s);
    }
    // Word n of a sliced reader: every byte distinct
    auto reader_word = [](uint32_t n) { return 0x0706050403020100ull + n * 0x0808080808080808ull; };
    for (size_t t = 0; t < c.cycles.size(); t++)
    {
        int64_t cycle = t;
        const CycleLine &l = c.cycles[t];
        auto fail = [&](const std::string &why) {
            printf("%s: cycle %ld (line %d): %s\n", c.name.c_str(), (long)cycle, l.lineno,
                why.c_str());
            errors++;
        };
        if (cycle == c.start_cycle)
        {
            SnaxGroupRule::Start answer = rule.start(cycle, c.jobs, ts);
            if (answer == SnaxGroupRule::TAKEN)
            {
                run_busy = 0;
                results = rule.firings_per_run[output] / rule.job_beats[output];
                packed = 0;
                packer.clear();
                for (Sliced &s : sliced)
                {
                    s.slicer.clear();
                    s.taken = 0;
                }
            }
            if (c.start_result != tb_start_names[answer])
            {
                fail(std::string("start ") + tb_start_names[answer] + ", expected " + c.start_result);
            }
        }
        int busy = rule.busy(cycle);
        run_busy += l.busy;
        SnaxGroupRule::Step step;
        step.units.assign(c.units.size(), SnaxGroupRule::UnitStep());
        std::vector<int> took(sliced.size(), 0);
        if (busy)
        {
            // a sliced input's beat is its slicer's word, not its reader's valid
            std::vector<int> seen = l.valid;
            for (size_t j = 0; j < sliced.size(); j++)
            {
                seen[c.din[j].first] = sliced[j].slicer.full;
            }
            std::vector<bool> inputs, seeds;
            size_t at = 0;
            for (const UnitLine &u : c.units)
            {
                bool all = true;
                for (int i = 0; i < u.inputs - (int)u.seed; i++)
                {
                    all = all && seen[at++];
                }
                inputs.push_back(all);
                seeds.push_back(u.seed ? (bool)seen[at++] : true);
            }
            std::vector<bool> room(c.units.size(), true);
            bool last = packed + 1 == results;
            room[output] = packer.room(l.ready, last);
            step = rule.step(cycle, inputs, seeds, room);
            // NB (D180): pop on the unit's firing (a seed's take), then take the reader's word
            // when the slicer was empty or that was its last pop
            for (size_t j = 0; j < sliced.size(); j++)
            {
                Sliced &s = sliced[j];
                bool pop = s.seed ? step.units[s.unit].seed : step.units[s.unit].fire;
                bool open = s.slicer.open(pop);
                if (pop)
                {
                    int bits = 64 / s.slicer.d_in, at = s.slicer.count;
                    s.slice = s.slicer.pop();
                    s.popped = (at ? s.popped : 0) | s.slice << (bits * at);
                    if (at == s.slicer.d_in - 1 && s.popped != reader_word(s.taken - 1))
                    {
                        fail("input " + std::to_string(c.din[j].first) + ": its slices give " +
                            std::to_string(s.popped) + ", not the word taken " +
                            std::to_string(reader_word(s.taken - 1)));
                    }
                }
                if (open && l.valid[c.din[j].first])
                {
                    s.slicer.take(reader_word(s.taken++));
                    took[j] = 1;
                }
            }
            int sent = 0;
            if (step.units[output].push)
            {
                uint64_t word;
                sent = packer.push((uint64_t)(-(int64_t)(packed + 1)), last, &word);
                if (sent)
                {
                    words.push_back(word);
                }
                packed++;
            }
            if (c.dout > 1 && sent != l.sent)
            {
                fail("sent " + std::to_string(sent) + ", expected " + std::to_string(l.sent));
            }
            if (data)
            {
                std::vector<uint64_t> a(lanes), bb(lanes);
                for (int lane = 0; lane < lanes; lane++)
                {
                    size_t i = (size_t)head_fired * lanes + lane;
                    if (c.lanes)
                    {
                        // past the last beat the head does not fire: any words
                        a[lane] = i < c.a.size() ? (uint64_t)c.a[i] : 0;
                        bb[lane] = i < c.b.size() ? (uint64_t)c.b[i] : 0;
                    }
                    else
                    {
                        a[lane] = a_of(i);
                        bb[lane] = b_of(i);
                    }
                }
                const std::vector<uint64_t> &out = data->cycle(step, {{a.data(), bb.data()}, {}});
                head_fired += step.units[0].fire;
                if (step.units[output].push)
                {
                    int64_t want = 0;
                    if (c.lanes)
                    {
                        want = (size_t)pushed < c.sums.size() ? c.sums[pushed] : 0;
                    }
                    else
                    {
                        for (uint32_t i = pushed * per_job * LANES; i < (pushed + 1) * per_job * LANES; i++)
                        {
                            want += a_of(i) * b_of(i);
                        }
                    }
                    if ((int64_t)out[0] != want)
                    {
                        fail("result " + std::to_string(pushed) + " is " +
                            std::to_string((int64_t)out[0]) + ", the job's sum " +
                            std::to_string(want));
                    }
                    pushed++;
                }
            }
            if (mac)
            {
                // a and b of firing head_fired, the seed of its job; a broadcast input's beat
                // is its slice (one lane), given to all lanes as SnaxGroup does
                uint32_t job = head_fired / ts[0];
                std::vector<uint64_t> ab[2] = {{0}, {0}}, wide[2] = {{0}, {0}};
                std::vector<uint64_t> seed(snax_words(LANES, MAC_OUT), 0);
                for (int lane = 0; lane < LANES; lane++)
                {
                    int i = head_fired * LANES + lane;
                    snax_lane_set(ab[0].data(), MAC_IN.width, lane, a_of(i));
                    snax_lane_set(ab[1].data(), MAC_IN.width, lane, b_of(i));
                    snax_lane_set(seed.data(), MAC_OUT.width, lane, seed_of(job * LANES + lane));
                }
                std::vector<const uint64_t *> outer = {ab[0].data(), ab[1].data(), seed.data()};
                const uint64_t *one[2] = {nullptr, nullptr};     // a broadcast's slice
                for (size_t j = 0; j < sliced.size(); j++)
                {
                    int x = c.din[j].first;
                    snax_broadcast(&sliced[j].slice, LANES, MAC_IN, wide[x].data());
                    outer[x] = wide[x].data();
                    one[x] = &sliced[j].slice;
                }
                const std::vector<uint64_t> &out = mac->cycle(step, {outer});
                if (step.units[0].push)
                {
                    for (int lane = 0; lane < LANES; lane++)
                    {
                        int64_t got = (int64_t)snax_lane_cast(snax_lane_get(out.data(),
                            MAC_OUT.width, lane), MAC_OUT, {64, true});
                        int64_t sum = (size_t)pushed < job_sums.size() ? job_sums[pushed][lane]
                            : 0;
                        if (got != sum)
                        {
                            fail("result " + std::to_string(pushed) + " lane " +
                                std::to_string(lane) + " is " + std::to_string(got) +
                                ", its job's seed + products " + std::to_string(sum));
                        }
                    }
                    pushed++;
                }
                // the sum the tb works out itself: from the seed on a job's first firing
                if (step.units[0].fire)
                {
                    for (int lane = 0; lane < LANES; lane++)
                    {
                        int i = head_fired * LANES + lane;
                        int64_t v[2] = {a_of(i), b_of(i)};
                        for (int x = 0; x < 2; x++)
                        {
                            v[x] = one[x] ? (int8_t)(*one[x] & 0xff) : v[x];
                        }
                        job_sum[lane] = (head_fired % ts[0] ? job_sum[lane]
                            : seed_of(job * LANES + lane)) + v[0] * v[1];
                    }
                    if (head_fired % ts[0] == ts[0] - 1)
                    {
                        job_sums.push_back(job_sum);
                    }
                    head_fired++;
                }
            }
        }
        if (!c.din.empty() && took != l.took)
        {
            std::string got, want;
            for (size_t j = 0; j < took.size(); j++)
            {
                got += (j ? " " : "") + std::to_string(took[j]);
                want += (j ? " " : "") + std::to_string(l.took[j]);
            }
            fail("took " + got + ", expected " + want);
        }
        if (busy != l.busy)
        {
            fail("busy " + std::to_string(busy) + ", expected " + std::to_string(l.busy));
        }
        for (size_t k = 0; k < c.units.size(); k++)
        {
            if (step.units[k].fire != (bool)l.fire[k] || step.units[k].push != (bool)l.give[k])
            {
                fail(c.units[k].name + ": fire " + std::to_string(step.units[k].fire) + " give " +
                    std::to_string(step.units[k].push) + ", expected " +
                    std::to_string(l.fire[k]) + " " + std::to_string(l.give[k]));
            }
        }
        size_t b = 0;
        for (size_t k = 0; busy && k < c.links.size(); k++)
        {
            if (c.links[k].depth == 0)
            {
                continue;
            }
            if (step.links[k].occupancy != l.occupancy[b])
            {
                fail("buffer " + std::to_string(k) + ": occupancy " +
                    std::to_string(step.links[k].occupancy) + ", expected " +
                    std::to_string(l.occupancy[b]));
            }
            b++;
        }
        if (busy && step.end)
        {
            std::string got = rule.run_line();
            long bs, si, so, fl;
            if (sscanf(got.c_str(), "run index=%*d firings=%*u busy=%ld stall_in=%ld "
                    "stall_out=%ld flush=%ld", &bs, &si, &so, &fl) != 4 ||
                bs + si + so + fl != run_busy)
            {
                fail("\"" + got + "\" does not add up to the run's " + std::to_string(run_busy) +
                    " busy cycles");
            }
            if (next_expect >= c.expects.size() || got != c.expects[next_expect])
            {
                fail("\"" + got + "\", expected \"" + (next_expect < c.expects.size()
                    ? c.expects[next_expect] : std::string("none")) + "\"");
            }
            next_expect++;
        }
    }
    if (mac && pushed != (int)c.jobs)
    {
        printf("%s: %d result(s) pushed, %u jobs\n", c.name.c_str(), pushed, c.jobs);
        errors++;
    }
    if (data && c.lanes && (size_t)pushed != c.sums.size())
    {
        printf("%s: %d result(s) pushed, %zu sums in the case\n", c.name.c_str(), pushed,
            c.sums.size());
        errors++;
    }
    if (next_expect < c.expects.size())
    {
        printf("%s: %zu run line(s) expected, %zu given\n", c.name.c_str(), c.expects.size(),
            next_expect);
        errors++;
    }
    if (c.dout > 1 && words != c.words)
    {
        printf("%s: %zu word(s) sent, the case's %zu differ\n", c.name.c_str(), words.size(),
            c.words.size());
        for (size_t i = 0; i < words.size(); i++)
        {
            printf("  word %zu: 0x%016llx\n", i, (unsigned long long)words[i]);
        }
        errors++;
    }
    return errors;
}

int main(int argc, char **argv)
{
    return tb_main<Case>(argc, argv, parse, run, [](const Case &c) {
        SnaxGroupRule rule;
        bool data = configure(c, rule).empty() && (dot_datapaths(c, rule) ||
            mac_datapaths(c, rule));
        printf("%s: %zu units, %zu cycles, %zu run(s)%s\n", c.name.c_str(), c.units.size(),
            c.cycles.size(), c.expects.size(), data ? ", data" : "");
    });
}
