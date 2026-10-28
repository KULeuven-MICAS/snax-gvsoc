// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxShell's rule against hand-worked cases (README.md): each case file
// gives the group's read-write CSRs and the unit behind it, then, per cycle,
// each input's valid, the output's ready, at most one CSR access with its
// expected result, and the expected STATUS. The tb steps snax_shell.hpp's rule
// with snax_unit.hpp's, wired as GVSoC wires them: the shell's accepted start
// (but the empty run) starts the unit with JOBS and JOB_BEATS, and the unit's
// busy feeds the shell.
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

#include "snax_shell.hpp"
#include "snax_unit.hpp"


struct CycleLine
{
    std::vector<int> valid;     // per input
    int ready;
    char access;                // 'w', 'r', '-' (none) or '.' (the write above still held)
    int offset;
    uint32_t value;             // a write's value
    int64_t result;             // a write's answer cycle, a read's value; -1 for '-' and '.'
    int status;
    int lineno;
};

struct Case
{
    std::string name;
    std::vector<std::string> csrs = {"START", "JOBS"};    // the read-write CSRs
    int latency = 0;
    int ii = 1;
    int inputs = 2;
    std::vector<CycleLine> cycles;
};

static std::string base_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    std::string base = slash == std::string::npos ? path : path.substr(slash + 1);
    size_t dot = base.rfind('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
}

static bool number(const std::string &token, int64_t &value)
{
    char *end;
    value = std::strtoll(token.c_str(), &end, 0);
    return !token.empty() && *end == '\0';
}

// A cycle line: VALID... READY ACCESS RESULT STATUS, ACCESS being `w OFFSET
// VALUE`, `r OFFSET`, `-` or `.`
static bool parse_cycle(const std::string &line, int inputs, CycleLine &l)
{
    std::istringstream cs(line);
    std::vector<std::string> t;
    std::string token;
    while (cs >> token)
    {
        t.push_back(token);
    }
    size_t at = inputs + 1;
    if (t.size() < at + 3)
    {
        return false;
    }
    int64_t v;
    l.valid.resize(inputs);
    for (int i = 0; i < inputs; i++)
    {
        if (!number(t[i], v)) return false;
        l.valid[i] = v;
    }
    if (!number(t[inputs], v)) return false;
    l.ready = v;
    l.access = t[at].size() == 1 ? t[at][0] : '?';
    l.offset = -1;
    l.value = 0;
    size_t rest = at + 1;
    if (l.access == 'w')
    {
        if (t.size() != at + 5 || !number(t[at + 1], v)) return false;
        l.offset = v;
        if (!number(t[at + 2], v)) return false;
        l.value = v;
        rest = at + 3;
    }
    else if (l.access == 'r')
    {
        if (t.size() != at + 4 || !number(t[at + 1], v)) return false;
        l.offset = v;
        rest = at + 2;
    }
    else if (l.access != '-' && l.access != '.')
    {
        return false;
    }
    else if (t.size() != at + 3)
    {
        return false;
    }
    if (l.access == '-' || l.access == '.')
    {
        if (t[rest] != "-") return false;
        l.result = -1;
    }
    else if (!number(t[rest], l.result))
    {
        return false;
    }
    if (!number(t[rest + 1], v)) return false;
    l.status = v;
    return true;
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
            ok = parse_cycle(line, c.inputs, l);
            l.lineno = lineno;
            c.cycles.push_back(l);
        }
        else if (key == "csrs")
        {
            // START, JOBS, then the units' (JOB_BEATS)
            c.csrs.clear();
            std::string word;
            while (ss >> word)
            {
                c.csrs.push_back(word);
            }
            ok = c.csrs.size() >= 2 && c.csrs[0] == "START" && c.csrs[1] == "JOBS";
        }
        else if (key == "latency") { ok = (bool)(ss >> c.latency); }
        else if (key == "ii") { ok = (bool)(ss >> c.ii); }
        else if (key == "inputs") { ok = (bool)(ss >> c.inputs) && c.inputs > 0; }
        else if (key == "cycles") { in_cycles = true; }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    return true;
}

