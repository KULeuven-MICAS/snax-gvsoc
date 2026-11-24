// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxGroupRule (snax/snax_group.hpp) against the shared group cases
// (README.md): each case gives the group (its units, head first, with their
// datapath, L, II, span, T and outer inputs; its links, the edges the rule
// takes, each into the input after its consumer's outer ones but its seed,
// which stays last, as SnaxGroup numbers a unit's inputs; its forks and outputs; a JOBS per output), the
// start and, per cycle, the outer inputs' valid (a forked input's once) and
// each outer output's ready, then per unit whether it fires and gives (pushes a result into its
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
// runs its datapath too: 4 lanes of int8 a and b into int32, its seed
// of 4 int32 lanes, each job's result seed + its products; a or b sliced to one
// lane a pop is a broadcast, each slice given to the 4 lanes by
// snax_broadcast, as SnaxGroup does. A fork case of bicg's one pass
// (vmul -> sum and mac, A forked to vmul.a and mac.a) runs its datapaths on 4
// lanes of int8 A, p and r into int32: each row's q = A p from the sum (its
// seed added when seeded) and s = A^T r from the Mac, r_i given to every
// lane (its seed added when seeded). A bank (rows R) with its b held,
// alone or as the fork's Mac, runs its datapath on r held a row: each
// result is the bank row its giving firing wrote, its sums worked out here;
// seeded, each row of a job starts from the seed beat its first firing
// took, int32 lanes seed_of(n * 4 + l) for the n-th beat taken.
//
//   tb CASE...
//
// Exit 1 on any difference.

#include <algorithm>
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
    std::vector<int> hold;  // the held ones among them
};

