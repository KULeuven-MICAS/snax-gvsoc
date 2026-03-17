# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Field utilities for the configuration system.

This module provides cfg_field() for creating configuration fields with metadata,
and ConfigLink for representing links between config instances.
"""

from __future__ import annotations
import inspect
from dataclasses import field, MISSING
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


def cfg_field(
    *,
    default: Any = MISSING,
    default_factory: Any = MISSING,
    desc: str = "",
    fmt: str | None = None,
    init: bool = True,
    read: bool | None = None,
    write: bool | None = None,
    inlined_dump: bool = False,
    dump: bool = False,  # deprecated alias for read
) -> Any:
    """
    Create a configuration field with custom metadata.

    This is a wrapper around dataclasses.field() that adds configuration-specific
    metadata for documentation, formatting, and serialization.

    Args:
        default: Default value for the field (same as dataclass field default).
        default_factory: Factory function for creating default values (for mutable defaults).
        desc: Human-readable description of the field's purpose.
        fmt: Format string for value display (e.g., "hex" for hexadecimal integers).
        init: Whether this field should be included in __init__ (default: True).
        read: Whether this field should be included in full dumps. This will also make the field have a define generated.
        write: Whether this field is run-time-overridable (kconfig / CLI). This also affects build-time expression
            semantics: when evaluating expressions with ``none_policy='propagate'`` (used by the builder for
            condition emission), writable fields return ``None`` (indeterminate) regardless of their Python
            default, because their value at run time is not yet known. With the default
            ``none_policy='fail'``, the concrete Python default is always returned, so build scripts and
            define emission always see the Python default as the visible build-time value.

            Two canonical patterns:

            * ``default=None, write=False`` — field has no meaningful default yet; conditions referencing
              it are indeterminate and defines are not emitted.
            * ``default=N, write=True`` — ``N`` is the hardware ceiling / maximum; build scripts always
              see ``N`` in defines, but any condition on the field is correctly deferred to run time.
        inlined_dump: Whether this field should be included in __repr__ output.

    Returns:
        A dataclass field with the specified metadata.

    Raises:
        ValueError: If both default and default_factory are specified.

    Example:
        >>> class MemConfig(Config):
        ...     base_addr: int = cfg_field(
        ...         default=0x80000000,
        ...         desc="Base address of memory region",
        ...         fmt="hex",
        ...         inlined_dump=True
        ...     )
        ...     size: int = cfg_field(
        ...         default=0x10000,
        ...         desc="Size in bytes",
        ...         fmt="hex"
        ...     )
        ...     items: list[int] = cfg_field(
        ...         default_factory=list,
        ...         desc="List of items",
        ...         read=True
        ...     )
    """
    md: dict[str, object] = {}
    md["description"] = desc
    md["format"] = fmt
    if read is not None or write is not None:
        # Preference for read/write over dump for new code, but support dump for backward compatibility
        md["read"] = read if read is not None else False
        md["write"] = write if write is not None else False
    else:
        md["read"] = dump
        md["write"] = False
    md["inlined_dump"] = inlined_dump

    # Record the file where cfg_field was called
    caller = inspect.stack()[1]
    md["source_file"] = caller.filename
    md["source_line"] = caller.lineno

    # Handle default and default_factory - can't have both
    if default is not MISSING and default_factory is not MISSING:
        raise ValueError("Cannot specify both default and default_factory")
    
    if default_factory is not MISSING:
        return field(default_factory=default_factory, init=init, metadata=md)
    else:
        return field(default=default, init=init, metadata=md)
