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
#include <utility>
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

// snax_types.hpp's arithmetic, which the classes run, on fixed vectors
// worked by hand: the edges the NumPy vectors (int32 and int64, add and mul)
// do not reach

// The op table on fixed vectors: wrapping, and min and max signed or not
static int check_ops(int *count)
{
    struct Vector { int op; SnaxType t; uint64_t a, b, r; };
    static const Vector vectors[] = {
        {SNAX_OP_ADD, {8, false}, 0xFF, 0x01, 0x00},
        {SNAX_OP_ADD, {64, false}, ~0ull, 2, 1},
        {SNAX_OP_SUB, {8, false}, 0x00, 0x01, 0xFF},
        {SNAX_OP_SUB, {32, false}, 5, 7, 0xFFFFFFFE},
        {SNAX_OP_MUL, {16, false}, 0x100, 0x100, 0x0000},
        {SNAX_OP_MUL, {64, false}, 0x100000000ull, 0x100000001ull, 0x100000000ull},
        {SNAX_OP_AND, {8, false}, 0xF0, 0x3C, 0x30},
        {SNAX_OP_OR, {8, false}, 0xF0, 0x3C, 0xFC},
        {SNAX_OP_XOR, {8, false}, 0xF0, 0x3C, 0xCC},
        {SNAX_OP_MIN, {8, false}, 0x80, 0x01, 0x01},
        {SNAX_OP_MIN, {8, true}, 0x80, 0x01, 0x80},
        {SNAX_OP_MAX, {32, false}, 0xFFFFFFFF, 1, 0xFFFFFFFF},
        {SNAX_OP_MAX, {32, true}, 0xFFFFFFFF, 1, 1},
        {SNAX_OP_MIN, {64, true}, 0x8000000000000000ull, 0, 0x8000000000000000ull},
        {SNAX_OP_MAX, {16, true}, 0x7FFF, 0x8000, 0x7FFF},
        // Operands wider than width are cut to it first
        {SNAX_OP_ADD, {8, false}, 0x1FF, 0x101, 0x00},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        uint64_t r = snax_op_compute(v.op, v.t, v.a, v.b);
        if (r != v.r)
        {
            printf("ops: %s %s 0x%lx 0x%lx = 0x%lx, expected 0x%lx\n",
                snax_op_names[v.op], snax_type_name(v.t).c_str(),
                (unsigned long)v.a, (unsigned long)v.b, (unsigned long)r, (unsigned long)v.r);
            errors++;
        }
    }
    return errors;
}

// A fold's tree on fixed vectors: halves first, wrapping, one lane as it is
static int check_tree(int *count)
{
    struct Vector { int op; SnaxType t; std::vector<uint64_t> lanes; uint64_t r; };
    static const Vector vectors[] = {
        {SNAX_OP_ADD, {64, false}, {7}, 7},
        {SNAX_OP_ADD, {64, false}, {1, 2, 3, 4}, 10},
        {SNAX_OP_ADD, {64, false}, {~0ull, 1, 2, 3}, 5},
        {SNAX_OP_ADD, {8, false}, {0x80, 0x80, 0x01, 0x02}, 0x03},
        {SNAX_OP_ADD, {64, false}, {1, 2, 3}, 6},
        // (a0 - a1) - (a2 - a3): the order of the halves
        {SNAX_OP_SUB, {64, false}, {10, 4, 3, 1}, 4},
        {SNAX_OP_MIN, {64, true}, {5, ~0ull, 3, 2}, ~0ull},
        {SNAX_OP_MAX, {64, false}, {5, ~0ull, 3, 2}, ~0ull},
    };
    int errors = 0;
    *count = sizeof(vectors) / sizeof(vectors[0]);
    for (const Vector &v : vectors)
    {
        uint64_t r = snax_op_tree(v.op, v.t, v.lanes.data(), v.lanes.size());
        if (r != v.r)
        {
            printf("tree: %s %s over %zu lanes = 0x%lx, expected 0x%lx\n",
                snax_op_names[v.op], snax_type_name(v.t).c_str(), v.lanes.size(),
                (unsigned long)r, (unsigned long)v.r);
            errors++;
        }
    }
    return errors;
}

// NumPy's result types (np.result_type) on fixed pairs; ok false, refused
static int check_types(int *count)
{
    struct Vector { SnaxType a, b; bool ok; SnaxType r; };
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
        SnaxType r;
        bool ok = snax_op_result_type(v.a, v.b, &r);
        if (ok != v.ok || (ok && (r.width != v.r.width || r.is_signed != v.r.is_signed)))
        {
            printf("types: %s, %s = %s, expected %s\n", snax_type_name(v.a).c_str(),
                snax_type_name(v.b).c_str(),
                ok ? snax_type_name(r).c_str() : "refused",
                v.ok ? snax_type_name(v.r).c_str() : "refused");
            errors++;
        }
    }
    return errors;
}

