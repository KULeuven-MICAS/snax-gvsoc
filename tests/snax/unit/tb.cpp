// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// SnaxUnit's cycle rule against hand-worked cases (README.md): each case file
// gives the parameters, the starts (their configuration words in the order
// the case's config gives) and, per cycle, each input's valid, the
// output's ready and the expected fire, push and busy; the tb drives
// snax_unit.hpp's rule with them and compares every cycle and the trace line
// at the end of each run, whose busy, stall_in, stall_out and flush must add
// up to the run's busy cycles in the case file. It also checks the op table,
// a fold's tree, NumPy's result types and whole beats on fixed vectors.
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

#include "snax_unit.hpp"


struct StartLine
{
    int64_t cycle;
    std::vector<uint32_t> words;    // in the case's config order
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
    std::string wait = "lockstep";
    int latency = 0;
    int ii = 1;
    int inputs = 2;
    int lanes = 1;      // a fold's input lanes: the tree, not the rule
    std::vector<std::string> config = {"count"};    // the start words' roles
    std::vector<StartLine> starts;
    std::vector<std::string> expects;   // run lines, in order
    std::vector<CycleLine> cycles;
    std::vector<std::string> likes;     // cases run with this one's wait, latency, ii
    bool has_wait = false, has_latency = false, has_ii = false;
};

static std::string dir_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    return slash == std::string::npos ? "." : path.substr(0, slash);
}

static std::string base_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    std::string base = slash == std::string::npos ? path : path.substr(slash + 1);
    size_t dot = base.rfind('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
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
        else if (key == "wait") { ok = (bool)(ss >> c.wait); c.has_wait = true; }
        else if (key == "latency") { ok = (bool)(ss >> c.latency); c.has_latency = true; }
        else if (key == "ii") { ok = (bool)(ss >> c.ii); c.has_ii = true; }
        else if (key == "inputs") { ok = (bool)(ss >> c.inputs); }
        else if (key == "lanes") { ok = (bool)(ss >> c.lanes) && c.lanes > 0; }
        else if (key == "config")
        {
            c.config.clear();
            std::string role;
            while (ss >> role)
            {
                ok = ok && (role == "count" || role == "rate");
                c.config.push_back(role);
            }
            ok = ok && !c.config.empty();
        }
        else if (key == "start")
        {
            // start CYCLE WORD... RESULT, one word per config role
            StartLine s;
            std::vector<std::string> tokens;
            std::string token;
            ok = (bool)(ss >> s.cycle);
            while (ss >> token)
            {
                tokens.push_back(token);
            }
            ok = ok && tokens.size() == c.config.size() + 1;
            for (size_t i = 0; ok && i + 1 < tokens.size(); i++)
            {
                s.words.push_back(std::stoul(tokens[i]));
            }
            if (ok)
            {
                s.result = tokens.back();
            }
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
        else if (key == "like")
        {
            std::string file;
            ok = (bool)(ss >> file);
            c.likes.push_back(dir_of(path) + "/" + file);
        }
        else if (key == "cycles") { in_cycles = true; }
        else { ok = false; }
        if (!ok)
        {
            fprintf(stderr, "%s:%d: cannot read \"%s\"\n", path.c_str(), lineno, raw.c_str());
            return false;
        }
    }
    if (c.lanes > 1 && c.inputs != 1)
    {
        fprintf(stderr, "%s: lanes %d needs a fold (inputs 1)\n", path.c_str(), c.lanes);
        return false;
    }
    return true;
}

static const char *start_names[] = {"taken", "ignored", "refused"};

