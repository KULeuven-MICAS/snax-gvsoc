// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

/**
 * @addtogroup interrupt_apis
 * @{
 */

/**
 * @brief Disable all interrupts.
 *
 * This function disables all interrupts on the processor.
 *
 * This can be used to enter a critical section where no interrupt routine will be executed.
 *
 * It returns the current state of the global interrupt enable so that it can be restored by calling
 * pi_irq_unlock() with the returned value.
 *
 * @return IRQ      Current interrupt state.
 */
static inline int pi_irq_lock();

/**
 * @brief Restore interrupts state.
 *
 * This function restores the state of the interrupts returned by the function pi_irq_lock().
 *
 * @param state     Interrupt state returned by pi_irq_lock().
 *
 * \note This function should be used in pair with pi_irq_lock() to define a critical section
 * where interrupt routines are not executed.
 */
static inline void pi_irq_unlock(int state);

/**
 * @brief Enable an interrupt.
 *
 * This function enables a specific interrupt, so that interrupt routines for this interrupt can be
 * received. The interrupt can still be disabled and enabled by the global lock.
 *
 * @param irq            Interrupt number.
 */
static inline void pi_irq_enable(int irq);

/**
 * @brief Disable an interrupt.
 *
 * This function disables a specific interrupt, so that interrupt routines for this interrupt can
 * not be received anymore.
 *
 * @param irq            Interrupt number.
 */
static inline void pi_irq_disable(int irq);

/**
 * @brief Set interrupt routine.
 *
 * This function sets the interrupt handler called when an interrupt occurs.
 *
 * @param irq            Interrupt number.
 * @param handler        Handler to execute.
 * @param arg            Argument given to the handler.
 */
void pi_irq_handler_set(int irq, void (*handler)(void *), void *arg);

/**
 * @brief Clear an interrupt status flag.
 *
 * When an interrupt occurs, a pending flag is set in the processor for this interrupt.
 * If this flag is not cleared when the interrupt routine is executed, this functions can
 * be called to clear it.
 *
 * @param irq            Interrupt number.
 */
static inline void pi_irq_clear(int irq);

/**
 * @brief Set an interrupt status flag.
 *
 * This can be used to software trigger an interrupt.
 *
 * @param irq            Interrupt number.
 */
static inline void pi_irq_set(int irq);

/**
 * @}
 */

#if defined(CONFIG_IRQ_INC)
#include CONFIG_IRQ_INC
#endif
