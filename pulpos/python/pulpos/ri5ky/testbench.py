# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import pulpos
from typing import cast, Any, List, Tuple
import gvrun.target
from ri5ky_testbench import Ri5kyTestbenchBoardConfig
from gvrun.parameter import BuildParameter
from pulpos.toolchain import RiscvGccToolchain, ToolchainConfig


class Ri5kyTestbenchPulposModule(pulpos.PulposModule):

    def __init__(self, target: gvrun.target.SystemTreeNode, container: pulpos.SourceContainer):
        super().__init__(target, parent=container)

        self.add_define('CONFIG_CHIP_NAME', 'ri5ky/testbench')
        self.add_define('CONFIG_CHIP_FAMILY_NAME', 'ri5ky/testbench')
        self.add_define('CONFIG_CHIP_RI5KY_TESTBENCH', '1')

        attr = cast(Ri5kyTestbenchBoardConfig, target.get_attributes())

        BuildParameter(self, 'linker_script', "link.ld", 'Linker script')

        if self.get_parameter('linker_script'):
            linker_script_template = f'arch/ri5ky/testbench/{self.get_parameter("linker_script")}'

            linker_script = self.new_template_file('linker_script', 'link.ld', linker_script_template)

            # The linker treats `0` as start of the default region (0x0..end)
            # which is exactly the testbench layout.
            linker_script.add_parameter('mem_start', attr.soc.mem_base)
            linker_script.add_parameter('mem_size', attr.soc.mem_size)

            self.add_ldflags([
                f'-T{linker_script.get_path()}'
            ])

        path = pulpos.get_home(self)

        self.add_define('__RV32__', '1')

        # Minimal ISA: integer + compressed + multiply. The ri5ky_gwt RTL
        # build instantiates the core with FPU=0 so we avoid F/D/Zfinx. The
        # GVSoC Ri5ky model handles a superset and runs the same binary.
        self.add_cflags([
            '-march=rv32imc_zicsr', '-mabi=ilp32'
        ])
        self.add_ldflags([
            '-march=rv32imc_zicsr', '-mabi=ilp32'
        ])

        self.add_sources(['arch/ri5ky/testbench/kernel/hal.c'])

        self.add_subdirectory(path, target)


class Ri5kyTestbenchPulposExecutable(pulpos.PulposExecutable):

    def __init__(self, name: str, target: gvrun.target.SystemTreeNode,
                 parameters: list[tuple[str, Any]] | None = None):

        ri5ky_parameters: list[tuple[str, Any]] = [
            ('pulpos/kernel.threading', False),
            ('pulpos/kernel.event', False),
        ]

        if parameters is not None:
            ri5ky_parameters = ri5ky_parameters + parameters

        super().__init__(name, target, parameters=ri5ky_parameters)

        toolchain = BuildParameter(self, 'toolchain', "gcc",
                                   'Toolchain to be used for compiling and linking').value

        if toolchain == 'gcc':
            config = ToolchainConfig(path_from_env='RISCV32_GCC_TOOLCHAIN')
            self.set_toolchain(RiscvGccToolchain(config))

        self.pulpos = Ri5kyTestbenchPulposModule(target, container=self)


def new_executable(name, target,
                   parameters: List[Tuple[str, Any]] | None = None):
    return Ri5kyTestbenchPulposExecutable(name, target, parameters=parameters)
