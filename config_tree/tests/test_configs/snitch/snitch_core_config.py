# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2020 ETH Zurich and University of Bologna

"""Snitch core configuration module.

This module provides the configuration class for the Snitch RISC-V core.
"""

from config_tree import Config, cfg_field


class SnitchCoreConfig(Config):
    """Configuration for Snitch core.

    This class defines the configuration parameters for the Snitch RISC-V core,
    including the ISA string and outstanding transaction settings.

    Attributes
    ----------
    isa: str
        The RISC-V ISA string (e.g., 'rv32imfdca').
    nb_outstanding: int
        Number of outstanding memory transactions allowed.
    """

    isa: str = cfg_field(default='rv32i', read=True, desc=(
        "RISC-V ISA string"
    ))

    nb_outstanding: int = cfg_field(default=4, read=True, desc=(
        "Number of outstanding memory transactions"
    ))
