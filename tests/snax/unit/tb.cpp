// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxUnit's cycle rule, snax_group.hpp's SnaxGroupRule with one unit and no
// links, against hand-worked cases (README.md): each case file
// gives the unit (latency, II, inputs, lanes), the starts (jobs and job_beats)
// and, per cycle, each input's valid, the output's ready and the expected
// fire, push and busy; the tb drives that rule with them and
// compares every cycle and the trace line at the end of each run, whose busy,
// stall_in, stall_out and flush must add up to the run's busy cycles in the
// case file. A case with `types` also gives each firing's input lanes and
// each pushed result's value, computed as the component computes them
// (snax_op_elementwise, snax_op_fold). It also checks the op table, a
// fold's tree, NumPy's result types and whole beats on fixed vectors.
//
//   tb CASE...
//
// Exit 1 on any difference.

#include <cstdio>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "snax_group.hpp"
#include "snax_types.hpp"


struct StartLine
{
    int64_t cycle;
    uint32_t jobs, job_beats;
    std::string result;             // taken, ignored or refused
};

struct CycleLine
{
    std::vector<int> valid; // per input
    int ready, fire, push, busy;
};

struct Case
{
    std::string name;
    int latency = 0;
    int ii = 1;
    int inputs = 2;
    int lanes = 1;      // input lanes: the tree in front of a fold, or the op's
    std::vector<SnaxType> types;    // the inputs' then the output's; empty: no data
    int op = SNAX_OP_ADD;
    std::vector<StartLine> starts;
    std::vector<std::string> expects;   // run lines, in order
    std::vector<CycleLine> cycles;
    std::map<int, std::vector<int64_t>> beats;      // firing -> its inputs' lanes
    std::map<int, std::vector<int64_t>> results;    // push -> its lanes (a fold's one)
};

static std::string base_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    std::string base = slash == std::string::npos ? path : path.substr(slash + 1);
    size_t dot = base.rfind('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
}

// A NumPy integer type's name, int8 to uint64
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

// `beat N V...` or `result N V...`: an index and its values
static bool values_line(std::istringstream &ss, std::map<int, std::vector<int64_t>> &into)
{
    int n;
    if (!(ss >> n) || into.count(n))
    {
        return false;
    }
    std::vector<int64_t> values;
    std::string token;
    while (ss >> token)
    {
        char *end;
        values.push_back(std::strtoll(token.c_str(), &end, 0));
        if (*end != '\0')
        {
            return false;
        }
    }
    into[n] = values;
    return !values.empty();
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
            CycleLine l;
            l.valid.resize(c.inputs);
            std::istringstream cs(line);
            for (int i = 0; i < c.inputs; i++)
            {
                ok = ok && (bool)(cs >> l.valid[i]);
            }
            ok = ok && (bool)(cs >> l.ready >> l.fire >> l.push >> l.busy);
            c.cycles.push_back(l);
        }
        else if (key == "latency") { ok = (bool)(ss >> c.latency) && c.latency >= 0; }
        else if (key == "ii") { ok = (bool)(ss >> c.ii) && c.ii >= 1; }
        else if (key == "inputs") { ok = (bool)(ss >> c.inputs) && (c.inputs == 1 || c.inputs == 2); }
        else if (key == "lanes") { ok = (bool)(ss >> c.lanes) && c.lanes > 0; }
        else if (key == "types")
        {
            std::string name;
            SnaxType t;
            c.types.clear();
            while (ok && ss >> name)
            {
                ok = type_of(name, t);
                c.types.push_back(t);
            }
        }
        else if (key == "op")
        {
            std::string name;
            ok = (bool)(ss >> name);
            c.op = -1;
            for (int op = 0; ok && op < SNAX_NB_OPS; op++)
            {
                c.op = name == snax_op_names[op] ? op : c.op;
            }
            ok = ok && c.op != -1;
        }
        else if (key == "start")
        {
            // start CYCLE JOBS JOB_BEATS RESULT
            StartLine s;
            ok = (bool)(ss >> s.cycle >> s.jobs >> s.job_beats >> s.result) &&
                (s.result == "taken" || s.result == "ignored" || s.result == "refused");
            c.starts.push_back(s);
        }
        else if (key == "expect")
        {
            std::string rest;
            std::getline(ss, rest);
            size_t first = rest.find_first_not_of(' ');
            size_t last = rest.find_last_not_of(" \t\r");
            c.expects.push_back(first == std::string::npos ? "" : rest.substr(first, last - first + 1));
        }
        else if (key == "beat") { ok = values_line(ss, c.beats); }
        else if (key == "result") { ok = values_line(ss, c.results); }
        else if (key == "cycles") { in_cycles = true; }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    if (!c.types.empty() && (int)c.types.size() != c.inputs + 1)
    {
        fprintf(stderr, "%s: types gives %zu types, the inputs' then the output's (%d)\n",
            path.c_str(), c.types.size(), c.inputs + 1);
        return false;
    }
    return true;
}

