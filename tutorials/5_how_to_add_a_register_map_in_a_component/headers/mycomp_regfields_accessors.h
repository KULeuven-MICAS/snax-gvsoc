
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

#ifndef __ARCHI_REGMAP_REGFIELDS_ACCESSORS__
#define __ARCHI_REGMAP_REGFIELDS_ACCESSORS__

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

#include <stdint.h>
#include "archi/utils.h"

#endif




//
// REGISTERS FIELDS ACCESS FUNCTIONS
//

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

static inline __attribute__((always_inline)) void regmap_reg0_field0_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG0_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG0_OFFSET), value, 8, 0));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg0_field0_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG0_OFFSET), 8, 0);
}

static inline __attribute__((always_inline)) int32_t regmap_reg0_field0_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG0_OFFSET), 8, 0);
}


static inline __attribute__((always_inline)) void regmap_reg0_field1_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG0_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG0_OFFSET), value, 24, 8));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg0_field1_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG0_OFFSET), 24, 8);
}

static inline __attribute__((always_inline)) int32_t regmap_reg0_field1_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG0_OFFSET), 24, 8);
}


static inline __attribute__((always_inline)) void regmap_reg1_field0_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG1_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG1_OFFSET), value, 8, 0));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg1_field0_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 0);
}

static inline __attribute__((always_inline)) int32_t regmap_reg1_field0_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 0);
}


static inline __attribute__((always_inline)) void regmap_reg1_field1_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG1_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG1_OFFSET), value, 8, 8));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg1_field1_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 8);
}

static inline __attribute__((always_inline)) int32_t regmap_reg1_field1_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 8);
}


static inline __attribute__((always_inline)) void regmap_reg1_field2_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG1_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG1_OFFSET), value, 8, 16));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg1_field2_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 16);
}

static inline __attribute__((always_inline)) int32_t regmap_reg1_field2_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 16);
}


static inline __attribute__((always_inline)) void regmap_reg1_field3_set(uint32_t base, uint32_t value)
{
    GAP_WRITE(base, REGMAP_REG1_OFFSET, GAP_BINSERT(GAP_READ(base, REGMAP_REG1_OFFSET), value, 8, 24));
}

static inline __attribute__((always_inline)) uint32_t regmap_reg1_field3_get(uint32_t base)
{
    return GAP_BEXTRACTU(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 24);
}

static inline __attribute__((always_inline)) int32_t regmap_reg1_field3_gets(uint32_t base)
{
    return GAP_BEXTRACT(GAP_READ(base, REGMAP_REG1_OFFSET), 8, 24);
}


#endif

#endif