struct CycleLine
{
    std::vector<int> valid;     // the outer inputs', unit by unit, a forked one once
    std::vector<int> ready;     // each outer output's
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
    std::vector<std::vector<std::pair<int, int>>> forks;   // per fork, its (unit, input)s
    std::vector<int> outputs;           // the outputs' units, in the order of jobs and R
    std::vector<uint32_t> jobs = {1};   // one per output
    std::vector<std::vector<int>> place;    // per unit and outer input, its V column
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

// Each unit's outer inputs as V columns, unit by unit in port order, a forked input at its
// first member's (README.md); the number of columns
static int valid_columns(Case &c)
{
    c.place.assign(c.units.size(), {});
    int at = 0;
    for (size_t k = 0; k < c.units.size(); k++)
    {
        for (int i = 0; i < c.units[k].inputs; i++)
        {
            int col = -1;
            for (const std::vector<std::pair<int, int>> &f : c.forks)
            {
                for (size_t m = 1; m < f.size(); m++)
                {
                    if (f[m] == std::make_pair((int)k, i) && f[0].first < (int)k)
                    {
                        col = c.place[f[0].first][f[0].second];
                    }
                }
            }
            c.place[k].push_back(col >= 0 ? col : at++);
        }
    }
    return at;
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
                int nb_out = c.outputs.empty() ? 1 : c.outputs.size();
                ok = (int)head.size() == valid_columns(c) + nb_out;
                if (ok)
                {
                    l.valid.assign(head.begin(), head.end() - nb_out);
                    l.ready.assign(head.end() - nb_out, head.end());
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
            // unit NAME DATAPATH latency L ii N span S t T inputs I [seed 1] [rows R] [hold J]...
            UnitLine u;
            std::string k1, k2, k3, k4, k5, k6;
            ok = (bool)(ss >> u.name >> u.datapath >> k1 >> u.cfg.latency >> k2 >> u.cfg.ii >> k3
                >> u.cfg.span >> k4 >> u.t >> k5 >> u.inputs) && k1 == "latency" && k2 == "ii" &&
                k3 == "span" && k4 == "t" && k5 == "inputs" && snax_datapaths().count(u.datapath);
            int seeded = 0;
            while (ok && ss >> k6)
            {
                int x = 0;
                ok = (bool)(ss >> x);
                if (k6 == "seed")
                {
                    seeded = x;
                    ok = ok && (seeded == 0 || seeded == 1) && (!seeded || u.inputs >= 1);
                }
                else if (k6 == "rows")
                {
                    u.cfg.rows = x;
                    ok = ok && x >= 1;
                }
                else if (k6 == "hold")
                {
                    u.hold.push_back(x);
                    ok = ok && x >= 0 && x < u.inputs;
                }
                else
                {
                    ok = false;
                }
            }
            u.seed = seeded;
            u.cfg.seeded = seeded;
            u.cfg.held = !u.hold.empty();
            ok = ok && (u.hold.empty() || u.cfg.rows > 1);
            for (int j : u.hold)
            {
                ok = ok && !(u.seed && j == u.inputs - 1);
            }
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
                e.to_input = c.units[e.to].inputs - (int)c.units[e.to].seed;
                e.depth = depth;
                c.links.push_back(e);
            }
        }
        else if (key == "jobs")
        {
            // jobs J...: one per output
            uint32_t j;
            c.jobs.clear();
            while (ss >> j)
            {
                c.jobs.push_back(j);
            }
            ok = ss.eof() && !c.jobs.empty();
        }
        else if (key == "fork")
        {
            // fork U.I U.I ...: outer input I of each unit U, one reader's
            std::string member;
            std::vector<std::pair<int, int>> f;
            while (ok && ss >> member)
            {
                size_t dot = member.find('.');
                int k = -1;
                for (size_t x = 0; dot != std::string::npos && x < c.units.size(); x++)
                {
                    k = c.units[x].name == member.substr(0, dot) ? (int)x : k;
                }
                int i = k >= 0 ? atoi(member.c_str() + dot + 1) : -1;
                ok = k >= 0 && i >= 0 && i < c.units[k].inputs;
                f.push_back({k, i});
            }
            ok = ok && f.size() >= 2;
            c.forks.push_back(f);
        }
        else if (key == "outputs")
        {
            // outputs U...: the sinks, in the order of jobs and the R columns
            std::string name;
            while (ok && ss >> name)
            {
                int k = -1;
                for (size_t x = 0; x < c.units.size(); x++)
                {
                    k = c.units[x].name == name ? (int)x : k;
                }
                ok = k >= 0;
                c.outputs.push_back(k);
            }
            ok = ok && !c.outputs.empty();
        }
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
            int i, d, nb_in = valid_columns(c);
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
    valid_columns(c);
    size_t nb_out = c.outputs.empty() ? 1 : c.outputs.size();
    if (c.jobs.size() != nb_out)
    {
        fprintf(stderr, "%s: %zu jobs, one per output (%zu)\n", path.c_str(), c.jobs.size(),
            nb_out);
        return false;
    }
    if ((c.lanes || !c.a.empty() || !c.b.empty() || !c.sums.empty()) &&
        (!c.lanes || c.a.size() != c.b.size() || c.a.size() % c.lanes || c.sums.size() != c.jobs[0]))
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
        c.units[0].inputs != 3 || c.units[0].cfg.rows > 1 || !c.links.empty() || c.lanes)
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

// bicg's one pass: 4 lanes of int8 A, p and r into int32, the sum's seed one int32
// a row, the Mac's 4 int32 lanes once
static const SnaxType I8 = {8, true}, I32 = {32, true};

static int64_t p_of(int l) { return (l * 3) % 7 - 3; }
static int64_t r_of(int i) { return (i * 5) % 9 - 4; }

