.. _events:

Events
######

Events provide a mechanism for asynchronous operations to signal their completion.

Traditional synchronous API functions can block the calling thread when they need to wait for
resources, such as responses from hardware devices. This blocking behavior often necessitates
the use of multiple threads to maintain application responsiveness while one thread waits.

However, multithreading introduces overhead: each thread requires its own stack, increasing
memory footprint, and context switches between threads consume additional energy and processing time.

Asynchronous operations offer a more efficient alternative. For any API function that may block,
an asynchronous variant is available, identified by the *_async* suffix. These asynchronous
functions return immediately, before the operation completes, and accept a :c:type:`pi_evt_t`
event object as an additional parameter to signal completion.

The typical workflow is:

1. Initialize an event object with the desired notification method
2. Call the asynchronous function with the event object
3. Continue with other work
4. React to the notification when the operation completes

Events can be configured in three different forms, each suited to different use cases.

Signal Events
*************

With signal events, the caller initializes the event using :c:func:`pi_evt_sig_init`, initiates
an asynchronous operation, continues with other tasks, and then explicitly waits for the event
by calling :c:func:`pi_evt_sig_wait` when the result is needed. The wait call blocks the
caller until the asynchronous operation signals completion. This approach is useful when the
calling thread can productively work on other tasks before needing the result.

Callback Events
***************

Callback events provide immediate notification through a function pointer supplied during event
initialization with :c:func:`pi_evt_cb_init`. When the asynchronous operation completes, it invokes
the callback function directly, potentially from within an interrupt context. This form enables
the fastest possible response to completion but requires the callback to be interrupt-safe and
to execute quickly.

Tasks
*****

Tasks provide deferred notification through a work queue system. The event is initialized using
:c:func:`pi_evt_task_init` with a callback and a target thread. Instead of executing the notification
callback immediately (potentially from interrupt context), the callback is scheduled on the
target thread's work queue. This approach combines the benefits of asynchronous notification
with the safety of executing callbacks in thread context rather than interrupt context, making it
suitable for callbacks that require more processing time or need to call blocking functions.


Event Status
************

Each event carries a status value that can be used to communicate the outcome of the
asynchronous operation. :c:func:`pi_evt_status_get` retrieves the current status of the
event, while :c:func:`pi_evt_status_set` allows setting it. This is typically used by the
asynchronous operation to indicate success or an error code, which the caller can then
inspect after the event has been notified.


API Reference
*************

.. doxygengroup:: event_apis
