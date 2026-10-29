// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxGroupRule (snax/snax_group.hpp) against the shared group cases
// (README.md): each case gives the group (its units, head first, with their
// datapath, L, II, span, T and outer inputs; its links' depths; JOBS), the
// start and, per cycle, the outer inputs' valid and the outer output's
// ready, then per unit whether it fires and gives (pushes a result into its
// link or the outer output), per buffer its occupancy after the cycle, and
// whether the group is busy. The tb steps the rule with them and compares
// every cycle and the run line at the end of each run, whose classes must add
// up to the run's busy cycles in the file. It also runs the group's datapaths
// with the rule's enables (snax_group.hpp's SnaxGroupDatapaths, as the
// component does) on a dot product of int64 at 4 lanes, beat i of a and b the
// head's i-th firing's, and checks each result the last unit pushes against
// the sum of its job's products.
//
//   tb CASE...
//
// Exit 1 on any difference.

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "snax_datapath.hpp"
#include "snax_group.hpp"


struct UnitLine
{
    std::string name, datapath;
    SnaxGroupRule::UnitCfg cfg;
    uint32_t t = 1;
    int inputs = 0;     // outer inputs
};

struct CycleLine
{
    std::vector<int> valid;     // the outer inputs', unit by unit
    int ready = 1;
    std::vector<int> fire, give;    // per unit
    std::vector<int> occupancy;     // per buffer
    int busy = 0;
    int lineno = 0;
};

struct Case
{
    std::string name;
    std::vector<UnitLine> units;
    std::vector<int> depths;
    uint32_t jobs = 1;
    int64_t start_cycle = -1;
    std::string start_result;
    std::vector<std::string> expects;
    std::vector<CycleLine> cycles;
};

static std::string base_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    std::string base = slash == std::string::npos ? path : path.substr(slash + 1);
    size_t dot = base.rfind('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
}

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
    c.name = base_of(path);
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
            for (int d : c.depths)
            {
                buffers += d > 0;
            }
            size_t want = 2 + c.units.size() + (buffers ? 1 : 0);
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
                std::vector<int> busy = ints(cols.back());
                ok = ok && busy.size() == 1;
                l.busy = ok ? busy[0] : 0;
            }
            c.cycles.push_back(l);
        }
        else if (key == "unit")
        {
            // unit NAME DATAPATH latency L ii N span S t T inputs I
            UnitLine u;
            std::string k1, k2, k3, k4, k5;
            ok = (bool)(ss >> u.name >> u.datapath >> k1 >> u.cfg.latency >> k2 >> u.cfg.ii >> k3
                >> u.cfg.span >> k4 >> u.t >> k5 >> u.inputs) && k1 == "latency" && k2 == "ii" &&
                k3 == "span" && k4 == "t" && k5 == "inputs" && snax_datapaths().count(u.datapath);
            c.units.push_back(u);
        }
        else if (key == "link")
        {
            // link FROM TO depth D
            std::string from, to, k1;
            int depth;
            ok = (bool)(ss >> from >> to >> k1 >> depth) && k1 == "depth" && depth >= 0 &&
                c.units.size() >= c.depths.size() + 2 &&
                from == c.units[c.depths.size()].name && to == c.units[c.depths.size() + 1].name;
            c.depths.push_back(depth);
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
        else if (key == "cycles") { in_cycles = true; }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    if (c.units.empty() || c.depths.size() + 1 != c.units.size())
    {
        fprintf(stderr, "%s: %zu units and %zu links: a chain has one link fewer\n",
            path.c_str(), c.units.size(), c.depths.size());
        return false;
    }
    return true;
}

static const char *start_names[] = {"taken", "ignored", "refused"};

// The dot product the data check runs: 4 lanes of int64, a head of two outer inputs
static const int LANES = 4;

static int64_t a_of(int i) { return (i * 7) % 13 - 6; }
static int64_t b_of(int i) { return (i * 5) % 11 - 5; }

