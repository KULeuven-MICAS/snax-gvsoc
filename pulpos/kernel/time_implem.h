
#pragma once

#include <pmsis/kernel/irq.h>
#include <pmsis/kernel/event.h>

ALWAYS_INLINE void pi_evt_timed_cancel(pi_evt_t *event)
{
    int irq = pi_irq_lock();
    pi_evt_timed_cancel_unsafe(event);
    pi_irq_unlock(irq);
}

ALWAYS_INLINE void pi_evt_notify_delayed(pi_evt_t *event, uint32_t delay)
{
    int irq = pi_irq_lock();
    pi_evt_notify_delayed_unsafe(event, delay);
    pi_irq_unlock(irq);
}
