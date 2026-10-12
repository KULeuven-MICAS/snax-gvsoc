# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from config_tree import Config, cfg_field, env, Expressions
from build_tree.script_typing import *


class PulposConfig(Config):
    platform: str = cfg_field(default='gvsoc', write=True, read=True)
    os_name: str = cfg_field(default='pulpos', read=True)
    log: list[str] = cfg_field(default_factory=list, write=True, read=True)
    log_all: bool = cfg_field(default=False, write=True, read=True)
    log_level: str = cfg_field(default='error', write=True, read=True)
    use_llvm_toolchain: bool = cfg_field(default=False, write=True, read=True)
    include_lib: bool = cfg_field(default=True, write=True, read=True)

pulpos_sw = PulposConfig('pulpos_sw')

exports.pulpos_sw = pulpos_sw

exports.kernel = builder.add_submodule('kernel', parent_config=pulpos_sw)
exports.lib = builder.add_submodule('lib', parent_config=pulpos_sw)
