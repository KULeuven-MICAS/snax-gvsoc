# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from config_tree import Config, cfg_field, env
from build_tree.script_typing import *


class LibcSoftwareConfig(Config):
    minimal: bool = cfg_field(default=True, write=True, read=True,
                              desc='Include minimal libc.')
    io_device: str = cfg_field(default='semihost', write=True, read=True,
                               desc='Device for libc I/O (semihost, stdout).')


libc_sw = LibcSoftwareConfig('libc_sw')

os_src = get_os_src()
os_src.with_define('CONFIG_LIBC', 1)
set_os_src(os_src)

with builder.if_(libc_sw.get_ref('minimal')):
    exports.minimal = builder.add_submodule('minimal', parent_config=libc_sw)

exports.libc_sw = libc_sw
