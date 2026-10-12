// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#include <pmsis/kernel/kernel.h>
#include <kernel/riscv.h>
#include <arch/pulp/kernel/archi/itc.h>
#include PI_CHIP_INC(CONFIG_CHIP_FAMILY_NAME, kernel/memory_map.h)

void __pi_irq_init();

static inline int pi_irq_lock()
{
    int state;
    asm volatile("csrrc %0, %1, %2" : "=r" (state) : "I" (CSR_MSTATUS), "I" (1 << CSR_MSTATUS_MIE_BIT): "memory");
    // This memory barrier is needed to prevent the compiler to cross the irq barrier
    __asm__ __volatile__ ("" : : : "memory");
    return state;
}

static inline void pi_irq_unlock(int state)
{
    // This memory barrier is needed to prevent the compiler to cross the irq barrier
    __asm__ __volatile__ ("" : : : "memory");
    asm volatile ("csrw %0, %1" :  : "I" (CSR_MSTATUS), "r" (state));
}

static inline void pi_irq_enable(int irq)
{
    itc_mask_set_set(SOC_FC_ITC_ADDR, 1 << irq);
}

static inline void pi_irq_disable(int irq)
{
    itc_mask_clr_set(SOC_FC_ITC_ADDR, 1 << irq);
}

static inline void __pi_irq_mask_enable(uint32_t mask)
{
    itc_mask_set_set(SOC_FC_ITC_ADDR, mask);
}

static inline void __pi_irq_mask_disable(uint32_t mask)
{
    itc_mask_clr_set(SOC_FC_ITC_ADDR, mask);
}

static inline void __pi_irq_mask_clear(uint32_t mask)
{
    itc_status_clr_set(SOC_FC_ITC_ADDR, mask);
}

static inline void pi_irq_clear(int irq)
{
    itc_status_clr_set(SOC_FC_ITC_ADDR, 1 << irq);
}

static inline void pi_irq_set(int irq)
{
    itc_status_set_set(SOC_FC_ITC_ADDR, 1 << irq);
}
