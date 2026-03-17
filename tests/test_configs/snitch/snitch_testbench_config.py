# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2020 ETH Zurich and University of Bologna

from config_tree import Config, cfg_field
from tests.test_configs.snitch.memory_config import MemoryConfig
from tests.test_configs.snitch.snitch_core_config import SnitchCoreConfig

# Disable repr to avoid displaying long name in tree
class SnitchTestbenchConfig(Config):
    """Configuration for Snitch testbench.

    This class defines the configuration parameters for a Snitch testbench,
    including memory hierarchies and address layout.

    Attributes:
    ----------
    base_addr: int
        Base address of the module.
    """

    base_addr: int = cfg_field(default=0x8000_0000, fmt="hex", read=True, desc=(
        "Base address of the module"
    ))

    core: SnitchCoreConfig = cfg_field(init=False, desc=(
        "Main core configuration"
    ))

    mem_l0: MemoryConfig = cfg_field(init=False, desc=(
        "Memory with low latency"
    ))

    mem_l1: MemoryConfig = cfg_field(init=False, desc=(
        "Memory with mid latency"
    ))

    mem_l2: MemoryConfig = cfg_field(init=False, desc=(
        "Memory with high latency"
    ))

    def __post_init__(self):
        super().__post_init__()

        self.core = SnitchCoreConfig('core', isa='rv32imfdca', nb_outstanding=8)
        self.mem_l0 = MemoryConfig('mem_l0', base=self.base_addr + 0x0000_0000, size=0x10_0000, atomics=True, latency=0)
        self.mem_l1 = MemoryConfig('mem_l1', base=self.base_addr + 0x0010_0000, size=0x10_0000, atomics=True, latency=10)
        self.mem_l2 = MemoryConfig('mem_l2', base=self.base_addr + 0x0020_0000, size=0x10_0000, atomics=True, latency=1000)


class SnitchTestbenchBoardConfig(Config):

    frequency: int = cfg_field(default=10000000, read=True, desc=(
        "Frequency in Hz of the SoC"
    ))

    base_addr: int = cfg_field(default=0x8000_0000, read=True, inlined_dump=True, fmt="hex", desc=(
        "Base address of the module"
    ))

    soc: SnitchTestbenchConfig = cfg_field(init=False, desc=(
        "Snitch testbench configuration"
    ))

    def __post_init__(self):
        super().__post_init__()
        self.soc = SnitchTestbenchConfig('soc', base_addr=self.base_addr)


class SnitchTestbenchMultiBoardConfig(Config):

    nb_boards: int = cfg_field(default=2, read=True, desc=(
        "Number of boards"
    ))

    boards: list[SnitchTestbenchBoardConfig] = cfg_field(init=False, desc=(
        "Boards configs"
    ))

    def __post_init__(self):
        super().__post_init__()

        self.boards = []
        base_addr = 0x8000_0000
        for id in range(0, self.nb_boards):
            self.boards.append(SnitchTestbenchBoardConfig(f'board_{id}', base_addr=base_addr))
            base_addr += 0x3000_0000