// Runs one case; returns the number of differences
static int run(const Case &c)
{
    SnaxUnitRule unit;
    unit.configure(c.latency, c.ii);
    SnaxShellRule shell;
    int job_beats = -1;
    for (size_t i = 2; i < c.csrs.size(); i++)
    {
        job_beats = c.csrs[i] == "JOB_BEATS" ? i : job_beats;
    }
    shell.configure(c.csrs.size(), job_beats);
    int nb_rw = c.csrs.size();

    int errors = 0;
    auto fail = [&](int64_t cycle, const CycleLine &l, const std::string &why) {
        printf("%s: cycle %ld (line %d): %s\n", c.name.c_str(), (long)cycle, l.lineno, why.c_str());
        errors++;
    };

    // The shell's accepted start in cycle (not the empty run): JOBS and
    // JOB_BEATS to the unit's ctrl
    auto start_unit = [&](int64_t cycle, const CycleLine &l) {
        SnaxUnitRule::Start answer = unit.start(cycle, shell.jobs(), shell.job_beats());
        if (answer == SnaxUnitRule::REFUSED)
        {
            fail(cycle, l, "the unit refused a start the shell sent while idle");
        }
        else if (answer == SnaxUnitRule::TAKEN)
        {
            shell.busy(cycle, true);
        }
    };

    // The write in flight: its line, and the cycle it was answered (-1 while held)
    const CycleLine *pending = nullptr;
    int64_t pending_cycle = 0, answered = -1;
    for (size_t t = 0; t < c.cycles.size(); t++)
    {
        int64_t cycle = t;
        const CycleLine &l = c.cycles[t];

        // A held start taken in E + 1: it goes to the unit, its write is answered
        if (shell.held && shell.release_cycle() == cycle)
        {
            if (!shell.release(cycle))
            {
                start_unit(cycle, l);
            }
            answered = cycle;
        }

        if (pending != nullptr && answered != -1 && answered < cycle)
        {
            // The write ended before this line: check its answer cycle
            if (answered != pending->result)
            {
                fail(pending_cycle, *pending, "write answered in cycle " + std::to_string(answered) +
                    ", expected " + std::to_string(pending->result));
            }
            pending = nullptr;
        }
        if (l.access == '.')
        {
            if (pending == nullptr)
            {
                fail(cycle, l, "`.` with no held write: it was answered by then");
            }
        }
        else if (pending != nullptr)
        {
            fail(cycle, l, "a new access while the write of cycle " + std::to_string(pending_cycle) +
                " is still held");
            pending = nullptr;
        }

        if (l.access == 'w')
        {
            if (l.offset < 0 || l.offset >= nb_rw)
            {
                fail(cycle, l, "a write to a read-only or unknown CSR");
            }
            else
            {
                SnaxShellRule::Write w = shell.write(cycle, l.offset, l.value);
                pending = &l;
                pending_cycle = cycle;
                answered = w.held ? -1 : cycle;
                if (w.start && !w.empty)
                {
                    start_unit(cycle, l);
                }
            }
        }
        else if (l.access == 'r')
        {
            if (l.offset < 0 || l.offset >= nb_rw + 2)
            {
                fail(cycle, l, "a read of an unknown CSR");
            }
            else
            {
                uint32_t got = shell.read(cycle, l.offset);
                if ((int64_t)got != l.result)
                {
                    fail(cycle, l, "read " + std::to_string(l.offset) + " gives " +
                        std::to_string(got) + ", expected " + std::to_string(l.result));
                }
            }
        }

        // The unit's busy cycle; its last one clears the busy wire
        if (unit.busy(cycle))
        {
            bool inputs = true;
            for (int v : l.valid)
            {
                inputs = inputs && v;
            }
            SnaxUnitRule::Step step = unit.step(cycle, inputs, l.ready);
            if (step.end)
            {
                shell.busy(cycle, false);
            }
        }

        int status = shell.read(cycle, nb_rw);
        if (status != l.status)
        {
            fail(cycle, l, "STATUS " + std::to_string(status) + ", expected " +
                std::to_string(l.status));
        }
    }
    if (pending != nullptr)
    {
        if (answered == -1)
        {
            printf("%s: the write of cycle %ld is still held after the last cycle\n",
                c.name.c_str(), (long)pending_cycle);
            errors++;
        }
        else if (answered != pending->result)
        {
            printf("%s: cycle %ld: write answered in cycle %ld, expected %ld\n", c.name.c_str(),
                (long)pending_cycle, (long)answered, (long)pending->result);
            errors++;
        }
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
        printf("%s %s: %zu cycles\n", errors ? "FAIL" : "PASS", c.name.c_str(), c.cycles.size());
        failed += errors != 0;
        passed += errors == 0;
    }
    printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
