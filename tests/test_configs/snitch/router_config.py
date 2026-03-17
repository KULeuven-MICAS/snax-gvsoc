# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2020 ETH Zurich and University of Bologna

"""
Router configuration and mapping classes for the gvrun framework.

This module provides configuration classes for defining router behavior and address mappings
in the simulation environment.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from config_tree import Config, cfg_field, AddressMapping, ConfigLink

class RouterConfig(Config):
    """
    Configuration class for router behavior.

    This class defines the operational parameters for a router component, including
    synchronization mode, buffering, and bandwidth settings.

    Attributes:
    ----------
    synchronous: bool
        True if the router should use synchronous mode where all incoming
        requests are handled as far as possible in synchronous IO mode.
    max_input_pending_size: int
        Size of the FIFO for each input. Only valid for
        asynchronous mode and only when input packet size is smaller or equal
        to the bandwidth.
    bandwidth: int
        Global bandwidth, in bytes per cycle, applied to all incoming
        request. This impacts the end time of the burst.
    """

    synchronous: bool = cfg_field(default=False, read=True, desc=(
        "True if the router should use synchronous mode where all incoming requests are handled as "
        "far as possible in synchronous IO mode."
    ))

    max_input_pending_size: int = cfg_field(default=0, read=True, desc=(
        "Size of the FIFO for each input. Only valid for asynchronous mode and only when input "
        "packet size is smaller or equal to the bandwidth."
    ))

    bandwidth: int = cfg_field(default=0, read=True, desc=(
        "Global bandwidth, in bytes per cycle, applied to all incoming request. This impacts the "
        "end time of the burst."
    ))

    mappings: list["RouterMapping"] = cfg_field(default_factory=list, init=False, desc=(
        "List of address mappings for the router"
    ))

    def __post_init__(self):
        super().__post_init__()
        for mapping in self.mappings:
            mapping.adopt(self)

    def add_mappings(self, *mappings: "RouterMapping"):
        for mapping in mappings:
            mapping.adopt(self)
            self.mappings.append(mapping)

class RouterMapping(AddressMapping, Config):
    """
    Configuration class for router address mapping.

    This class defines how address ranges are mapped through the router, including
    address translation and timing parameters.

    Attributes:
    ----------
    base: int
        Base address of the mapping (in hexadecimal).
    size: int
        Size of the mapping (in hexadecimal).
    remove_base: bool
        Remove the base address when a request is propagated using this mapping.
    latency: int
        Global latency applied to all incoming requests. This impacts
        the start time of the burst.
    config: Config
        Mapping destination.
    """

    _defer_parent_init: ClassVar[bool] = True

    remove_base: bool = cfg_field(default=True, read=True, desc=(
        "Remove the base address when a request is propagated using this mapping"
    ))

    latency: int = cfg_field(default=0, read=True, desc=(
        "Global latency applied to all incoming requests. This impacts the start time of the burst."
    ))

    to: Config = cfg_field(default=None, desc=(
        "Mapping destination"
    ))

    def __post_init__(self):
        if self.name is None and self.to is not None:
            self.name = f"{self.to.name}_mapping"
        super().__post_init__()
        if self.to is not None:
            self.to.links.append(ConfigLink(self.name, self))
