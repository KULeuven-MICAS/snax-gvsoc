# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Utility functions for the configuration system.

This module provides utilities for type casting, value formatting, and
command-line attribute handling.
"""

from __future__ import annotations
import json
import enum
from dataclasses import is_dataclass
from typing import Any, cast, get_args, get_origin, Literal


def hex_grouped(value: int, group: int = 4) -> str:
    """
    Format an integer as a hex string with underscore grouping.

    Args:
        value: The integer value to format.
        group: Number of hex digits per group (default: 4).

    Returns:
        Hex string like "0x8000_0000" or "0x1234_5678_abcd".

    Example:
        >>> hex_grouped(0x12345678)
        '0x1234_5678'
        >>> hex_grouped(0xabcdef, group=2)
        '0xab_cd_ef'
    """
    s = f"{value:x}"
    parts = [s[max(i - group, 0):i] for i in range(len(s), 0, -group)]
    return "0x" + "_".join(reversed(parts))


def parse_bool(s: Any) -> bool:
    """
    Parse a boolean value from various string representations.

    Accepts common boolean representations (case-insensitive):
    - True: "1", "true", "t", "yes", "y", "on"
    - False: "0", "false", "f", "no", "n", "off"

    Args:
        s: Value to parse (string, bool, or other).

    Returns:
        Boolean value.

    Raises:
        ValueError: If the value cannot be parsed as a boolean.

    Example:
        >>> parse_bool("yes")
        True
        >>> parse_bool("0")
        False
        >>> parse_bool(True)
        True
    """
    if isinstance(s, bool):
        return s
    if s is None:
        raise ValueError("Cannot parse bool from None")
    v = str(s).strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {s!r}")

def pascal_to_snake(s: str) -> str:
    """
    Convert a PascalCase string to snake_case.

    Args:
        s: The PascalCase string to convert.

    Returns:
        The converted snake_case string.

    Example:
        >>> pascal_to_snake("MyConfigClass")
        'my_config_class'
        >>> pascal_to_snake("HTTPServer")
        'http_server'
    """
    result = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0 and (s[i-1].islower() or (i+1 < len(s) and s[i+1].islower())):
            result.append('_')
        result.append(c.lower())
    return ''.join(result)
