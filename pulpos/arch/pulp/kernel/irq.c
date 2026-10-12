// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#include <stdint.h>
#include <pmsis/kernel/memory.h>
#include <pmsis/kernel/irq.h>
#include <kernel/riscv.h>
#include <kernel/hal.h>

PI_MEMORY_TINY uint_t __pi_irq_handlers[32];
PI_MEMORY_TINY uint_t __pi_irq_handlers_arg[32];

void pi_irq_handler_set(int irq, void (*handler)(void *arg), void *arg)
{
    __pi_irq_handlers[irq] = (long)handler;
    __pi_irq_handlers_arg[irq] = (long)arg;
}

void __pi_irq_init()
{
    // We may enter the runtime with some interrupts active for example
    // if we force the boot to jump to the runtime through jtag.
    __pi_irq_mask_disable(-1);
    __pi_irq_mask_clear(-1);

    // As the FC code may not be at the beginning of the L2, set the
    // vector base to get proper interrupt handlers
    uintptr_t base = __pi_linker_irq_vector_base();
    asm volatile ("csrw %0, %1" :  : "I" (CSR_MTVEC), "r" (base) );
}

void pi_irq_handle_exception()
{
}
