# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from config_tree import env
from build_tree.script_typing import *

os_src = get_os_src()

os_src.with_include(env('PULPOS_HOME') + '/include/pmsis/lib/libc/minimal')
os_src.with_define('CONFIG_LIBC_MINIMAL', 1)

# I/O device define — mirrors libc/config.py CONFIG_LIBC_IO_{SEMIHOST,STDOUT}
libc_sw = builder.get_single_config_by_path('**/libc_sw')
with builder.if_(libc_sw.get_ref('io_device') == 'semihost'):
    os_src.with_define('CONFIG_LIBC_IO_SEMIHOST', 1)
with builder.if_(libc_sw.get_ref('io_device') == 'stdout'):
    os_src.with_define('CONFIG_LIBC_IO_STDOUT', 1)

os_src.add(
    'io.c',
    'string.c',
)

# printf sources — controlled by parent lib_sw config
lib_sw = builder.get_single_config_by_path('**/lib_sw')
with builder.if_(lib_sw.get_ref('printf')):
    os_src.add(
        'prf.c',
        'fprintf.c',
        'sprintf.c',
    )

set_os_src(os_src)
