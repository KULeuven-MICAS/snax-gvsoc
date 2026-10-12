.. _time:

Time
####

The Time API provides time-related services built on top of hardware timers. It offers the
following features:

Global Time Tracking
====================

A 64-bit software-emulated microsecond clock that tracks elapsed time since runtime boot.
The underlying hardware timer runs with prescaling configured so that each tick is
approximately one microsecond. A periodic interrupt updates the global time, and reading the
current timer value provides microsecond-level precision. The time can be retrieved with
:c:func:`pi_time_get_us`.

Blocking Delays
===============

A thread can block for a specified duration in microseconds using :c:func:`pi_time_wait_us`.
This suspends the calling thread until the delay elapses.

Delayed Event Notification
==========================

Events can be scheduled for notification after a specified delay using
:c:func:`pi_evt_notify_delayed`. Delayed events are maintained in a sorted linked list ordered
by increasing timestamp. A dedicated hardware timer in one-shot mode triggers an interrupt
when the earliest event's deadline is reached, at which point the event is dequeued and
notified. An unsafe variant, :c:func:`pi_evt_notify_delayed_unsafe`, is provided for use from
interrupt handlers or other contexts where interrupts are already disabled, avoiding
redundant interrupt lock/unlock overhead.

Timed Event Cancellation
=========================

A pending timed event can be cancelled with :c:func:`pi_evt_timed_cancel`, which removes it
from the delayed event queue so it can be safely reused. A safe-caller variant,
:c:func:`pi_evt_timed_cancel_safe`, is available for use from interrupt-disabled contexts.

Thread Time-Slicing
===================

When thread preemption is enabled, the uptime timer also drives cooperative/preemptive
thread scheduling by generating periodic interrupts at a configurable slice interval.
At each slice boundary, the runtime checks whether the current thread should be preempted.

The implementation uses two hardware timers: one for uptime tracking and thread slicing
(running in continuous mode), and another for delayed events (running in one-shot mode).
Both timers support dynamic clock source and frequency reconfiguration.

API Reference
=============

.. doxygengroup:: time_apis
