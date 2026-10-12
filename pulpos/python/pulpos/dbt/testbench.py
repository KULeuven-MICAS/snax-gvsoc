# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any, List, Tuple

import pulpos
import gvrun.target
from gvrun.parameter import BuildParameter
from pulpos.toolchain import RiscvGccToolchain, ToolchainConfig
from pulpos.ri5ky.testbench import Ri5kyTestbenchPulposModule


class DbtTestbenchPulposModule(Ri5kyTestbenchPulposModule):
    """PulpOS module for the DBT core testbench.

    The platform layout (mem at 0x0, MMIO putchar/exit at 0x1000_0000,
    boot at 0x80) is the ri5ky testbench one, so the linker script and
    HAL are reused. Only the ISA differs: the DBT core is a standard
    rv32imafc_zfinx, so the firmware is compiled with atomics and
    fence.i available (the trailing -march overrides the base one).
    """

    def __init__(self, target: gvrun.target.SystemTreeNode, container: pulpos.SourceContainer):
        super().__init__(target, container)

        self.add_cflags(['-march=rv32imac_zicsr_zifencei'])
        self.add_ldflags(['-march=rv32imac_zicsr_zifencei'])


class DbtTestbenchPulposExecutable(pulpos.PulposExecutable):

    def __init__(self, name: str, target: gvrun.target.SystemTreeNode,
                 parameters: list[tuple[str, Any]] | None = None):

        dbt_parameters: list[tuple[str, Any]] = [
            ('pulpos/kernel.threading', False),
            ('pulpos/kernel.event', False),
        ]

        if parameters is not None:
            dbt_parameters = dbt_parameters + parameters

        super().__init__(name, target, parameters=dbt_parameters)

        toolchain = BuildParameter(self, 'toolchain', "gcc",
                                   'Toolchain to be used for compiling and linking').value

        if toolchain == 'gcc':
            config = ToolchainConfig(path_from_env='RISCV32_GCC_TOOLCHAIN')
            self.set_toolchain(RiscvGccToolchain(config))

        self.pulpos = DbtTestbenchPulposModule(target, container=self)


def new_executable(name, target,
                   parameters: List[Tuple[str, Any]] | None = None):
    return DbtTestbenchPulposExecutable(name, target, parameters=parameters)