// Runs one case; returns the number of differences
static int run(const Case &c)
{
    SnaxUnitRule rule;
    SnaxUnitRule::Wait wait;
    if (c.wait == "lockstep") wait = SnaxUnitRule::LOCKSTEP;
    else if (c.wait == "pipelined") wait = SnaxUnitRule::PIPELINED;
    else
    {
        printf("%s: unknown wait %s\n", c.name.c_str(), c.wait.c_str());
        return 1;
    }
    rule.configure(wait, c.latency, c.ii);

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
            uint32_t count = 0, rate = 1;
            for (size_t w = 0; w < c.config.size(); w++)
            {
                (c.config[w] == "count" ? count : rate) = s.words[w];
            }
            if (count != 0 && rate != 0 && count % rate != 0)
            {
                // The component stops there (a fatal error): not a case
                printf("%s: cycle %ld: count %u is not a multiple of rate %u\n", c.name.c_str(),
                    (long)cycle, count, rate);
                errors++;
                continue;
            }
            SnaxUnitRule::Start answer = rule.start(cycle, count, rate);
            const char *got = start_names[answer];
            if (answer == SnaxUnitRule::TAKEN)
            {
                run_busy = 0;
            }
            if (s.result != got)
            {
                printf("%s: cycle %ld: start %u %s, expected %s\n", c.name.c_str(),
                    (long)cycle, count, got, s.result.c_str());
                errors++;
            }
        }

        int busy = rule.busy(cycle);
        SnaxUnitRule::Step step = {false, false, false, SnaxUnitRule::FLUSH, false};
        run_busy += l.busy;
        if (busy)
        {
            bool inputs = true;
            for (int v : l.valid)
            {
                inputs = inputs && v;
            }
            step = rule.step(cycle, inputs, l.ready);
        }
        if (busy != l.busy || step.fire != l.fire || step.push != l.push)
        {
            printf("%s: cycle %ld: fire %d push %d busy %d, expected %d %d %d\n",
                c.name.c_str(), (long)cycle, step.fire, step.push, busy, l.fire, l.push,
                l.busy);
            errors++;
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
    return errors;
}

// The op table on fixed vectors: wrapping, and min and max signed or not
static int check_ops(int *count)
{
    struct Vector { int op; SnaxUnitType t; uint64_t a, b, r; };
    static const Vector vectors[] = {
        {UNIT_ADD, {8, false}, 0xFF, 0x01, 0x00},
        {UNIT_ADD, {64, false}, ~0ull, 2, 1},
        {UNIT_SUB, {8, false}, 0x00, 0x01, 0xFF},
        {UNIT_SUB, {32, false}, 5, 7, 0xFFFFFFFE},
        {UNIT_MUL, {16, false}, 0x100, 0x100, 0x0000},
        {UNIT_MUL, {64, false}, 0x100000000ull, 0x100000001ull, 0x100000000ull},
        {UNIT_AND, {8, false}, 0xF0, 0x3C, 0x30},
        {UNIT_OR, {8, false}, 0xF0, 0x3C, 0xFC},
        {UNIT_XOR, {8, false}, 0xF0, 0x3C, 0xCC},
        {UNIT_MIN, {8, false}, 0x80, 0x01, 0x01},
        {UNIT_MIN, {8, true}, 0x80, 0x01, 0x80},
        {UNIT_MAX, {32, false}, 0xFFFFFFFF, 1, 0xFFFFFFFF},
        {UNIT_MAX, {32, true}, 0xFFFFFFFF, 1, 1},
        {UNIT_MIN, {64, true}, 0x8000000000000000ull, 0, 0x8000000000000000ull},
        {UNIT_MAX, {16, true}, 0x7FFF, 0x8000, 0x7FFF},
        // Operands wider than width are cut to it first
        {UNIT_ADD, {8, false}, 0x1FF, 0x101, 0x00},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        uint64_t r = snax_unit_compute(v.op, v.t, v.a, v.b);
        if (r != v.r)
        {
            printf("ops: %s %s 0x%lx 0x%lx = 0x%lx, expected 0x%lx\n",
                snax_unit_op_names[v.op], snax_unit_type_name(v.t).c_str(),
                (unsigned long)v.a, (unsigned long)v.b, (unsigned long)r, (unsigned long)v.r);
            errors++;
        }
    }
    return errors;
}

// A fold's tree on fixed vectors: halves first, wrapping, one lane as it is
static int check_tree(int *count)
{
    struct Vector { int op; SnaxUnitType t; std::vector<uint64_t> lanes; uint64_t r; };
    static const Vector vectors[] = {
        {UNIT_ADD, {64, false}, {7}, 7},
        {UNIT_ADD, {64, false}, {1, 2, 3, 4}, 10},
        {UNIT_ADD, {64, false}, {~0ull, 1, 2, 3}, 5},
        {UNIT_ADD, {8, false}, {0x80, 0x80, 0x01, 0x02}, 0x03},
        {UNIT_ADD, {64, false}, {1, 2, 3}, 6},
        // (a0 - a1) - (a2 - a3): the order of the halves
        {UNIT_SUB, {64, false}, {10, 4, 3, 1}, 4},
        {UNIT_MIN, {64, true}, {5, ~0ull, 3, 2}, ~0ull},
        {UNIT_MAX, {64, false}, {5, ~0ull, 3, 2}, ~0ull},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        uint64_t r = snax_unit_tree(v.op, v.t, v.lanes.data(), v.lanes.size());
        if (r != v.r)
        {
            printf("tree: %s %s over %zu lanes = 0x%lx, expected 0x%lx\n",
                snax_unit_op_names[v.op], snax_unit_type_name(v.t).c_str(), v.lanes.size(),
                (unsigned long)r, (unsigned long)v.r);
            errors++;
        }
    }
    return errors;
}