// Whole beats on fixed vectors, the 64-bit channel words lane 0 lowest: an
// elementwise op (a op b at their result type, cast to out), or a fold
// (folds firings of the same beat a into one output word). Those the NumPy
// vectors cover are not here: add int32 -> int32 (elementwise_add_int32_w8),
// a fold add int32 -> int64 (tree_int32_to_int64_w4)
static int check_beats(int *count)
{
    struct Vector
    {
        const char *name;
        int op;
        int lanes;
        int folds;          // 0: elementwise
        SnaxType a_t, b_t, out_t;
        std::vector<uint64_t> a, b, out;
    };
    const SnaxType i8 = {8, true}, u8 = {8, false}, i16 = {16, true}, i32 = {32, true},
        i64 = {64, true};
    const std::vector<uint64_t> add2_a = {0x00000005fffffffdull, 0xffffffff00000007ull,
        0x7fffffff00000064ull, 0x0000000080000000ull};
    const std::vector<uint64_t> ones32(4, 0x0000000100000001ull);
    const Vector vectors[] = {
        {"1 mul int32 -> int64", SNAX_OP_MUL, 4, 0, i32, i32, i64,
            {0xfffffffe00000003ull, 0xfffffffb7fffffffull},
            {0x0000000700000004ull, 0xffffffff00000002ull},
            {0x000000000000000cull, 0xfffffffffffffff2ull, 0xfffffffffffffffeull,
                0x0000000000000005ull}},
        {"2b add int32 -> int64", SNAX_OP_ADD, 8, 0, i32, i32, i64, add2_a, ones32,
            {0xfffffffffffffffeull, 0x6, 0x8, 0x0, 0x65, 0xffffffff80000000ull,
                0xffffffff80000001ull, 0x1}},
        {"3 mul int8 -> int32", SNAX_OP_MUL, 8, 0, i8, i8, i32,
            {0x000000000780fd64ull}, {0x00000000fe800503ull},
            {0xfffffff10000002cull, 0xfffffff200000000ull, 0x0, 0x0}},
        {"5 fold add int8 -> int32", SNAX_OP_ADD, 8, 1, i8, {}, i32,
            {0x00000000f200f12cull}, {}, {0x000000000000000full}},
        {"6a fold add int8 -> int32", SNAX_OP_ADD, 8, 1, i8, {}, i32,
            {0x00000000000005fdull}, {}, {0x2}},
        {"6b fold add uint8 -> int32", SNAX_OP_ADD, 8, 1, u8, {}, i32,
            {0x00000000000005fdull}, {}, {0x102}},
        {"7a max int8 -> int32", SNAX_OP_MAX, 8, 0, i8, i8, i32, {0x90}, {0x0},
            {0x0, 0x0, 0x0, 0x0}},
        {"7b max uint8 -> int32", SNAX_OP_MAX, 8, 0, u8, u8, i32, {0x90}, {0x0},
            {0x90, 0x0, 0x0, 0x0}},
        {"7c fold max int8 -> int16", SNAX_OP_MAX, 8, 1, i8, {}, i16,
            {0x0000000000001090ull}, {}, {0x10}},
        {"7d fold max uint8 -> int16", SNAX_OP_MAX, 8, 1, u8, {}, i16,
            {0x0000000000001090ull}, {}, {0x90}},
        {"8 add int8 + uint8 -> int16", SNAX_OP_ADD, 8, 0, i8, u8, i16,
            {0xffffffffffffffffull}, {0xffffffffffffffffull},
            {0x00fe00fe00fe00feull, 0x00fe00fe00fe00feull}},
        {"9 add int32 -> int16", SNAX_OP_ADD, 4, 0, i32, i32, i16,
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
            snax_op_elementwise(v.op, v.lanes, v.a_t, v.b_t, v.out_t, v.a.data(), v.b.data(),
                out.data());
        }
        else
        {
            uint64_t acc = 0;
            for (int n = 0; n < v.folds; n++)
            {
                acc = snax_op_fold(v.op, v.lanes, v.a_t, v.out_t, v.a.data(), n == 0, acc);
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
    for (auto check : {std::make_pair("ops", check_ops), std::make_pair("tree", check_tree),
        std::make_pair("types", check_types), std::make_pair("beats", check_beats)})
    {
        int errors = check.second(&count);
        printf("%s %s: %d vectors\n", errors ? "FAIL" : "PASS", check.first, count);
        failed += errors != 0;
        passed += errors == 0;
    }
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
