# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Custom field type aliases with special formatting, conversion, and validation.

This module provides the interface and implementations for custom config field types
that have special display formatting (e.g., hexadecimal integers), custom conversion
logic, and validation rules.
"""

from types import SimpleNamespace
from typing import Any, Annotated, get_args, get_origin, Literal, cast
import json
import enum
from dataclasses import is_dataclass

from .utils import parse_bool


class ConfigDumpable:
    """Interface for items that can render themselves as a row in a Rich table.

    Implement this on dataclasses that appear as list items in a Config field so
    the config dumper can display them as a table rather than a plain string.

    Example::

        class MyItem(ConfigDumpable):
            name: str
            value: int

            @classmethod
            def dump_headers(cls) -> list[str]:
                return ['Name', 'Value']

            def dump_row(self) -> list[str]:
                return [self.name, str(self.value)]
    """

    @classmethod
    def dump_headers(cls) -> list[str]:
        """Return column header labels for the Rich table."""
        raise NotImplementedError(f"{cls.__name__} must implement dump_headers()")

    def dump_row(self) -> list[str]:
        """Return one row of string values, aligned with dump_headers()."""
        raise NotImplementedError(f"{type(self).__name__} must implement dump_row()")

    def dump_children(self) -> list['ConfigDumpable']:
        """Return child items to render as a nested sub-tree when expand_lists=True.

        The default implementation returns an empty list (no expansion).
        Override to expose nested structure, e.g. register fields or command fields.
        """
        return []


class ConfigFieldTypeAliasInterface:
    """Base interface for custom config field type aliases with formatting, casting, and validation.
    
    Subclasses should:
    1. Inherit from both the base type (int, str, etc.) and this interface
    2. Implement format() class method for string representation
    3. Implement cast() class method for type conversion
    4. Implement validate() class method for value validation
    5. Implement check_annotation() to recognize type hints
    6. Override __str__() and __repr__() to use format()
    
    Example:
        >>> class HexInt(int, ConfigFieldTypeAliasInterface):
        ...     @classmethod
        ...     def format(cls, value: int) -> str:
        ...         return f"0x{value:x}"
        ...     @classmethod
        ...     def cast(cls, value: Any, typ: Any) -> int:
        ...         return int(str(value).replace("_", ""), 0)
    """
    
    @classmethod
    def format(cls, value: Any) -> str:
        """Format a value for display.
        
        Args:
            value: The value to format
        
        Returns:
            Formatted string representation
        """
        raise NotImplementedError(f"{cls.__name__} must implement format()")
    
    @classmethod
    def cast(cls, value: Any, field: Any, *, config: Any = None) -> Any:
        """Cast/convert a value to this type.
        
        Args:
            value: The value to convert (typically a string from CLI)
            field: The dataclass Field descriptor (use field.type for the type annotation).
            config: Optional Config instance that owns the field being cast.
        
        Returns:
            Converted value of the appropriate type
        
        Raises:
            ValueError: If conversion fails
        """
        raise NotImplementedError(f"{cls.__name__} must implement cast()")
    
    @classmethod
    def validate(cls, value: Any, field: Any, *, config: Any = None) -> Any:
        """Validate a value for this type.
        
        Args:
            value: The value to validate
            field: The dataclass Field descriptor (use field.type for the type annotation).
            config: Optional Config instance that owns the field being validated.

        Returns:
            Converted value of the appropriate type        

        Raises:
            ValueError: If validation fails with descriptive message
        """
        # Default implementation: no validation
        return value
    
    @classmethod
    def check_annotation(cls, field_type: Any) -> bool:
        """Check if a type annotation matches this alias type.
        
        Args:
            field_type: The type annotation to check
        
        Returns:
            True if field_type matches this alias
        """
        raise NotImplementedError(f"{cls.__name__} must implement check_annotation()")


class HexInt(int, ConfigFieldTypeAliasInterface):
    """Integer that displays in hexadecimal format with underscore grouping.
    
    Can be used both as a runtime value and as a type hint. When converted to
    string, automatically formats with hex grouping.
    
    Example:
        >>> addr: HexInt = HexInt(0x80000000)
        >>> print(addr)  # 0x8000_0000
        >>> str(addr)    # '0x8000_0000'
        >>> 
        >>> # Also works with Annotated type hint:
        >>> base_addr: Annotated[int, "hex"] = 0x80000000
    """
    
    def __str__(self) -> str:
        """Format as hex string with underscore grouping."""
        return self.format(int(self))
    
    def __repr__(self) -> str:
        """Format as hex string with underscore grouping."""
        return self.format(int(self))
    
    @classmethod
    def format(cls, value: int, group: int = 4) -> str:
        """Format an integer as hex string with underscore grouping.
        
        Args:
            value: The integer to format
            group: Number of hex digits per group (default: 4)
        
        Returns:
            Formatted hex string like "0x8000_0000"
        """
        s = f"{value:x}"
        parts = [s[max(i - group, 0):i] for i in range(len(s), 0, -group)]
        return "0x" + "_".join(reversed(parts))
    
    @classmethod
    def cast(cls, value: Any, field: Any, *, config: Any = None) -> int:
        """Cast a value to integer, supporting hex format with underscores.
        
        Args:
            value: The value to convert (string or int)
            field: The dataclass Field descriptor (unused for HexInt).
            config: Optional Config instance (unused for HexInt).
        
        Returns:
            Integer value
        
        Example:
            >>> HexInt.cast("0x8000_0000", SimpleNamespace(type=int))
            2147483648
        """
        if isinstance(value, int):
            return value
        # Support hex like "0x8000_0000" with underscores
        return int(str(value).replace("_", ""), 0)
    
    @classmethod
    def validate(cls, value: Any, field: Any, *, config: Any = None) -> None:
        """Validate that value is an integer.
        
        Args:
            value: The value to validate
            field: The dataclass Field descriptor (unused for HexInt).
            config: Optional Config instance (unused for HexInt).
        
        Raises:
            ValueError: If value is not an integer
        """
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        return value
    
    @classmethod
    def check_annotation(cls, field_type: Any) -> bool:
        """Check if a type annotation is HexInt (supports both direct and Annotated).
        
        Args:
            field_type: The type annotation to check
        
        Returns:
            True if field_type is HexInt or Annotated[int, "hex"]
        """
        if field_type is cls:
            return True
        
        if get_origin(field_type) is Annotated:
            args = get_args(field_type)
            if args and args[0] is int and "hex" in args[1:]:
                return True
        
        return False

class IrqNumber(int):
    pass


class IntRange(int, ConfigFieldTypeAliasInterface):
    """Integer with range validation.
    
    Use subscript syntax to specify min/max range:
        value: IntRange[min_val, max_val]
    
    Also supports Annotated syntax:
        value: Annotated[int, IntRange, min_val, max_val]
    
    Backward compatible with string marker:
        value: Annotated[int, "range", min_val, max_val]
    
    Example:
        >>> # Define a percentage field (0-100)
        >>> percentage: IntRange[0, 100] = 50
        >>> 
        >>> # The validation will ensure the value is within range
    """
    
    def __str__(self) -> str:
        return str(int(self))
    
    def __repr__(self) -> str:
        return str(int(self))
    
    def __class_getitem__(cls, bounds: tuple[int | None, int | None] | int) -> Any:
        """Support IntRange[min, max] syntax.
        
        Args:
            bounds: Either (min, max) tuple or single value for min
        
        Returns:
            Annotated type with IntRange handler and bounds
        
        Examples:
            >>> IntRange[0, 100]  # Range from 0 to 100
            >>> IntRange[10]      # Minimum 10, no maximum
        """
        if isinstance(bounds, tuple):
            if len(bounds) == 2:
                min_val, max_val = bounds
                return Annotated[int, cls, min_val, max_val]
            elif len(bounds) == 1:
                return Annotated[int, cls, bounds[0], None]
            else:
                raise ValueError(f"IntRange requires 1 or 2 bounds, got {len(bounds)}")
        else:
            # Single value: minimum only
            return Annotated[int, cls, bounds, None]
    
    @classmethod
    def format(cls, value: int) -> str:
        """Format as regular integer string."""
        return str(value)
    
    @classmethod
    def cast(cls, value: Any, field: Any, *, config: Any = None) -> int:
        """Cast a value to integer."""
        if isinstance(value, int):
            return value
        return int(str(value).replace("_", ""), 0)
    
    @classmethod
    def validate(cls, value: Any, field: Any, *, config: Any = None) -> None:
        """Validate that value is within the specified range.
        
        Args:
            value: The value to validate
            field: The dataclass Field descriptor (extracts min/max from field.type Annotated metadata).
        
        Raises:
            ValueError: If value is out of range
        """
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        
        # Extract min/max from the type annotation
        min_val, max_val = cls.get_range(field.type)
        
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} is less than minimum {min_val}")
        
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} is greater than maximum {max_val}")
        return value

    @classmethod
    def check_annotation(cls, field_type: Any) -> bool:
        """Check if a type annotation is IntRange.
        
        Args:
            field_type: The type annotation to check
        
        Returns:
            True if field_type is IntRange or IntRange[min, max] or Annotated[int, "range", ...]
        """
        if field_type is cls:
            return True
        
        if get_origin(field_type) is Annotated:
            args = get_args(field_type)
            if args and args[0] is int:
                # Check for IntRange class or "range" string marker
                if cls in args[1:] or "range" in args[1:]:
                    return True
        
        return False
    
    @classmethod
    def get_range(cls, field_type: Any) -> tuple[int | None, int | None]:
        """Extract min/max values from Annotated type.
        
        Args:
            field_type: The Annotated type
        
        Returns:
            Tuple of (min_val, max_val), either can be None
            
        Examples:
            >>> IntRange.get_range(Annotated[int, IntRange, 0, 100])
            (0, 100)
            >>> IntRange.get_range(Annotated[int, "range", 10])
            (10, None)
        """
        if get_origin(field_type) is Annotated:
            args = get_args(field_type)
            # Find where IntRange or "range" marker is
            handler_idx = None
            for i, arg in enumerate(args[1:], start=1):
                if arg is cls or arg == "range":
                    handler_idx = i
                    break
            
            if handler_idx is not None:
                # Min/max come after the handler
                min_val = args[handler_idx + 1] if len(args) > handler_idx + 1 else None
                max_val = args[handler_idx + 2] if len(args) > handler_idx + 2 else None
                return (min_val, max_val)
        
        return (None, None)


def get_field_alias_formatter(field_type: Any) -> type[ConfigFieldTypeAliasInterface] | None:
    """Extract the ConfigFieldAliasInterface handler from a type annotation.

    Args:
        field_type: The type annotation to check

    Returns:
        The ConfigFieldAliasInterface subclass if found, or None

    Examples:
        >>> get_field_alias_formatter(HexInt)  # Direct usage
        <class 'HexInt'>
        >>> get_field_alias_formatter(Annotated[int, IntRange, 0, 100])
        <class 'IntRange'>
    """
    # Direct usage: field_type is itself a ConfigFieldAliasInterface subclass
    if isinstance(field_type, type) and issubclass(field_type, ConfigFieldTypeAliasInterface):
        return field_type

    # Annotated[base_type, handler_class, ...metadata]
    if get_origin(field_type) is Annotated:
        args = get_args(field_type)
        # Look for a ConfigFieldAliasInterface subclass in the metadata
        for arg in args[1:]:  # Skip the base type (args[0])
            if isinstance(arg, type) and issubclass(arg, ConfigFieldTypeAliasInterface):
                return arg

    return None


def cast_to_type(value: Any, typ: Any, *, config: Any = None) -> Any:
    """
    Cast a CLI-provided value (usually string) to a dataclass field type annotation.

    This function handles complex type annotations including:
    - ConfigFieldAliasInterface types (custom casting and validation)
    - Generic types: list[T], set[T], tuple[T, ...], dict[K, V]
    - Enums (by name or value)
    - Nested dataclasses (from JSON)
    - Primitives: bool, int, float, str
    - Hex integers with underscores (e.g., "0x8000_0000")

    Args:
        value: The value to cast (typically a string from CLI).
        typ: The target type annotation (can be generic, union, etc.).

    Returns:
        The value cast to the appropriate type.

    Raises:
        ValueError: If casting fails or value format is invalid.
        json.JSONDecodeError: If JSON parsing fails for dict/dataclass types.

    Example:
        >>> cast_to_type("42", int)
        42
        >>> cast_to_type("true", bool)
        True
        >>> cast_to_type("[1,2,3]", list[int])
        [1, 2, 3]
        >>> cast_to_type("0x1000_0000", int)
        268435456
    """
    if value is None:
        return None

    # Resolve string annotations produced by exec() or PEP 563.
    if isinstance(typ, str):
        _BUILTIN_TYPES = {'str': str, 'int': int, 'float': float, 'bool': bool}
        resolved = _BUILTIN_TYPES.get(typ)
        if resolved is not None:
            typ = resolved
        else:
            try:
                typ = eval(typ)  # noqa: S307 – needed for annotations like 'list[int]'
            except Exception:
                raise TypeError(
                    f"Cannot resolve string type annotation {typ!r} for cast_to_type"
                )

    # Check for ConfigFieldAliasInterface types first
    alias_handler = get_field_alias_formatter(typ)
    if alias_handler:
        fake_field = SimpleNamespace(type=typ)
        result = alias_handler.cast(value, fake_field, config=config)
        alias_handler.validate(result, fake_field, config=config)
        return result

    origin = get_origin(typ)
    args = get_args(typ)

    # Literal type validation
    if origin is Literal:
        if value in args:
            return value
        raise ValueError(f"Value {value!r} not in allowed values: {args}")

    # list[T], set[T], tuple[T, ...]
    if origin in (list, set, tuple):
        (elem_t,) = args if args else (str,)
        if isinstance(value, str):
            s = value.strip()
            # Support JSON arrays: '[1,2,3]'
            if s.startswith("["):
                items = json.loads(s)
            else:
                # Fallback: comma-separated: '1,2,3'
                items = [x.strip() for x in s.split(",") if x.strip() != ""]
        else:
            items = list(value)

        casted = [cast_to_type(x, elem_t) for x in items]
        if origin is list:
            return casted
        if origin is set:
            return set(casted)
        return tuple(casted)

    # dict[K, V] (expect JSON)
    if origin is dict:
        if not isinstance(value, str):
            return value
        return json.loads(value)

    # Enums
    if isinstance(typ, type) and issubclass(typ, enum.Enum):
        if isinstance(value, typ):
            return value
        # allow both "NAME" and raw value
        s = str(value)
        try:
            return typ[s]
        except KeyError:
            # try constructor on the enum value
            return typ(cast_to_type(s, type(next(iter(typ)).value)))

    # Nested dataclass (expect JSON object)
    if isinstance(typ, type) and is_dataclass(typ):
        if isinstance(value, typ):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Expected JSON string for {typ.__name__}, got {type(value)}")
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object for {typ.__name__}, got {data!r}")
        return typ(**data)

    # Primitives / fallbacks
    if typ is bool:
        return parse_bool(value)
    if typ is int:
        # supports hex like "0x8000_0000"
        return int(str(value).replace("_", ""), 0)
    if typ is float:
        return float(value)
    if typ is str:
        return str(value)

    # If it's already the right type, keep it
    if isinstance(value, typ):
        return value

    # Last resort: call the type
    return cast(Any, typ(value))