// NumPy's result types (np.result_type) on fixed pairs; ok false, refused
static int check_types(int *count)
{
    struct Vector { SnaxUnitType a, b; bool ok; SnaxUnitType r; };
    static const Vector vectors[] = {
        {{8, true}, {8, false}, true, {16, true}},
        {{32, true}, {32, false}, true, {64, true}},
        {{16, true}, {8, false}, true, {16, true}},
        {{8, true}, {32, true}, true, {32, true}},
        {{8, false}, {16, false}, true, {16, false}},
        // NumPy gives float64
        {{64, true}, {64, false}, false, {0, false}},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        SnaxUnitType r;
        bool ok = snax_unit_result_type(v.a, v.b, &r);
        if (ok != v.ok || (ok && (r.width != v.r.width || r.is_signed != v.r.is_signed)))
        {
            printf("types: %s, %s = %s, expected %s\n", snax_unit_type_name(v.a).c_str(),
                snax_unit_type_name(v.b).c_str(),
                ok ? snax_unit_type_name(r).c_str() : "refused",
                v.ok ? snax_unit_type_name(v.r).c_str() : "refused");
            errors++;
        }
    }
    return errors;
}

// Whole beats on fixed vectors, the 64-bit channel words lane 0 lowest: an
// elementwise op (a op b at their result type, cast to out), or a fold
// (folds firings of the same beat a into one output word)
static int check_beats(int *count)
{
    struct Vector
    {
        const char *name;
        int op;
        int lanes;
        int folds;          // 0: elementwise
        SnaxUnitType a_t, b_t, out_t;
        std::vector<uint64_t> a, b, out;
    };
    const SnaxUnitType i8 = {8, true}, u8 = {8, false}, i16 = {16, true}, i32 = {32, true},
        i64 = {64, true};
    const std::vector<uint64_t> add2_a = {0x00000005fffffffdull, 0xffffffff00000007ull,
        0x7fffffff00000064ull, 0x0000000080000000ull};
    const std::vector<uint64_t> ones32(4, 0x0000000100000001ull);
    const Vector vectors[] = {
        {"1 mul int32 -> int64", UNIT_MUL, 4, 0, i32, i32, i64,
            {0xfffffffe00000003ull, 0xfffffffb7fffffffull},
            {0x0000000700000004ull, 0xffffffff00000002ull},
            {0x000000000000000cull, 0xfffffffffffffff2ull, 0xfffffffffffffffeull,
                0x0000000000000005ull}},
        {"2a add int32 -> int32", UNIT_ADD, 8, 0, i32, i32, i32, add2_a, ones32,
            {0x00000006fffffffeull, 0x0000000000000008ull, 0x8000000000000065ull,
                0x0000000180000001ull}},
        {"2b add int32 -> int64", UNIT_ADD, 8, 0, i32, i32, i64, add2_a, ones32,
            {0xfffffffffffffffeull, 0x6, 0x8, 0x0, 0x65, 0xffffffff80000000ull,
                0xffffffff80000001ull, 0x1}},
        {"3 mul int8 -> int32", UNIT_MUL, 8, 0, i8, i8, i32,
            {0x000000000780fd64ull}, {0x00000000fe800503ull},
            {0xfffffff10000002cull, 0xfffffff200000000ull, 0x0, 0x0}},
        {"4a fold add int32 -> int64", UNIT_ADD, 4, 1, i32, {}, i64,
            {0x000000017fffffffull, 0xfffffffe00000005ull}, {}, {0x0000000080000003ull}},
        {"4b fold add int32 -> int64, twice", UNIT_ADD, 4, 2, i32, {}, i64,
            {0x000000017fffffffull, 0xfffffffe00000005ull}, {}, {0x0000000100000006ull}},
        {"5 fold add int8 -> int32", UNIT_ADD, 8, 1, i8, {}, i32,
            {0x00000000f200f12cull}, {}, {0x000000000000000full}},
        {"6a fold add int8 -> int32", UNIT_ADD, 8, 1, i8, {}, i32,
            {0x00000000000005fdull}, {}, {0x2}},
        {"6b fold add uint8 -> int32", UNIT_ADD, 8, 1, u8, {}, i32,
            {0x00000000000005fdull}, {}, {0x102}},
        {"7a max int8 -> int32", UNIT_MAX, 8, 0, i8, i8, i32, {0x90}, {0x0},
            {0x0, 0x0, 0x0, 0x0}},
        {"7b max uint8 -> int32", UNIT_MAX, 8, 0, u8, u8, i32, {0x90}, {0x0},
            {0x90, 0x0, 0x0, 0x0}},
        {"7c fold max int8 -> int16", UNIT_MAX, 8, 1, i8, {}, i16,
            {0x0000000000001090ull}, {}, {0x10}},
        {"7d fold max uint8 -> int16", UNIT_MAX, 8, 1, u8, {}, i16,
            {0x0000000000001090ull}, {}, {0x90}},
        {"8 add int8 + uint8 -> int16", UNIT_ADD, 8, 0, i8, u8, i16,
            {0xffffffffffffffffull}, {0xffffffffffffffffull},
            {0x00fe00fe00fe00feull, 0x00fe00fe00fe00feull}},
        {"9 add int32 -> int16", UNIT_ADD, 4, 0, i32, i32, i16,
            {0xffffffff00011170ull, 0x7fffffff00000005ull}, ones32,
            {0x0000000600001171ull}},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        std::vector<uint64_t> out;
        if (v.folds == 0)
        {
            out.assign(v.lanes * v.out_t.width / 64, 0);
            snax_unit_elementwise(v.op, v.lanes, v.a_t, v.b_t, v.out_t, v.a.data(), v.b.data(),
                out.data());
        }
        else
        {
            uint64_t acc = 0;
            for (int n = 0; n < v.folds; n++)
            {
                acc = snax_unit_fold(v.op, v.lanes, v.a_t, v.out_t, v.a.data(), n == 0, acc);
            }
            out.assign(1, acc);
        }
        if (out != v.out)
        {
            printf("beats: %s =", v.name);
            for (uint64_t w : out)
            {
                printf(" 0x%016lx", (unsigned long)w);
            }
            printf(", expected");
            for (uint64_t w : v.out)
            {
                printf(" 0x%016lx", (unsigned long)w);
            }
            printf("\n");
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
    int nb_ops;
    int op_errors = check_ops(&nb_ops);
    printf("%s ops: %d vectors\n", op_errors ? "FAIL" : "PASS", nb_ops);
    failed += op_errors != 0;
    passed += op_errors == 0;
    int nb_trees;
    int tree_errors = check_tree(&nb_trees);
    printf("%s tree: %d vectors\n", tree_errors ? "FAIL" : "PASS", nb_trees);
    failed += tree_errors != 0;
    passed += tree_errors == 0;
    int nb_types;
    int type_errors = check_types(&nb_types);
    printf("%s types: %d vectors\n", type_errors ? "FAIL" : "PASS", nb_types);
    failed += type_errors != 0;
    passed += type_errors == 0;
    int nb_beats;
    int beat_errors = check_beats(&nb_beats);
    printf("%s beats: %d vectors\n", beat_errors ? "FAIL" : "PASS", nb_beats);
    failed += beat_errors != 0;
    passed += beat_errors == 0;

    for (int i = 1; i < argc; i++)
    {
        Case c;
        if (!parse(argv[i], c))
        {
            return 2;
        }
        std::vector<Case> runs;
        if (c.likes.empty())
        {
            runs.push_back(c);
        }
        for (const std::string &like : c.likes)
        {
            // The liked case with this case's wait, latency and ii
            Case l;
            if (!parse(like, l))
            {
                return 2;
            }
            if (c.has_wait) l.wait = c.wait;
            if (c.has_latency) l.latency = c.latency;
            if (c.has_ii) l.ii = c.ii;
            l.name = c.name + "(" + l.name + ")";
            runs.push_back(l);
        }
        for (const Case &r : runs)
        {
            int errors = run(r);
            printf("%s %s: %zu cycles, %zu run(s)\n", errors ? "FAIL" : "PASS", r.name.c_str(),
                r.cycles.size(), r.expects.size());
            failed += errors != 0;
            passed += errors == 0;
        }
    }
    printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
