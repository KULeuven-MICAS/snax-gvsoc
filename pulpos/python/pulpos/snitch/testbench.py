# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from __future__ import annotations

import os
import pulpos
from typing import cast
import gvrun.target
import snitch_testbench
from typing import Any, List, Tuple
from snitch_testbench import SnitchTestbenchBoardConfig
from gvrun.parameter import BuildParameter
from pulpos.toolchain import RiscvGccToolchain, RiscvLlvmToolchain, ToolchainConfig

class SnitchTestbenchPulposModule(pulpos.PulposModule):

    def __init__(self, target: gvrun.target.SystemTreeNode, container: pulpos.SourceContainer):
        super().__init__(target, parent=container)

        self.add_define('CONFIG_CHIP_NAME', 'snitch/testbench')
        self.add_define('CONFIG_CHIP_FAMILY_NAME', 'snitch/testbench')
        self.add_define('CONFIG_CHIP_SNITCH_TESTBENCH', '1')

        attr = cast(SnitchTestbenchBoardConfig, target.get_attributes())

        BuildParameter(self, 'linker_script',  "link.ld", 'Linker script')

        if self.get_parameter('linker_script'):
            linker_script_template = f'arch/snitch/testbench/{self.get_parameter("linker_script")}'

            linker_script = self.new_template_file('linker_script', 'link.ld', linker_script_template)

            linker_script.add_parameter('mem_start', attr.soc.mem_l0_mapping.base)
            linker_script.add_parameter('mem_size', attr.soc.mem_l0_mapping.size)

            self.add_ldflags([
                f'-T{linker_script.get_path()}'
            ])

        path = pulpos.get_home(self)

        self.add_define('__RV32__', '1')

        self.add_cflags([
            '-march=rv32imafdc'
        ])
        self.add_ldflags([
            '-march=rv32imafdc'
        ])

        self.add_sources(['arch/snitch/testbench/kernel/hal.c'])

        self.add_subdirectory(path, target)



class SnitchTestbenchPulposExecutable(pulpos.PulposExecutable):


    def __init__(self, name: str, target: gvrun.target.SystemTreeNode,
            parameters: list[tuple[str, Any]] | None=None):

        snitch_parameters: list[tuple[str, Any]] = [
            ('pulpos/kernel.threading', False),
            ('pulpos/kernel.event', False),
        ]

        if parameters is not None:
            snitch_parameters = snitch_parameters + parameters

        super().__init__(name, target, parameters=snitch_parameters)


        toolchain = BuildParameter(self, 'toolchain',  "gcc", 'Toolchain to be used for compiling and linking').value

        if toolchain == 'gcc':
            config = ToolchainConfig(path_from_env='SNITCH_GCC_TOOLCHAIN')
            self.set_toolchain(RiscvGccToolchain(config))
        elif toolchain == 'llvm':
            config = ToolchainConfig(path_from_env='SNITCH_LLVM_TOOLCHAIN')
            self.set_toolchain(RiscvLlvmToolchain(config))

        self.pulpos = SnitchTestbenchPulposModule(target, container=self)


def new_executable(name, target,
        parameters:List[Tuple[str,Any]] | None=None):
    return SnitchTestbenchPulposExecutable(name, target, parameters=parameters)
