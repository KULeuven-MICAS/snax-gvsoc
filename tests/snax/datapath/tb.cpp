// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// The datapath classes of snax/snax_datapath.hpp against NumPy's vectors
// (README.md, vectors.txt written by gen.py): per test a datapath built from
// the registry by its catalogue name and params, then per step the enables
// and the inputs; eval's output must be the step's expected lanes, then
// commit clocks it. Also checks the registry: every catalogue name builds,
// an unknown one and a Mac of the wrong shape are refused.
//
//   tb VECTORS
//
// Exit 1 on any difference.

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "snax_datapath.hpp"


static bool type_of(const std::string &name, SnaxType &t)
{
    for (int width : {8, 16, 32, 64})
    {
        for (bool is_signed : {true, false})
        {
            if (name == snax_type_name({width, is_signed}))
            {
                t = {width, is_signed};
                return true;
            }
        }
    }
    return false;
}

struct Step
{
    SnaxEnables en;
    std::vector<std::vector<int64_t>> in;   // per input, its lanes
    std::vector<int64_t> out;
};

struct Test
{
    std::string name, datapath;
    SnaxDatapathParams p;
    std::vector<Step> steps;
};

static std::vector<int64_t> numbers(const std::string &text)
{
    std::istringstream ss(text);
    std::vector<int64_t> v;
    std::string token;
    while (ss >> token)
    {
        v.push_back(std::strtoll(token.c_str(), nullptr, 0));
    }
    return v;
}

static bool parse(const std::string &path, std::vector<Test> &tests)
{
    std::ifstream in(path);
    if (!in)
    {
        fprintf(stderr, "%s: cannot open\n", path.c_str());
        return false;
    }
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
        if (key == "test")
        {
            tests.emplace_back();
            ok = (bool)(ss >> tests.back().name);
        }
        else if (tests.empty()) { ok = false; }
        else if (key == "datapath") { ok = (bool)(ss >> tests.back().datapath); }
        else if (key == "in")
        {
            std::string name;
            SnaxType t;
            while (ok && ss >> name)
            {
                ok = type_of(name, t);
                tests.back().p.in_types.push_back(t);
            }
        }
        else if (key == "optype" || key == "out")
        {
            std::string name;
            ok = (bool)(ss >> name) && type_of(name, key == "out" ? tests.back().p.out_type
                : tests.back().p.op_type);
        }
        else if (key == "lanes") { ok = (bool)(ss >> tests.back().p.lanes); }
        else if (key == "depth") { ok = (bool)(ss >> tests.back().p.depth); }
        else if (key == "accumulate") { int v; ok = (bool)(ss >> v); tests.back().p.accumulate = v; }
        else if (key == "regOut") { int v; ok = (bool)(ss >> v); tests.back().p.reg_out = v; }
        else if (key == "op")
        {
            std::string name;
            ok = (bool)(ss >> name);
            tests.back().p.op = -1;
            for (int op = 0; op < SNAX_NB_OPS; op++)
            {
                tests.back().p.op = name == snax_op_names[op] ? op : tests.back().p.op;
            }
            ok = ok && tests.back().p.op != -1;
        }
        else if (key == "step")
        {
            // step FIRE FIRST READ LANE EN LOAD WSLOT RSLOT : IN0 ; IN1 ... => OUT
            Step s;
            int fire, first, read, en, load;
            ok = (bool)(ss >> fire >> first >> read >> s.en.lane >> en >> load >> s.en.wslot
                >> s.en.rslot);
            s.en.fire = fire, s.en.first = first, s.en.read = read, s.en.en = en,
                s.en.load = load;
            size_t colon = line.find(':'), arrow = line.find("=>");
            ok = ok && colon != std::string::npos && arrow != std::string::npos;
            if (ok)
            {
                std::string ins = line.substr(colon + 1, arrow - colon - 1);
                size_t at = 0;
                while (true)
                {
                    size_t semi = ins.find(';', at);
                    s.in.push_back(numbers(ins.substr(at, semi == std::string::npos
                        ? std::string::npos : semi - at)));
                    if (semi == std::string::npos)
                    {
                        break;
                    }
                    at = semi + 1;
                }
                s.out = numbers(line.substr(arrow + 2));
            }
            tests.back().steps.push_back(s);
        }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    return true;
}

// A beat's words from its lanes, each of type t
static std::vector<uint64_t> words(const std::vector<int64_t> &lanes, SnaxType t)
{
    std::vector<uint64_t> w((lanes.size() * t.width + 63) / 64, 0);
    for (size_t l = 0; l < lanes.size(); l++)
    {
        snax_lane_set(w.data(), t.width, l, (uint64_t)lanes[l]);
    }
    return w;
}

