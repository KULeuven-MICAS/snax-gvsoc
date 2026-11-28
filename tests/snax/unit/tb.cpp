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
#include "../tb_common.hpp"


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
    bool lane_fold = false; // `fold lanes`: a one-input fold whose lanes each keep their own sum
    bool has_k = false;     // one input, an elementwise op with the constant k (relu's)
    uint64_t k = 0;         // its 64-bit two's complement
    // axpby's k1 and k2 (op axpby): each given, and whether read from its CSR (sent with
    // each start) rather than baked; the arithmetic is the same
    bool has_k1 = false, k1_csr = false, has_k2 = false, k2_csr = false;
    uint64_t k1 = 0, k2 = 0;
    // axpbypcz's k3 (as k1 and k2), threshold's k from its CSR, the baked d, lo and hi
    bool has_k3 = false, k3_csr = false, k_csr = false, has_d = false, has_lo = false,
        has_hi = false;
    uint64_t k3 = 0, d = 1, lo = 0, hi = 0;
    bool has_op_type = false;   // `optype`: the op's type, else the inputs' result type
    SnaxType op_type = {64, true};

    // One input computing lane by lane (relu's k, requant, threshold), not a fold
    bool lanewise_one() const
    {
        return this->has_k || this->op == SNAX_OP_REQUANT || this->op == SNAX_OP_THRESHOLD;
    }
    std::vector<StartLine> starts;
    std::vector<std::string> expects;   // run lines, in order
    std::vector<CycleLine> cycles;
    std::map<int, std::vector<int64_t>> beats;      // firing -> its inputs' lanes
    std::map<int, std::vector<int64_t>> results;    // push -> its lanes (a fold's one)
};

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
        else if (key == "inputs") { ok = (bool)(ss >> c.inputs) && c.inputs >= 1 && c.inputs <= 3; }
        else if (key == "optype")
        {
            std::string name;
            ok = (bool)(ss >> name) && tb_type_of(name, c.op_type);
            c.has_op_type = ok;
        }
        else if (key == "lanes") { ok = (bool)(ss >> c.lanes) && c.lanes > 0; }
        else if (key == "types")
        {
            std::string name;
            SnaxType t;
            c.types.clear();
            while (ok && ss >> name)
            {
                ok = tb_type_of(name, t);
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
            for (int i = 0; ok && i < SNAX_NB_NAMED_OPS; i++)
            {
                c.op = name == snax_named_ops[i] ? SNAX_OP_AXPBY + i : c.op;
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
        else if (key == "k" || key == "k1" || key == "k2" || key == "k3")
        {
            // k V [csr]: one input's constant or threshold's k; k1, k2, k3: axpby's and
            // axpbypcz's slots; each baked, or read from its CSR (V the value written)
            std::string v, from;
            ok = (bool)(ss >> v) && !v.empty();
            bool csr = (bool)(ss >> from);
            ok = ok && (!csr || from == "csr");
            if (ok)
            {
                uint64_t bits = v[0] == '-' ? (uint64_t)std::stoll(v) : std::stoull(v);
                int i = key == "k" ? 0 : key[1] - '0';
                uint64_t *value[4] = {&c.k, &c.k1, &c.k2, &c.k3};
                bool *has[4] = {&c.has_k, &c.has_k1, &c.has_k2, &c.has_k3};
                bool *from_csr[4] = {&c.k_csr, &c.k1_csr, &c.k2_csr, &c.k3_csr};
                *value[i] = bits;
                *has[i] = true;
                *from_csr[i] = csr;
            }
        }
        else if (key == "d" || key == "lo" || key == "hi")
        {
            // axpbypcz's and requant's divisor, requant's bounds, threshold's hi: baked
            std::string v;
            ok = (bool)(ss >> v) && !v.empty();
            if (ok)
            {
                (key == "d" ? c.d : key == "lo" ? c.lo : c.hi) =
                    v[0] == '-' ? (uint64_t)std::stoll(v) : std::stoull(v);
                (key == "d" ? c.has_d : key == "lo" ? c.has_lo : c.has_hi) = true;
            }
        }
        else if (key == "fold")
        {
            // fold tree (the default: the lanes summed into one) or fold lanes (each its own)
            std::string how;
            ok = (bool)(ss >> how) && (how == "tree" || how == "lanes");
            c.lane_fold = how == "lanes";
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
    bool axpby = c.op == SNAX_OP_AXPBY, xyz = c.op == SNAX_OP_AXPBYPCZ;
    bool requant = c.op == SNAX_OP_REQUANT, threshold = c.op == SNAX_OP_THRESHOLD;
    if ((axpby && (!c.has_k1 || c.inputs != 2)) || ((c.has_k1 || c.has_k2) && !axpby && !xyz))
    {
        fprintf(stderr, "%s: op axpby takes two inputs and k1 (k2 optional); k1 and k2 are "
            "axpby's and axpbypcz's\n", path.c_str());
        return false;
    }
    if ((xyz && (c.inputs != 3 || !c.has_d)) || (c.inputs == 3 && !xyz) || (c.has_k3 && !xyz))
    {
        fprintf(stderr, "%s: op axpbypcz takes three inputs and d (k1, k2, k3 optional), and only "
            "it\n", path.c_str());
        return false;
    }
    if ((requant && (c.inputs != 1 || !c.has_d || !c.has_lo || !c.has_hi || c.has_k)) ||
        (threshold && (c.inputs != 1 || !c.has_k || !c.has_hi)) || (c.has_lo && !requant) ||
        (c.has_hi && !requant && !threshold) || (c.has_d && !requant && !xyz))
    {
        fprintf(stderr, "%s: op requant takes one input, d, lo and hi; threshold one input, k "
            "and hi\n", path.c_str());
        return false;
    }
    if (c.lane_fold && (c.inputs != 1 || c.has_k))
    {
        fprintf(stderr, "%s: fold lanes is a one-input fold, without k\n", path.c_str());
        return false;
    }
    if (c.has_k && c.inputs != 1)
    {
        fprintf(stderr, "%s: k is one input's constant; inputs is %d\n", path.c_str(), c.inputs);
        return false;
    }
    if (!c.types.empty() && (int)c.types.size() != c.inputs + 1)
    {
        fprintf(stderr, "%s: types gives %zu types, the inputs' then the output's (%d)\n",
            path.c_str(), c.types.size(), c.inputs + 1);
        return false;
    }
    return true;
}

// The data of a case with types: each firing's beat into a result, as the
// component computes it, and each push checked against the case's results
struct Data
{
    const Case &c;
    std::deque<std::vector<uint64_t>> pending;  // results computed, not pushed: their words
    uint64_t acc = 0;
    std::vector<uint64_t> lane_acc;             // fold lanes: each lane's sum, at the output type
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
        if (this->c.op == SNAX_OP_AXPBYPCZ || this->c.op == SNAX_OP_REQUANT ||
            this->c.op == SNAX_OP_THRESHOLD)  // at optype, else the inputs' result type
        {
            std::vector<uint64_t> out(this->c.lanes * out_t.width / 64 + 1, 0);
            SnaxType t = this->c.types[0];
            for (int i = 1; i < this->c.inputs; i++)
            {
                snax_op_result_type(t, this->c.types[i], &t);
            }
            t = this->c.has_op_type ? this->c.op_type : t;
            int shift = 0;
            while (((uint64_t)1 << shift) < this->c.d)
            {
                shift++;
            }
            std::vector<std::vector<uint64_t>> w;
            std::vector<const uint64_t *> in;
            for (int i = 0; i < this->c.inputs; i++)
            {
                w.push_back(this->words(i, it->second));
            }
            for (const std::vector<uint64_t> &x : w)
            {
                in.push_back(x.data());
            }
            if (this->c.op == SNAX_OP_AXPBYPCZ)
            {
                const bool has[3] = {this->c.has_k1, this->c.has_k2, this->c.has_k3};
                const uint64_t k[3] = {this->c.k1, this->c.k2, this->c.k3};
                snax_op_axpbypcz(this->c.lanes, this->c.types.data(), t, out_t, in.data(), has, k,
                    shift, out.data());
            }
            else if (this->c.op == SNAX_OP_REQUANT)
            {
                snax_op_requant(this->c.lanes, this->c.types[0], t, out_t, in[0], shift,
                    this->c.lo, this->c.hi, out.data());
            }
            else
            {
                snax_op_threshold(this->c.lanes, this->c.types[0], t, out_t, in[0], this->c.k,
                    this->c.hi, out.data());
            }
            this->pending.push_back(out);
            return;
        }
        if (this->c.op == SNAX_OP_AXPBY)  // k1 * a + k2 * b at the inputs' result type
        {
            SnaxType t;
            snax_op_result_type(this->c.types[0], this->c.types[1], &t);
            std::vector<uint64_t> out(this->c.lanes * out_t.width / 64 + 1, 0);
            snax_op_axpby(this->c.lanes, this->c.types[0], this->c.types[1], t, out_t,
                this->words(0, it->second).data(), this->words(1, it->second).data(), this->c.k1,
                this->c.has_k2, this->c.k2, out.data());
            this->pending.push_back(out);
            return;
        }
        if (this->c.has_k)  // one input, op(a, k) at a's type
        {
            std::vector<uint64_t> out(this->c.lanes * out_t.width / 64 + 1, 0);
            snax_op_elementwise_k(this->c.op, this->c.lanes, this->c.types[0], this->c.types[0],
                out_t, this->words(0, it->second).data(), this->c.k, out.data());
            this->pending.push_back(out);
            return;
        }
        if (this->c.inputs == 1 && this->c.lane_fold)  // per lane s <- first ? a : s + a
        {
            std::vector<uint64_t> a = this->words(0, it->second);
            std::vector<uint64_t> next(this->c.lanes * out_t.width / 64 + 1, 0);  // set ORs
            this->lane_acc.resize(next.size(), 0);
            for (int l = 0; l < this->c.lanes; l++)
            {
                uint64_t x = snax_lane_cast(snax_lane_get(a.data(), this->c.types[0].width, l),
                    this->c.types[0], out_t);
                uint64_t s = snax_lane_get(this->lane_acc.data(), out_t.width, l);
                snax_lane_set(next.data(), out_t.width, l, n % job_beats == 0 ? x :
                    snax_op_compute(SNAX_OP_ADD, out_t, s, x));
            }
            this->lane_acc = next;
            if (result)
            {
                this->pending.push_back(this->lane_acc);
            }
            return;
        }
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
        int lanes = this->c.inputs == 1 && !this->c.lanewise_one() && !this->c.lane_fold ? 1
            : this->c.lanes;
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
            const char *got = tb_start_names[answer];
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
                data.fire(cycle, rule.firings() - 1, rule.job_beats[0], u.gives);
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
    return tb_main<Case>(argc, argv, parse, run, [](const Case &c) {
        printf("%s: %zu cycles, %zu run(s)%s\n", c.name.c_str(), c.cycles.size(),
            c.expects.size(), c.types.empty() ? "" : ", data");
    });
}