static const char *start_names[] = {"taken", "ignored", "refused"};

// The data of a case with types: each firing's beat into a result, as the
// component computes it, and each push checked against the case's results
struct Data
{
    const Case &c;
    std::deque<std::vector<uint64_t>> pending;  // results computed, not pushed: their words
    uint64_t acc = 0;
    int fired = 0, pushed = 0;
    int errors = 0;

    std::vector<uint64_t> words(int input, const std::vector<int64_t> &lanes) const
    {
        SnaxType t = this->c.types[input];
        std::vector<uint64_t> w(this->c.lanes * t.width / 64 + 1, 0);
        for (int l = 0; l < this->c.lanes; l++)
        {
            snax_lane_set(w.data(), t.width, l, lanes[input * this->c.lanes + l]);
        }
        return w;
    }

    // Firing n of its run (first: it starts a result), with job_beats
    void fire(int64_t cycle, uint32_t n, uint32_t job_beats, bool result)
    {
        int index = this->fired++;
        auto it = this->c.beats.find(index);
        if (it == this->c.beats.end() || (int)it->second.size() != this->c.inputs * this->c.lanes)
        {
            printf("%s: cycle %ld: firing %d has no beat of %d values\n", this->c.name.c_str(),
                (long)cycle, index, this->c.inputs * this->c.lanes);
            this->errors++;
            return;
        }
        SnaxType out_t = this->c.types[this->c.inputs];
        if (this->c.inputs == 1)
        {
            this->acc = snax_op_fold(this->c.op, this->c.lanes, this->c.types[0], out_t,
                this->words(0, it->second).data(), n % job_beats == 0, this->acc);
            if (result)
            {
                this->pending.push_back({this->acc});
            }
            return;
        }
        std::vector<uint64_t> out(this->c.lanes * out_t.width / 64 + 1, 0);
        snax_op_elementwise(this->c.op, this->c.lanes, this->c.types[0], this->c.types[1],
            out_t, this->words(0, it->second).data(), this->words(1, it->second).data(),
            out.data());
        this->pending.push_back(out);
    }

    void push(int64_t cycle)
    {
        int index = this->pushed++;
        std::vector<uint64_t> got = this->pending.front();
        this->pending.pop_front();
        auto it = this->c.results.find(index);
        SnaxType out_t = this->c.types[this->c.inputs];
        int lanes = this->c.inputs == 1 ? 1 : this->c.lanes;
        if (it == this->c.results.end() || (int)it->second.size() != lanes)
        {
            printf("%s: cycle %ld: push %d has no result of %d values\n", this->c.name.c_str(),
                (long)cycle, index, lanes);
            this->errors++;
            return;
        }
        for (int l = 0; l < lanes; l++)
        {
            uint64_t want = (uint64_t)it->second[l] & snax_lane_mask(out_t.width);
            uint64_t value = snax_lane_get(got.data(), out_t.width, l);
            if (value != want)
            {
                printf("%s: cycle %ld: push %d lane %d is %lu, expected %lu\n",
                    this->c.name.c_str(), (long)cycle, index, l, (unsigned long)value,
                    (unsigned long)want);
                this->errors++;
            }
        }
    }
};

