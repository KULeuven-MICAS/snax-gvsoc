.. _threads:

Threads
#######

Threads are the fundamental unit of execution managed by the scheduler. They allow an
application to decompose complex workloads into multiple, independently scheduled execution
contexts that share a single core through cooperative and, optionally, preemptive multitasking.
Each thread maintains its own stack and saved register state, ensuring that local variables,
call chains, and execution flow are completely isolated from one another. The scheduler
multiplexes these threads on the core, transparently saving and restoring their contexts so that
each thread runs as if it had exclusive access to the processor.

Creating a Thread
*****************

A thread is created by calling :c:func:`pi_thread_create`. The caller supplies:

* A :c:type:`pi_thread_t` structure that holds the thread state.
* A human-readable name (used for debugging and profiling).
* An entry-point function and an opaque argument pointer.
* A priority level.
* A pointer to a caller-allocated stack buffer and its size.
* An optional event that is notified when the thread exits.

The new thread becomes ready to run as soon as :c:func:`pi_thread_create` returns.

Thread Priorities
*****************

Every thread is assigned a numeric priority at creation time. Higher numeric values represent
higher scheduling priority. When several threads are ready, the scheduler always picks the one
with the highest priority. Threads that share the same priority are served in round-robin order
using time-slicing.

Preemptive Time-Slicing
***********************

When preemptive scheduling is enabled, a hardware timer periodically interrupts the running
thread so the scheduler can re-evaluate which thread should execute. The slice duration is
configurable and expressed in microseconds.

Without preemption the scheduler is purely cooperative: a running thread keeps the core until
it voluntarily yields by waiting on an event or by exiting.

Regardless of the preemption setting, a higher-priority thread that becomes ready always
preempts a lower-priority thread at the next scheduling point.

Thread Exit and Joining
***********************

A thread terminates by returning from its entry function or by calling :c:func:`pi_thread_exit`.
If an event was provided at creation time, that event is notified upon exit, which lets another
thread wait for the completion and retrieve the exit status through
:c:func:`pi_thread_status_get`.

The exit status can be set at any time with :c:func:`pi_thread_status_set` before the thread
terminates.

Tasks
*****

Each thread owns a private task queue. When a thread is blocked waiting for an event, it
continues to drain and execute any tasks that have been posted to its queue (see the
:ref:`events` documentation for details on task events). This means a waiting thread is never
completely idle as long as tasks are available, which reduces latency and avoids dedicating
additional threads solely for deferred processing.

Interaction with Events
***********************

Threads and events are closely integrated. Calling :c:func:`pi_evt_sig_wait` blocks the
calling thread until the given event is notified. While blocked, the thread still processes its
task queue and may be temporarily switched out in favour of other ready threads.

Task events (:c:func:`pi_evt_task`) target a specific thread's task queue, allowing interrupt
handlers and other asynchronous producers to schedule tasks that will run safely in thread
context.

Sleep Behaviour
***************

When no thread is ready to run the core enters a low-power sleep state (``wfi``). It is woken
by the next interrupt, which may enqueue event callbacks or unblock a waiting thread. The
scheduler then resumes normal operation automatically.

API Reference
*************

.. doxygengroup:: thread_apis
