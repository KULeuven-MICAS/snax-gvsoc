# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2020 ETH Zurich and University of Bologna

"""Memory configuration module.

This module provides configuration classes for memory components in the system,
including settings for size, atomic operations, and latency.
"""

from config_tree import Config, cfg_field, MemoryMapped


class MemoryConfig(MemoryMapped, Config):
    """Configuration for memory components.

    This class defines the configuration parameters for memory components in the system,
    like size and atomic operation support.

    Attributes
    ----------
    base: int
        The base address of the memory.
    size: int
        The size of the memory in bytes.
    atomics: bool
        True if the memory should support riscv atomics. Since this is slowing down the model, it
        should be set to True only if needed.
    latency: int
        Specify extra latency which will be added to any incoming request.
    """

    atomics: bool = cfg_field(default=False, read=True, desc=(
        "True if the memory should support riscv atomics. "
        "Since this is slowing down the model, it should be "
        "set to True only if needed"
    ))

    latency: int = cfg_field(default=0, read=True, desc=(
        "Specify extra latency which will be added to any "
        "incoming request"
    ))