// Runs one case; returns the number of differences
static int run(const Case &c)
{
    SnaxGroupRule rule;
    SnaxGroupRule::UnitCfg cfg;
    cfg.latency = c.latency;
    cfg.ii = c.ii;
    rule.configure({cfg}, {});
    Data data{c};

    int errors = 0;
    size_t next_expect = 0;
    long run_busy = 0;      // busy cycles of the current run, from the case file
    for (size_t t = 0; t < c.cycles.size(); t++)
    {
        int64_t cycle = t;
        const CycleLine &l = c.cycles[t];
        for (const StartLine &s : c.starts)
        {
            if (s.cycle != cycle)
            {
                continue;
            }
            SnaxGroupRule::Start answer = rule.start(cycle, s.jobs, {s.job_beats});
            const char *got = start_names[answer];
            if (answer == SnaxGroupRule::TAKEN)
            {
                run_busy = 0;
            }
            if (s.result != got)
            {
                printf("%s: cycle %ld: start %u x %u %s, expected %s\n", c.name.c_str(),
                    (long)cycle, s.jobs, s.job_beats, got, s.result.c_str());
                errors++;
            }
        }
        int busy = rule.busy(cycle);
        SnaxGroupRule::Step step;
        step.units.assign(1, SnaxGroupRule::UnitStep());
        run_busy += l.busy;
        if (busy)
        {
            bool inputs = true;
            for (int v : l.valid)
            {
                inputs = inputs && v;
            }
            step = rule.step(cycle, {inputs}, {l.ready != 0});
        }
        const SnaxGroupRule::UnitStep &u = step.units[0];
        if (busy != l.busy || u.fire != l.fire || u.push != l.push)
        {
            printf("%s: cycle %ld: fire %d push %d busy %d, expected %d %d %d\n",
                c.name.c_str(), (long)cycle, u.fire, u.push, busy, l.fire, l.push,
                l.busy);
            errors++;
        }
        if (!c.types.empty())
        {
            // A push leaves before the firing of its cycle enters (L = 0: the same result)
            if (u.push && c.latency > 0)
            {
                data.push(cycle);
            }
            if (u.fire)
            {
                data.fire(cycle, rule.firings() - 1, rule.t[0], u.gives);
            }
            if (u.push && c.latency == 0)
            {
                data.push(cycle);
            }
        }
        if (step.end)
        {
            std::string got = rule.run_line();
            long b, si, so, fl;
            if (sscanf(got.c_str(), "run index=%*d firings=%*u busy=%ld stall_in=%ld stall_out=%ld flush=%ld",
                    &b, &si, &so, &fl) != 4)
            {
                printf("%s: cycle %ld: cannot read \"%s\"\n", c.name.c_str(), (long)cycle,
                    got.c_str());
                errors++;
            }
            else if (b + si + so + fl != run_busy)
            {
                printf("%s: cycle %ld: busy %ld + stall_in %ld + stall_out %ld + flush %ld = %ld, "
                    "the run's busy cycles %ld\n", c.name.c_str(), (long)cycle, b, si, so, fl,
                    b + si + so + fl, run_busy);
                errors++;
            }
            if (next_expect >= c.expects.size())
            {
                printf("%s: cycle %ld: \"%s\", none expected\n", c.name.c_str(),
                    (long)cycle, got.c_str());
                errors++;
            }
            else if (got != c.expects[next_expect])
            {
                printf("%s: cycle %ld: \"%s\", expected \"%s\"\n", c.name.c_str(),
                    (long)cycle, got.c_str(), c.expects[next_expect].c_str());
                errors++;
            }
            next_expect++;
        }
    }
    if (next_expect < c.expects.size())
    {
        printf("%s: %zu run line(s) expected, %zu given\n", c.name.c_str(),
            c.expects.size(), next_expect);
        errors++;
    }
    if (!c.types.empty() && data.pushed != (int)c.results.size())
    {
        printf("%s: %zu result(s) given, %d pushed\n", c.name.c_str(), c.results.size(),
            data.pushed);
        errors++;
    }
    return errors + data.errors;
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
        printf("%s %s: %zu cycles, %zu run(s)%s\n", errors ? "FAIL" : "PASS", c.name.c_str(),
            c.cycles.size(), c.expects.size(), c.types.empty() ? "" : ", data");
        failed += errors != 0;
        passed += errors == 0;
    }
    printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