// The group's datapaths for the dot shape: the head's two inputs a and b, the next unit's
// one the link; nullptr when the case is not a dot (no data check then)
static std::unique_ptr<SnaxGroupDatapaths> dot_datapaths(const Case &c)
{
    const SnaxUnitType i64 = {64, true};
    if (c.units.size() != 2 || c.units[0].inputs != 2 || c.units[1].inputs != 0)
    {
        return nullptr;
    }
    auto g = std::unique_ptr<SnaxGroupDatapaths>(new SnaxGroupDatapaths());
    for (size_t k = 0; k < c.units.size(); k++)
    {
        SnaxDatapathParams p;
        p.in_types.assign(k == 0 ? 2 : 1, i64);
        p.lanes = LANES;
        p.op = c.units[k].datapath == "ElementwiseLanes" ? UNIT_MUL : UNIT_ADD;
        std::string why;
        g->units.push_back(snax_datapath_new(c.units[k].datapath, p, &why));
        if (!g->units.back())
        {
            return nullptr;
        }
        g->linked.push_back(k == 0 ? -1 : 0);
    }
    SnaxDatapathParams p;
    p.in_types = {i64};
    p.lanes = LANES;
    p.depth = c.depths[0];
    std::string why;
    g->buffers.push_back(c.depths[0] ? snax_datapath_new("LinkBuffer", p, &why) : nullptr);
    return g;
}

static int run(const Case &c)
{
    SnaxGroupRule rule;
    std::vector<SnaxGroupRule::UnitCfg> cfgs;
    std::vector<uint32_t> ts;
    for (const UnitLine &u : c.units)
    {
        cfgs.push_back(u.cfg);
        ts.push_back(u.t);
    }
    rule.configure(cfgs, c.depths);

    int errors = 0;
    size_t next_expect = 0;
    long run_busy = 0;
    std::unique_ptr<SnaxGroupDatapaths> data = dot_datapaths(c);
    int head_fired = 0, pushed = 0;
    // Each job's sum: the head fires n / JOBS beats a job
    uint32_t per_job = c.jobs ? ts[0] * ts[1] : 0;
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
            }
            if (c.start_result != start_names[answer])
            {
                fail(std::string("start ") + start_names[answer] + ", expected " + c.start_result);
            }
        }
        int busy = rule.busy(cycle);
        run_busy += l.busy;
        SnaxGroupRule::Step step;
        step.units.assign(c.units.size(), SnaxGroupRule::UnitStep());
        if (busy)
        {
            std::vector<bool> inputs;
            size_t at = 0;
            for (const UnitLine &u : c.units)
            {
                bool all = true;
                for (int i = 0; i < u.inputs; i++)
                {
                    all = all && l.valid[at++];
                }
                inputs.push_back(all);
            }
            step = rule.step(cycle, inputs, l.ready);
            if (data)
            {
                std::vector<uint64_t> a(LANES), bb(LANES);
                for (int lane = 0; lane < LANES; lane++)
                {
                    a[lane] = a_of(head_fired * LANES + lane);
                    bb[lane] = b_of(head_fired * LANES + lane);
                }
                const std::vector<uint64_t> &out = data->cycle(step, {{a.data(), bb.data()}, {}});
                head_fired += step.units[0].fire;
                if (step.units.back().push)
                {
                    int64_t want = 0;
                    for (uint32_t i = pushed * per_job * LANES; i < (pushed + 1) * per_job * LANES; i++)
                    {
                        want += a_of(i) * b_of(i);
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
        for (size_t k = 0; busy && k < c.depths.size(); k++)
        {
            if (c.depths[k] == 0)
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
    if (next_expect < c.expects.size())
    {
        printf("%s: %zu run line(s) expected, %zu given\n", c.name.c_str(), c.expects.size(),
            next_expect);
        errors++;
    }
    return errors;
}

int main(int argc, char **argv)
{
    if (argc < 2)
    {
        fprintf(stderr, "usage: %s CASE...\n", argv[0]);
        return 2;
    }
    int failed = 0, passed = 0;
    for (int i = 1; i < argc; i++)
    {
        Case c;
        if (!parse(argv[i], c))
        {
            return 2;
        }
        int errors = run(c);
        printf("%s %s: %zu units, %zu cycles, %zu run(s)%s\n", errors ? "FAIL" : "PASS",
            c.name.c_str(), c.units.size(), c.cycles.size(), c.expects.size(),
            dot_datapaths(c) ? ", data" : "");
        failed += errors != 0;
        passed += errors == 0;
    }
    printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
