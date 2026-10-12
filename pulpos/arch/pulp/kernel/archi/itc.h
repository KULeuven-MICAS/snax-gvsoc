// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once


#ifndef LANGUAGE_ASSEMBLY

#define GAP_WRITE_VOL(base, offset, value) __builtin_pulp_write_base_off_v((value), (base), (offset))
#define GAP_WRITE(base, offset, value)     \
({ __asm__ __volatile__ ("" : : : "memory"); \
    *(volatile uint32_t *)((base) + (offset)) = value; \
    __asm__ __volatile__ ("" : : : "memory"); \
})
#define GAP_READ(base, offset)             \
({ __asm__ __volatile__ ("" : : : "memory"); \
    uint32_t result = *(volatile uint32_t *)((base) + (offset)); \
    __asm__ __volatile__ ("" : : : "memory"); \
    result; \
})
#define GAP_WRITE_PTR(base, offset, value) __builtin_pulp_OffsetedWritePtr((int *)(value), (int *)(base), (offset))

#endif



#define ITC_MASK_OFFSET                          0x0

#define ITC_MASK_SET_OFFSET                      0x4

#define ITC_MASK_CLR_OFFSET                      0x8

#define ITC_STATUS_OFFSET                        0xc

#define ITC_STATUS_SET_OFFSET                    0x10

#define ITC_STATUS_CLR_OFFSET                    0x14

#define ITC_ACK_OFFSET                           0x18

#define ITC_ACK_SET_OFFSET                       0x1c

#define ITC_ACK_CLR_OFFSET                       0x20

#define ITC_FIFO_OFFSET                          0x24






#if !defined(LANGUAGE_ASSEMBLY) && !defined(ASSEMBLY_LANGUAGE)

static inline uint32_t itc_mask_get(uint32_t base) { return GAP_READ(base, ITC_MASK_OFFSET); }
static inline void itc_mask_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_MASK_OFFSET, value); }

static inline uint32_t itc_mask_set_get(uint32_t base) { return GAP_READ(base, ITC_MASK_SET_OFFSET); }
static inline void itc_mask_set_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_MASK_SET_OFFSET, value); }

static inline uint32_t itc_mask_clr_get(uint32_t base) { return GAP_READ(base, ITC_MASK_CLR_OFFSET); }
static inline void itc_mask_clr_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_MASK_CLR_OFFSET, value); }

static inline uint32_t itc_status_get(uint32_t base) { return GAP_READ(base, ITC_STATUS_OFFSET); }
static inline void itc_status_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_STATUS_OFFSET, value); }

static inline uint32_t itc_status_set_get(uint32_t base) { return GAP_READ(base, ITC_STATUS_SET_OFFSET); }
static inline void itc_status_set_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_STATUS_SET_OFFSET, value); }

static inline uint32_t itc_status_clr_get(uint32_t base) { return GAP_READ(base, ITC_STATUS_CLR_OFFSET); }
static inline void itc_status_clr_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_STATUS_CLR_OFFSET, value); }

static inline uint32_t itc_ack_get(uint32_t base) { return GAP_READ(base, ITC_ACK_OFFSET); }
static inline void itc_ack_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_ACK_OFFSET, value); }

static inline uint32_t itc_ack_set_get(uint32_t base) { return GAP_READ(base, ITC_ACK_SET_OFFSET); }
static inline void itc_ack_set_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_ACK_SET_OFFSET, value); }

static inline uint32_t itc_ack_clr_get(uint32_t base) { return GAP_READ(base, ITC_ACK_CLR_OFFSET); }
static inline void itc_ack_clr_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_ACK_CLR_OFFSET, value); }

static inline uint32_t itc_fifo_get(uint32_t base) { return GAP_READ(base, ITC_FIFO_OFFSET); }
static inline void itc_fifo_set(uint32_t base, uint32_t value) { GAP_WRITE(base, ITC_FIFO_OFFSET, value); }

#endif
