// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

 #include <stdio.h>
 #include <stdint.h>
 #include <kernel/hal.h>

 static char __pi_libc_buffer[PI_LIBC_PUTC_BUFFER_SIZE];
 static int __pi_libc_buffer_index = 0;

void __pi_init_soc()
{
#ifdef CONFIG_SPATZ_MULTICORE
    // Counterpart of the barrier the secondary harts wait on in crt0.S:
    // hart 0 joins it here, at the end of the runtime initialization the
    // generic init flow drives (BSS, libc, constructors all done), which
    // releases the secondaries into main. The cluster hardware barrier
    // releases when every core has issued the load. Living in this port
    // hook keeps the generic kernel/init.c free of any multi-hart code.
    volatile uint32_t *barrier =
        (volatile uint32_t *)(CONFIG_CLUSTER_PERIPH_BASE + 0x40);
    (void)*barrier;
#endif
}

int __pi_libc_fputc_safe(int c, FILE *stream)
{
    char *buffer = __pi_libc_buffer;
    int *index = &__pi_libc_buffer_index;

    buffer[*index] = c;
    *index = *index + 1;

    if (*index == PI_LIBC_PUTC_BUFFER_SIZE || c == '\n')
    {
        buffer[*index] = 0;

        __pi_libc_write(1, (uint8_t *)buffer, *index);
        *index = 0;
    }

    return 0;
}
