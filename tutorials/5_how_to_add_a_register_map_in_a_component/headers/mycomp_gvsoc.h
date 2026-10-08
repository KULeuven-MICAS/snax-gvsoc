
/* THIS FILE HAS BEEN GENERATED, DO NOT MODIFY IT.
 */

/*
 * Copyright (C) GreenWaves Technologies, ETH Zurich and University of Bologna
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef __ARCHI_REGMAP_GVSOC__
#define __ARCHI_REGMAP_GVSOC__

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

#include <stdint.h>

#endif




//
// REGISTERS STRUCTS
//

#ifdef __GVSOC__

class vp_regmap_reg0 : public vp::Register<uint32_t>
{
public:
    inline void field0_set(uint32_t value) { this->set_field(value, REGMAP_REG0_FIELD0_BIT, REGMAP_REG0_FIELD0_WIDTH); }
    inline uint32_t field0_get() { return this->get_field(REGMAP_REG0_FIELD0_BIT, REGMAP_REG0_FIELD0_WIDTH); }
    inline void field1_set(uint32_t value) { this->set_field(value, REGMAP_REG0_FIELD1_BIT, REGMAP_REG0_FIELD1_WIDTH); }
    inline uint32_t field1_get() { return this->get_field(REGMAP_REG0_FIELD1_BIT, REGMAP_REG0_FIELD1_WIDTH); }
    vp_regmap_reg0(vp::Block &top, std::string name) : vp::Register<uint32_t>(top, name, 32, true, 0)
    {
        this->name = "REG0";
        this->offset = 0x0;
        this->width = 32;
        this->do_reset = 1;
        this->write_mask = 0xffffffff;
        this->reset_val = 0x0;
        this->regfields.push_back(new vp::regfield("FIELD0", 0, 8));
        this->regfields.push_back(new vp::regfield("FIELD1", 8, 24));
    }
};

class vp_regmap_reg1 : public vp::Register<uint32_t>
{
public:
    inline void field0_set(uint32_t value) { this->set_field(value, REGMAP_REG1_FIELD0_BIT, REGMAP_REG1_FIELD0_WIDTH); }
    inline uint32_t field0_get() { return this->get_field(REGMAP_REG1_FIELD0_BIT, REGMAP_REG1_FIELD0_WIDTH); }
    inline void field1_set(uint32_t value) { this->set_field(value, REGMAP_REG1_FIELD1_BIT, REGMAP_REG1_FIELD1_WIDTH); }
    inline uint32_t field1_get() { return this->get_field(REGMAP_REG1_FIELD1_BIT, REGMAP_REG1_FIELD1_WIDTH); }
    inline void field2_set(uint32_t value) { this->set_field(value, REGMAP_REG1_FIELD2_BIT, REGMAP_REG1_FIELD2_WIDTH); }
    inline uint32_t field2_get() { return this->get_field(REGMAP_REG1_FIELD2_BIT, REGMAP_REG1_FIELD2_WIDTH); }
    inline void field3_set(uint32_t value) { this->set_field(value, REGMAP_REG1_FIELD3_BIT, REGMAP_REG1_FIELD3_WIDTH); }
    inline uint32_t field3_get() { return this->get_field(REGMAP_REG1_FIELD3_BIT, REGMAP_REG1_FIELD3_WIDTH); }
    vp_regmap_reg1(vp::Block &top, std::string name) : vp::Register<uint32_t>(top, name, 32, true, 0)
    {
        this->name = "REG1";
        this->offset = 0x4;
        this->width = 32;
        this->do_reset = 1;
        this->write_mask = 0xffffffff;
        this->reset_val = 0x0;
        this->regfields.push_back(new vp::regfield("FIELD0", 0, 8));
        this->regfields.push_back(new vp::regfield("FIELD1", 8, 8));
        this->regfields.push_back(new vp::regfield("FIELD2", 16, 8));
        this->regfields.push_back(new vp::regfield("FIELD3", 24, 8));
    }
};


class vp_regmap_regmap : public vp::regmap
{
public:
    vp_regmap_reg0 reg0;
    vp_regmap_reg1 reg1;
    vp_regmap_regmap(vp::Block &top, std::string name): vp::regmap(top, name),
        reg0(*this, "reg0"),
        reg1(*this, "reg1")
    {
        this->registers_new.push_back(&this->reg0);
        this->registers_new.push_back(&this->reg1);
    }
};

#endif

#endif
