
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

#ifndef __ARCHI_REGMAP_STRUCTS__
#define __ARCHI_REGMAP_STRUCTS__

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)


#endif




//
// REGISTERS STRUCTS
//

#if !defined(LANGUAGE_ASSEMBLY) && !defined(__ASSEMBLER__)

typedef union {
  struct {
    unsigned int field0          :8 ; // Field 0
    unsigned int field1          :24; // Field 1
  };
  unsigned int raw;
} __attribute__((packed)) regmap_reg0_t;

typedef union {
  struct {
    unsigned int field0          :8 ; // Field 0
    unsigned int field1          :8 ; // Field 1
    unsigned int field2          :8 ; // Field 2
    unsigned int field3          :8 ; // Field 3
  };
  unsigned int raw;
} __attribute__((packed)) regmap_reg1_t;

#endif

#endif
