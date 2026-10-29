/*
 * Copyright 2026 KU Leuven.
 * Licensed under the Apache License, Version 2.0, see LICENSE for details.
 * SPDX-License-Identifier: Apache-2.0
 */

// SnaxProps: the SNAX components' checked property readers (get_js_config).
// A missing property, one of the wrong type, or an element width other than
// 8, 16, 32 or 64 is a fatal error on the component's trace naming its path:
// "Property csr_base: missing", "Property units[0].in_widths[1]: 12, must be
// 8, 16, 32 or 64". where is the path of config ("" for the component's own,
// "units[0]", "movers[2]").

#pragma once

#include <string>
#include <vector>
#include <vp/vp.hpp>


class SnaxProps
{
public:
    explicit SnaxProps(vp::Trace *trace) : trace(trace) {}

    // where.name, or name at the top
    static std::string path(const std::string &where, const std::string &name)
    {
        return where.empty() ? name : where + "." + name;
    }

    js::Config *prop(js::Config *config, const char *name, const std::string &where)
    {
        js::Config *value = config->get(name);
        if (value == nullptr)
        {
            this->trace->fatal("Property %s: missing\n", path(where, name).c_str());
        }
        return value;
    }

    // value as a number, path naming it in the error
    int as_int(js::Config *value, const std::string &path)
    {
        if (dynamic_cast<js::ConfigNumber *>(value) == nullptr)
        {
            this->trace->fatal("Property %s: not a number\n", path.c_str());
        }
        return value->get_int();
    }

    bool as_bool(js::Config *value, const std::string &path)
    {
        if (dynamic_cast<js::ConfigBool *>(value) == nullptr)
        {
            this->trace->fatal("Property %s: not a bool\n", path.c_str());
        }
        return value->get_bool();
    }

    std::string as_str(js::Config *value, const std::string &path)
    {
        if (dynamic_cast<js::ConfigString *>(value) == nullptr)
        {
            this->trace->fatal("Property %s: not a string\n", path.c_str());
        }
        return value->get_str();
    }

    std::vector<js::Config *> as_list(js::Config *value, const std::string &path)
    {
        if (dynamic_cast<js::ConfigArray *>(value) == nullptr)
        {
            this->trace->fatal("Property %s: not a list\n", path.c_str());
        }
        return value->get_elems();
    }

    // An element width: 8, 16, 32 or 64 bits
    int as_width(js::Config *value, const std::string &path)
    {
        int w = this->as_int(value, path);
        if (w != 8 && w != 16 && w != 32 && w != 64)
        {
            this->trace->fatal("Property %s: %d, must be 8, 16, 32 or 64\n", path.c_str(), w);
        }
        return w;
    }

    int int_prop(js::Config *config, const char *name, const std::string &where)
    {
        return this->as_int(this->prop(config, name, where), path(where, name));
    }

    bool bool_prop(js::Config *config, const char *name, const std::string &where)
    {
        return this->as_bool(this->prop(config, name, where), path(where, name));
    }

    std::string str_prop(js::Config *config, const char *name, const std::string &where)
    {
        return this->as_str(this->prop(config, name, where), path(where, name));
    }

    std::vector<js::Config *> list_prop(js::Config *config, const char *name,
        const std::string &where)
    {
        return this->as_list(this->prop(config, name, where), path(where, name));
    }

    int width_prop(js::Config *config, const char *name, const std::string &where)
    {
        return this->as_width(this->prop(config, name, where), path(where, name));
    }

private:
    vp::Trace *trace;
};
