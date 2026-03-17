# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Configuration system module."""

from .config import Config
from .devices import HasSize, Timer, Bus, Memory, MemoryMapped, Soc, Itc, HasIrq, MemoryDevice, MemoryMappedDevice
from .expression import ConditionError, ConfigFieldRef, NonePolicy
from .expression import EnvironmentVariableExpression, env
from .expression import ListToTuplesExpression, list_to_tuples
from .expression import Expressions
from .decorators import class_or_instance_method
from .dump import build_config_tree
from .field_type_alias import (
    ConfigFieldTypeAliasInterface,
    ConfigDumpable,
    HexInt,
    IntRange,
    IrqNumber,
    cast_to_type,
    get_field_alias_formatter,
)
from .fields import cfg_field
from .ref_proxy import ConfigRefProxy
from .utils import hex_grouped, parse_bool
from .register_types import Cmd, Cmdfield, Cmdmap, Regfield, Register
from .register_field_types import CommandList, MarkdownFieldList, RegisterList

__all__ = [
    'Config',
    'HasSize',
    'class_or_instance_method',
    'cfg_field',
    'ConfigFieldTypeAliasInterface',
    'ConfigDumpable',
    'ConfigRefProxy',
    'HexInt',
    'IntRange',
    'cast_to_type',
    'get_field_alias_formatter',
    'hex_grouped',
    'parse_bool',
    'ConditionError',
    'ConfigFieldRef',
    'NonePolicy',
    'EnvironmentVariableExpression',
    'env',
    'ListToTuplesExpression',
    'list_to_tuples',
    'Expressions',
    'build_config_tree',
    'Register',
    'Regfield',
    'Cmd',
    'Cmdfield',
    'Cmdmap',
    'MarkdownFieldList',
    'RegisterList',
    'CommandList',
    'Timer',
    'MemoryMapped',
    'Bus',
    'Memory',
    'Soc',
    'Itc',
    'HasIrq',
    'MemoryDevice',
    'MemoryMappedDevice',
]
