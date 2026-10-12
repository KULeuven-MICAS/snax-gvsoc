# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from config_tree.config import Config, HasIrq, MemoryMapped, HasSize
from config_tree.decorators import with_type_hint
from config_tree.field_type_alias import IrqNumber
from config_tree.fields import cfg_field


class Itc():
    pass

class Timer():
    pass

class Bus(MemoryMapped):
    pass

class Memory(MemoryMapped):
    pass

class Soc(Bus):
    pass

class MemoryDevice(Memory, Config):
    pass


class MemoryMappedDevice(MemoryMapped, Config):
    pass

__all__ = [
    'HasSize',
    'HasIrq',
    'Itc', 
    'Timer',
    'Bus',
    'Memory',
    'Soc',
    'MemoryDevice',
    'MemoryMappedDevice',
]