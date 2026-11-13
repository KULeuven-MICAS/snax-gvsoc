// Copyright 2026 KU Leuven.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

// What the g++ testbenches (unit, group, shell, datapath) share: a case's name,
// a dtype by name, the START outcomes, the PASS/FAIL tally and the case loop.

#pragma once

#include <cstdio>
#include <string>

#include "snax_types.hpp"

// A path's file name without its extension: a case's name
inline std::string tb_base_of(const std::string &path)
{
    size_t slash = path.rfind('/');
    std::string base = slash == std::string::npos ? path : path.substr(slash + 1);
    size_t dot = base.rfind('.');
    return dot == std::string::npos ? base : base.substr(0, dot);
}

// A NumPy integer type's name, int8 to uint64
inline bool tb_type_of(const std::string &name, SnaxType &t)
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

// What a START write did, as the cases name it
inline const char *const tb_start_names[] = {"taken", "ignored", "refused"};

// The PASS and FAIL counts; finish() prints the closing line and gives the exit code
struct TbTally
{
    int passed = 0, failed = 0;

    void add(int errors)
    {
        failed += errors != 0;
        passed += errors == 0;
    }

    int finish() const
    {
        printf("%d passed, %d failed\n", passed, failed);
        return failed ? 1 : 0;
    }
};

// main over case files: parse each, run it, print PASS or FAIL and its line (`line(c)`
// prints the rest, newline included); exit 2 on a file that does not parse
template <typename Case, typename Parse, typename Run, typename Line>
int tb_main(int argc, char **argv, Parse parse, Run run, Line line)
{
    if (argc < 2)
    {
        fprintf(stderr, "usage: %s CASE...\n", argv[0]);
        return 2;
    }
    TbTally tally;
    for (int i = 1; i < argc; i++)
    {
        Case c;
        if (!parse(argv[i], c))
        {
            return 2;
        }
        int errors = run(c);
        printf("%s ", errors ? "FAIL" : "PASS");
        line(c);
        tally.add(errors);
    }
    return tally.finish();
}
