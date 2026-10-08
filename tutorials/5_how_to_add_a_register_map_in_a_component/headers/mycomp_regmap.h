
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

#ifndef __ARCHI_REGMAP_REGMAP__
#define __ARCHI_REGMAP_REGMAP__

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

#include <stdint.h>

#endif




//
// REGISTERS GLOBAL STRUCT
//

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

/** REGMAP_Type Register Layout Typedef */
typedef struct {
    volatile uint32_t reg0;  // Register 0
    volatile uint32_t reg1;  // Register 1
} __attribute__((packed)) regmap_t;
/** REGMAP_Type Register Layout Typedef */
typedef struct {

    volatile regmap_reg0_t reg0;  // Register 0
    volatile regmap_reg1_t reg1;  // Register 1
} __attribute__((packed)) regmap_struct_t;

#endif  /* LANGUAGE_ASSEMBLY || __ASSEMBLER__ */

#endif