// The fork shape: vmul (SimdLanes, a b) -> sum (TreeAccumulate, seeded or not) and mac (Mac,
// a b, seeded or not), A forked to vmul.a and mac.a: its datapaths; nullptr when the case is
// not one
static std::unique_ptr<SnaxGroupDatapaths> fork_datapaths(const Case &c, const SnaxGroupRule &rule)
{
    std::vector<std::pair<int, int>> a = {{0, 0}, {2, 0}};
    if (c.units.size() != 3 || c.units[0].datapath != "SimdLanes" || c.units[0].inputs != 2 ||
        c.units[1].datapath != "TreeAccumulate" || c.units[1].inputs != (int)c.units[1].seed ||
        c.units[2].datapath != "Mac" || c.units[2].inputs != 2 + (int)c.units[2].seed ||
        c.links.size() != 1 || c.links[0].from != 0 || c.links[0].to != 1 ||
        c.forks.size() != 1 || c.forks[0] != a || !c.din.empty() || c.dout != 1)
    {
        return nullptr;
    }
    auto g = std::unique_ptr<SnaxGroupDatapaths>(new SnaxGroupDatapaths());
    SnaxDatapathParams p[3];
    p[0].in_types = {I8, I8};
    p[0].op = SNAX_OP_MUL;
    p[1].in_types = {I32};
    p[2].in_types = {I8, I8};
    for (int k = 0; k < 3; k++)
    {
        p[k].lanes = LANES;
        p[k].op_type = p[k].out_type = I32;
        p[k].seed = c.units[k].seed;
        p[k].rows = c.units[k].cfg.rows;
        if (p[k].seed)
        {
            p[k].in_types.push_back(I32);
        }
        std::string why;
        g->units.push_back(snax_datapath_new(c.units[k].datapath, p[k], &why));
        if (!g->units.back())
        {
            return nullptr;
        }
    }
    SnaxDatapathParams b;
    b.in_types = {I32};
    b.out_type = I32;
    b.lanes = LANES;
    b.depth = c.links[0].depth;
    std::string why;
    g->buffers.push_back(b.depth ? snax_datapath_new("LinkBuffer", b, &why) : nullptr);
    g->wire(rule);
    return g;
}

// A bank's sums as the tb works them out, R rows of LANES int32 lanes, and its
// held r, r_of(n) for the n-th row taken: a firing adds a * r into row fired mod R,
// starting it on its job's first R firings (seeded, from the seed beat taken then:
// seed_of(n * LANES + l) for the n-th); a result is the row the last firing wrote
struct BankModel
{
    int rows = 1;
    uint32_t t = 1;
    bool seeded = false;
    uint32_t fired = 0, taken = 0, seeds = 0;
    int last = 0;
    int64_t r = 0;
    std::vector<std::vector<int64_t>> s;

    BankModel(int rows, uint32_t t, bool seeded) : rows(rows), t(t), seeded(seeded),
        s(rows, std::vector<int64_t>(LANES, 0)) {}

    // the seed beat the next seeded firing takes, its int32 lanes
    std::vector<uint64_t> seed_beat() const
    {
        std::vector<uint64_t> w(snax_words(LANES, {32, true}), 0);
        for (int lane = 0; lane < LANES; lane++)
        {
            snax_lane_set(w.data(), 32, lane, seed_of(this->seeds * LANES + lane));
        }
        return w;
    }

    // r for this cycle: taken anew on a row's first firing
    int64_t held(bool take)
    {
        return take ? r_of(this->taken) : this->r;
    }

    void fire(bool take, const std::vector<int64_t> &a)
    {
        if (take)
        {
            this->r = r_of(this->taken++);
        }
        int row = this->fired % this->rows;
        bool first = this->fired % this->t < (uint32_t)this->rows;
        for (int lane = 0; lane < LANES; lane++)
        {
            int64_t from = !first ? this->s[row][lane] : this->seeded
                ? seed_of(this->seeds * LANES + lane) : 0;
            this->s[row][lane] = from + a[lane] * this->r;
        }
        this->seeds += first && this->seeded;
        this->last = row;
        this->fired++;
    }
};

