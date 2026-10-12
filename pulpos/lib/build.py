# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from config_tree import Config, cfg_field
from build_tree.script_typing import *


class LibSoftwareConfig(Config):
    libc_enabled: bool = cfg_field(default=True, write=True, read=True)
    printf: bool = cfg_field(default=True, write=True, read=True)


lib_sw = LibSoftwareConfig('lib_sw')

with builder.if_(lib_sw.get_ref('libc_enabled')):
    exports.libc = builder.add_submodule('libc', parent_config=lib_sw)

exports.lib_sw = lib_sw
