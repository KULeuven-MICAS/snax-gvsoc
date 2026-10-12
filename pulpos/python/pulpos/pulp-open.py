# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from __future__ import annotations

from pulpos import PulposModule, SourceContainer, PulposExecutable, get_home
from typing import cast, Any
from gvrun.systree import SystemTreeNode
import os
import pulpos
from typing import cast
import gvrun.target
from gvrun.parameter import BuildParameter
from pulpos.toolchain import RiscvGccToolchain, ToolchainConfig
from pulp.chips.pulp_open.pulp_open import PulpOpenAttr

class PulpOpenPulposModule(PulposModule):

    def __init__(self, target: SystemTreeNode, container: SourceContainer):
        super().__init__(target, parent=container)

        self.add_define('CONFIG_CHIP_NAME', 'pulp_open')
        self.add_define('CONFIG_CHIP_FAMILY_NAME', 'pulp')
        self.add_define('CONFIG_CHIP_PULP_OPEN', '1')

        attr = cast(PulpOpenAttr, target.get_attributes())

        _ = BuildParameter(self, 'linker_script',  "link.ld", 'Linker script')

        if self.get_parameter('linker_script'):
            linker_script_template = f'arch/pulp/kernel/{self.get_parameter("linker_script")}'

            linker_script = self.new_template_file('linker_script', 'link.ld', linker_script_template)

            linker_script.add_parameter('mem_start', attr.soc.l2.range.base)
            linker_script.add_parameter('mem_size', attr.soc.l2.range.size)

            self.add_ldflags([
                f'-T{linker_script.get_path()}'
            ])

        path: str = get_home(self)

        self.add_define('__RV32__', '1')

        self.add_cflags([
            '-march=rv32imcxgap9 -mnohwloop'
        ])
        self.add_ldflags([
            '-march=rv32imcxgap9'
        ])

        self.add_define('CONFIG_ISA_PULPV2', 1)

        self.add_define('CONFIG_IRQ_INC', '<arch/pulp/kernel/irq.h>')
        self.add_define('CONFIG_MEMORY_INC', '<arch/pulp/kernel/memory.h>')

        self.add_sources([
            'arch/pulp/kernel/hal.c',
            'arch/pulp/kernel/irq.c',
            'arch/pulp/kernel/irq_asm.S',
        ])

        self.add_subdirectory(path, target)



class PulpOpenPulposExecutable(PulposExecutable):

    def __init__(self, name: str, target: SystemTreeNode,
            parameters:list[tuple[str,Any]] | None=None):
        super().__init__(name, target, parameters=parameters)

        toolchain: str = BuildParameter(self, 'toolchain',  "gcc", 'Toolchain to be used for compiling and linking').value

        if toolchain == 'gcc':
            config = ToolchainConfig(path_from_env='PULP_OPEN_GCC_TOOLCHAIN')
            self.set_toolchain(RiscvGccToolchain(config))

        self.pulpos: PulpOpenPulposModule = PulpOpenPulposModule(target, container=self)


def new_executable(name: str, target: SystemTreeNode,
        parameters:list[tuple[str,Any]] | None=None):
    return PulpOpenPulposExecutable(name, target, parameters=parameters)