// A banked Mac alone (rows above 1, b held, seeded or not, nothing sliced): its datapath;
// nullptr when the case is not one
static std::unique_ptr<SnaxGroupDatapaths> bank_datapaths(const Case &c, const SnaxGroupRule &rule)
{
    if (c.units.size() != 1 || c.units[0].datapath != "Mac" || c.units[0].cfg.rows < 2 ||
        c.units[0].inputs != 2 + (int)c.units[0].seed || c.units[0].hold != std::vector<int>{1} ||
        !c.links.empty() || c.lanes || !c.din.empty() || c.dout != 1)
    {
        return nullptr;
    }
    SnaxDatapathParams p;
    p.in_types = {I8, I8};
    p.op_type = p.out_type = I32;
    p.lanes = LANES;
    p.rows = c.units[0].cfg.rows;
    p.seed = c.units[0].seed;
    if (p.seed)
    {
        p.in_types.push_back(I32);
    }
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

// A bank's result against the model: false, with why, on a lane that differs
static bool bank_result(const BankModel &m, const std::vector<uint64_t> &out, std::string *why)
{
    for (int lane = 0; lane < LANES; lane++)
    {
        int64_t got = (int64_t)snax_lane_cast(snax_lane_get(out.data(), I32.width, lane), I32,
            {64, true});
        if (got != m.s[m.last][lane])
        {
            *why = "row " + std::to_string(m.last) + " lane " + std::to_string(lane) + " is " +
                std::to_string(got) + ", the bank's sum " + std::to_string(m.s[m.last][lane]);
            return false;
        }
    }
    return true;
}

// The rule of the case's group; "" or why it refuses the graph
static std::string configure(const Case &c, SnaxGroupRule &rule)
{
    std::vector<SnaxGroupRule::UnitCfg> cfgs;
    for (const UnitLine &u : c.units)
    {
        cfgs.push_back(u.cfg);
    }
    std::vector<std::vector<int>> forks;
    for (const std::vector<std::pair<int, int>> &f : c.forks)
    {
        forks.emplace_back();
        for (const std::pair<int, int> &m : f)
        {
            forks.back().push_back(m.first);
        }
    }
    return rule.configure(cfgs, c.links, c.outputs, forks);
}

static int run(const Case &c)
{
    SnaxGroupRule rule;
    std::vector<uint32_t> ts, rows_of;
    for (const UnitLine &u : c.units)
    {
        ts.push_back(u.t);
        rows_of.push_back(u.cfg.rows);
    }
    std::string refused = configure(c, rule);
    if (!refused.empty())
    {
        printf("%s: the group is refused: %s\n", c.name.c_str(), refused.c_str());
        return 1;
    }
    size_t output = rule.output_unit();
    const std::vector<int> &outputs = rule.output_units();
    const uint32_t jobs = c.jobs[0];

    int errors = 0;
    size_t next_expect = 0;
    long run_busy = 0;
    std::unique_ptr<SnaxGroupDatapaths> data = dot_datapaths(c, rule);
    std::unique_ptr<SnaxGroupDatapaths> mac = mac_datapaths(c, rule);
    std::unique_ptr<SnaxGroupDatapaths> forked = fork_datapaths(c, rule);
    std::unique_ptr<SnaxGroupDatapaths> banked = bank_datapaths(c, rule);
    // the fork's: the rows fired, the sum's seeds taken, the Mac's sums so far and its pushes
    int rows = 0, q_pushed = 0, s_pushed = 0, q_seeded = 0;
    std::vector<int64_t> s_sum(LANES, 0);
    // a bank's (the Mac alone's, or the fork's Mac's): its sums and held r
    const UnitLine &bank_unit = c.units.back();
    BankModel bank(bank_unit.cfg.rows, bank_unit.t, bank_unit.seed);
    int bank_pushed = 0;
    // the seeded Mac's: per lane its job's sum so far, and each job's sums when done
    std::vector<int64_t> job_sum(LANES, 0);
    std::vector<std::vector<int64_t>> job_sums;
    int head_fired = 0, pushed = 0;
    // Each job's sum: the head fires n / JOBS beats a job
    uint32_t per_job = jobs && ts.size() > 1 ? ts[0] * ts[1] : 0;
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
        bool hold;
        SnaxSlicer slicer;
        uint32_t taken = 0;
        uint64_t popped = 0;
        uint64_t slice = 0;
    };
    std::vector<Sliced> sliced;
    for (const std::pair<int, int> &x : c.din)
    {
        Sliced s;
        bool found = false;
        for (size_t k = 0; !found && k < c.units.size(); k++)
        {
            for (int i = 0; !found && i < c.units[k].inputs; i++)
            {
                if (c.place[k][i] == x.first)
                {
                    s.unit = k;
                    s.seed = c.units[k].seed && i == c.units[k].inputs - 1;
                    s.hold = std::find(c.units[k].hold.begin(), c.units[k].hold.end(), i) !=
                        c.units[k].hold.end();
                    found = true;
                }
            }
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
            SnaxGroupRule::Start answer = rule.start(cycle, c.jobs, ts, rows_of);
            if (answer == SnaxGroupRule::TAKEN)
            {
                run_busy = 0;
                results = rule.firings_per_run[output] / rule.job_beats[output] *
                    rule.rows[output];
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
            std::vector<bool> inputs, seeds, holds;
            for (size_t k = 0; k < c.units.size(); k++)
            {
                const UnitLine &u = c.units[k];
                bool all = true, kept = true;
                for (int i = 0; i < u.inputs - (int)u.seed; i++)
                {
                    bool held = std::find(u.hold.begin(), u.hold.end(), i) != u.hold.end();
                    (held ? kept : all) = (held ? kept : all) && seen[c.place[k][i]];
                }
                inputs.push_back(all);
                seeds.push_back(u.seed ? (bool)seen[c.place[k][u.inputs - 1]] : true);
                holds.push_back(kept);
            }
            std::vector<bool> room(c.units.size(), true);
            bool last = packed + 1 == results;
            for (size_t o = 0; o < outputs.size(); o++)
            {
                room[outputs[o]] = l.ready[o];
            }
            room[output] = packer.room(l.ready[0], last);
            step = rule.step(cycle, inputs, seeds, holds, room);
            // NB (D180): pop on the unit's firing (a seed's take), then take the reader's word
            // when the slicer was empty or that was its last pop
            for (size_t j = 0; j < sliced.size(); j++)
            {
                Sliced &s = sliced[j];
                bool pop = s.seed ? step.units[s.unit].seed : s.hold ? step.units[s.unit].take
                    : step.units[s.unit].fire;
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
        if (busy && banked)
        {
            // row f / ROWS of A on a (a_of), r held a row on every lane of b
            std::vector<uint64_t> A(1, 0), R(1, 0);
            std::vector<int64_t> a(LANES);
            int64_t r = bank.held(step.units[0].take);
            for (int lane = 0; lane < LANES; lane++)
            {
                a[lane] = a_of(bank.fired * LANES + lane);
                snax_lane_set(A.data(), I8.width, lane, a[lane]);
                snax_lane_set(R.data(), I8.width, lane, r);
            }
            std::vector<uint64_t> seed = bank.seed_beat();
            std::vector<const uint64_t *> outer = {A.data(), R.data()};
            if (bank.seeded)
            {
                outer.push_back(seed.data());
            }
            banked->cycle(step, {outer});
            std::string why;
            if (step.units[0].push && !bank_result(bank, banked->out(0), &why))
            {
                fail(why);
            }
            bank_pushed += step.units[0].push;
            if (step.units[0].fire)
            {
                bank.fire(step.units[0].take, a);
            }
        }
        if (busy && forked)
        {
            // row i of A on vmul.a and mac.a, p on vmul.b, r_i on every lane of mac.b
            std::vector<uint64_t> A(1, 0), P(1, 0), R(1, 0);
            std::vector<uint64_t> q_seed(1, 0), s_seed(snax_words(LANES, I32), 0);
            for (int lane = 0; lane < LANES; lane++)
            {
                snax_lane_set(A.data(), I8.width, lane, a_of(rows * LANES + lane));
                snax_lane_set(P.data(), I8.width, lane, p_of(lane));
                snax_lane_set(R.data(), I8.width, lane, bank.rows > 1
                    ? bank.held(step.units[2].take) : r_of(rows));
                snax_lane_set(s_seed.data(), I32.width, lane, seed_of(lane));
            }
            snax_lane_set(q_seed.data(), I32.width, 0, seed_of(100 + q_seeded));
            std::vector<std::vector<const uint64_t *>> outer = {{A.data(), P.data()}, {},
                {A.data(), R.data()}};
            if (c.units[1].seed)
            {
                outer[1].push_back(q_seed.data());
            }
            std::vector<uint64_t> bank_seed = bank.seed_beat();
            if (c.units[2].seed)
            {
                outer[2].push_back(bank.rows > 1 ? bank_seed.data() : s_seed.data());
            }
            forked->cycle(step, outer);
            if (step.units[0].fire != step.units[2].fire)
            {
                fail("vmul and mac fire apart on their forked input");
            }
            q_seeded += step.units[1].seed;
            if (step.units[1].push)
            {
                // q's partial over its T rows of A
                int64_t want = c.units[1].seed ? seed_of(100 + q_pushed) : 0;
                for (uint32_t f = q_pushed * ts[1]; f < (q_pushed + 1) * ts[1]; f++)
                {
                    for (int lane = 0; lane < LANES; lane++)
                    {
                        want += a_of(f * LANES + lane) * p_of(lane);
                    }
                }
                int64_t got = (int64_t)snax_lane_cast(snax_lane_get(forked->out(1).data(),
                    I32.width, 0), I32, {64, true});
                if (got != want)
                {
                    fail("q[" + std::to_string(q_pushed) + "] is " + std::to_string(got) +
                        ", (A p)[" + std::to_string(q_pushed) + "] " + std::to_string(want));
                }
                q_pushed++;
            }
            std::string why;
            if (step.units[2].push && bank.rows > 1 && !bank_result(bank, forked->out(2), &why))
            {
                fail("s: " + why);
            }
            if (step.units[2].push && bank.rows > 1)
            {
                s_pushed++;
            }
            if (step.units[2].fire && bank.rows > 1)
            {
                std::vector<int64_t> a(LANES);
                for (int lane = 0; lane < LANES; lane++)
                {
                    a[lane] = a_of(rows * LANES + lane);
                }
                bank.fire(step.units[2].take, a);
            }
            if (step.units[2].push && bank.rows == 1)
            {
                for (int lane = 0; lane < LANES; lane++)
                {
                    int64_t got = (int64_t)snax_lane_cast(snax_lane_get(forked->out(2).data(),
                        I32.width, lane), I32, {64, true});
                    if (got != s_sum[lane])
                    {
                        fail("s[" + std::to_string(lane) + "] is " + std::to_string(got) +
                            ", (A^T r)[" + std::to_string(lane) + "] " +
                            std::to_string(s_sum[lane]));
                    }
                }
                s_pushed++;
            }
            if (step.units[2].fire && bank.rows == 1)
            {
                for (int lane = 0; lane < LANES; lane++)
                {
                    s_sum[lane] = (rows % ts[2] ? s_sum[lane] : c.units[2].seed ? seed_of(lane)
                        : 0) + a_of(rows * LANES + lane) * r_of(rows);
                }
            }
            rows += step.units[0].fire;
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
    if (mac && pushed != (int)jobs)
    {
        printf("%s: %d result(s) pushed, %u jobs\n", c.name.c_str(), pushed, jobs);
        errors++;
    }
    if (banked && bank_pushed != (int)(jobs * bank.rows))
    {
        printf("%s: %d result(s) pushed, %u jobs of %d rows\n", c.name.c_str(), bank_pushed,
            jobs, bank.rows);
        errors++;
    }
    if (forked && (q_pushed != (int)c.jobs[0] || s_pushed != (int)c.jobs[1] * bank.rows))
    {
        printf("%s: %d q and %d s result(s) pushed, jobs %u and %u\n", c.name.c_str(), q_pushed,
            s_pushed, c.jobs[0], c.jobs[1]);
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
            mac_datapaths(c, rule) || fork_datapaths(c, rule) || bank_datapaths(c, rule));
        printf("%s: %zu units, %zu cycles, %zu run(s)%s\n", c.name.c_str(), c.units.size(),
            c.cycles.size(), c.expects.size(), data ? ", data" : "");
    });
}