static int run(const Test &t)
{
    std::string why;
    std::unique_ptr<SnaxDatapath> dp = snax_datapath_new(t.datapath, t.p, &why);
    if (!dp)
    {
        printf("%s: %s refused: %s\n", t.name.c_str(), t.datapath.c_str(), why.c_str());
        return 1;
    }
    int errors = 0;
    for (size_t k = 0; k < t.steps.size(); k++)
    {
        const Step &s = t.steps[k];
        std::vector<std::vector<uint64_t>> beats;
        for (size_t i = 0; i < s.in.size(); i++)
        {
            beats.push_back(words(s.in[i], t.p.in_types[i]));
            beats.back().resize(std::max<size_t>(beats.back().size(), dp->in_words[i]), 0);
        }
        std::vector<const uint64_t *> in;
        for (const auto &b : beats)
        {
            in.push_back(b.data());
        }
        dp->eval(in, s.en);
        int out_lanes = dp->out_words * 64 / t.p.out_type.width;
        out_lanes = (int)s.out.size() < out_lanes ? (int)s.out.size() : out_lanes;
        if ((int)s.out.size() != out_lanes)
        {
            printf("%s: step %zu: %zu output lanes expected, the datapath has %d\n",
                t.name.c_str(), k, s.out.size(), out_lanes);
            errors++;
        }
        for (int l = 0; l < out_lanes; l++)
        {
            uint64_t got = snax_lane_get(dp->out().data(), t.p.out_type.width, l);
            uint64_t want = (uint64_t)s.out[l] & snax_lane_mask(t.p.out_type.width);
            if (got != want)
            {
                printf("%s: step %zu: lane %d is 0x%lx, expected 0x%lx\n", t.name.c_str(), k, l,
                    (unsigned long)got, (unsigned long)want);
                errors++;
            }
        }
        dp->commit(s.en);
    }
    return errors;
}

// The registry: each catalogue name builds; the wrong shapes are refused
static int check_registry(int *count)
{
    const SnaxType i64 = {64, true};
    struct Case { const char *name; SnaxDatapathParams p; bool builds; int latency, span; };
    SnaxDatapathParams two, one, plain, plain_bad, serial, link;
    two.in_types = {i64, i64};
    one.in_types = {i64};
    plain.in_types = {i64, i64, i64};
    plain.accumulate = false;
    plain.reg_out = true;
    plain_bad = plain;
    plain_bad.in_types[2] = {32, true};
    serial.in_types = {i64};
    serial.lanes = 4;
    link.in_types = {i64};
    link.depth = 2;
    std::vector<Case> cases = {
        {"ElementwiseLanes", two, true, 0, 1}, {"TreeAccumulate", one, true, 1, 1},
        {"Mac", two, true, 1, 1}, {"Mac", plain, true, 1, 1}, {"Mac", plain_bad, false, 0, 0},
        {"Mac", one, false, 0, 0}, {"SerialAccumulate", serial, true, 1, 4},
        {"LinkBuffer", link, true, 1, 1}, {"FifoBlock", one, false, 0, 0},
    };
    int errors = 0;
    *count = cases.size();
    for (const Case &c : cases)
    {
        std::string why;
        std::unique_ptr<SnaxDatapath> dp = snax_datapath_new(c.name, c.p, &why);
        if ((bool)dp != c.builds || (dp && (dp->latency != c.latency || dp->span != c.span)))
        {
            printf("registry: %s %s (L %d, span %d), expected %s (L %d, span %d)\n", c.name,
                dp ? "built" : ("refused: " + why).c_str(), dp ? dp->latency : 0,
                dp ? dp->span : 0, c.builds ? "built" : "refused", c.latency, c.span);
            errors++;
        }
    }
    return errors;
}

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        fprintf(stderr, "usage: %s VECTORS\n", argv[0]);
        return 2;
    }
    std::vector<Test> tests;
    if (!parse(argv[1], tests))
    {
        return 2;
    }
    int failed = 0, passed = 0, count;
    int reg_errors = check_registry(&count);
    printf("%s registry: %d cases\n", reg_errors ? "FAIL" : "PASS", count);
    failed += reg_errors != 0;
    passed += reg_errors == 0;
    for (const Test &t : tests)
    {
        int errors = run(t);
        printf("%s %s: %s, %zu steps\n", errors ? "FAIL" : "PASS", t.name.c_str(),
            t.datapath.c_str(), t.steps.size());
        failed += errors != 0;
        passed += errors == 0;
    }
    printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
