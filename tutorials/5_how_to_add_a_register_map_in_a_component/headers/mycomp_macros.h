
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

#ifndef __ARCHI_REGMAP_MACROS__
#define __ARCHI_REGMAP_MACROS__

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

#include "archi/utils.h"

#endif




//
// REGISTERS FIELDS MACROS
//

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

#define REGMAP_REG0_FIELD0_GET(value)                      (GAP_BEXTRACTU((value),8,0))
#define REGMAP_REG0_FIELD0_GETS(value)                     (GAP_BEXTRACT((value),8,0))
#define REGMAP_REG0_FIELD0_SET(value,field)                (GAP_BINSERT((value),(field),8,0))
#define REGMAP_REG0_FIELD0(val)                            ((val) << 0)

#define REGMAP_REG0_FIELD1_GET(value)                      (GAP_BEXTRACTU((value),24,8))
#define REGMAP_REG0_FIELD1_GETS(value)                     (GAP_BEXTRACT((value),24,8))
#define REGMAP_REG0_FIELD1_SET(value,field)                (GAP_BINSERT((value),(field),24,8))
#define REGMAP_REG0_FIELD1(val)                            ((val) << 8)

#define REGMAP_REG1_FIELD0_GET(value)                      (GAP_BEXTRACTU((value),8,0))
#define REGMAP_REG1_FIELD0_GETS(value)                     (GAP_BEXTRACT((value),8,0))
#define REGMAP_REG1_FIELD0_SET(value,field)                (GAP_BINSERT((value),(field),8,0))
#define REGMAP_REG1_FIELD0(val)                            ((val) << 0)

#define REGMAP_REG1_FIELD1_GET(value)                      (GAP_BEXTRACTU((value),8,8))
#define REGMAP_REG1_FIELD1_GETS(value)                     (GAP_BEXTRACT((value),8,8))
#define REGMAP_REG1_FIELD1_SET(value,field)                (GAP_BINSERT((value),(field),8,8))
#define REGMAP_REG1_FIELD1(val)                            ((val) << 8)

#define REGMAP_REG1_FIELD2_GET(value)                      (GAP_BEXTRACTU((value),8,16))
#define REGMAP_REG1_FIELD2_GETS(value)                     (GAP_BEXTRACT((value),8,16))
#define REGMAP_REG1_FIELD2_SET(value,field)                (GAP_BINSERT((value),(field),8,16))
#define REGMAP_REG1_FIELD2(val)                            ((val) << 16)

#define REGMAP_REG1_FIELD3_GET(value)                      (GAP_BEXTRACTU((value),8,24))
#define REGMAP_REG1_FIELD3_GETS(value)                     (GAP_BEXTRACT((value),8,24))
#define REGMAP_REG1_FIELD3_SET(value,field)                (GAP_BINSERT((value),(field),8,24))
#define REGMAP_REG1_FIELD3(val)                            ((val) << 24)

#endif

#endif
