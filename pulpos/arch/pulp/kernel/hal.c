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
