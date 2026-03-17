
# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Configuration system with dataclass-based configuration and command-line attribute overrides.

This module provides a framework for defining hierarchical configurations using Python
dataclasses. It supports type casting, command-line attribute overrides, and custom
formatting for configuration values.

Key Features:
    - Hierarchical configuration with parent-child relationships
    - Command-line attribute overrides via override_fields()
    - Type-safe configuration with automatic casting
    - Support for enums, nested dataclasses, lists, sets, tuples, and dicts
    - Custom field metadata (description, format, dump options)
    - Hex formatting with grouping for integer values

Organization:
    This is the main module that re-exports all public APIs from submodules:
    - core: Config class and its methods
    - decorators: helper decorators
    - fields: cfg_field() and ConfigLink
    - field_alias: HexInt and ConfigFieldAliasInterface
    - utils: Type casting and formatting utilities
"""


from __future__ import annotations

import contextlib
import fnmatch
import sys
from dataclasses import dataclass, field, fields, Field
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    ClassVar,
    Type,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
    override,
)

from rich.console import Console

from .expression import ConfigFieldRef, NonePolicy
from .decorators import class_or_instance_method, with_type_hint
from .dump import build_config_tree, format_value
from .field_type_alias import (
    ConfigFieldTypeAliasInterface,
    HexInt,
    IrqNumber,
    cast_to_type,
    get_field_alias_formatter,
)
from .fields import cfg_field
from .ref_proxy import ConfigRefProxy
from .utils import hex_grouped
from .utils import pascal_to_snake

# Tracks every Config subclass that has had _class_field_flags populated,
# so Config.reset() can restore them to their metadata-derived defaults.
_all_config_subclasses: set[type] = set()


def _wrap_config_subclass(cls: Type["Config"], *, is_base: bool = False) -> None:
    """Apply dataclass machinery and init/post_init wrapping to a Config (sub)class.

    Called from config_tree.__init_subclass__ for every subclass (is_base=False), and once
    directly to bootstrap Config itself (is_base=True). For is_base=True, @dataclass is
    already applied as a decorator on Config, so only the init wrapping is done.
    """
    if not is_base:
        dataclass(cls, repr=False, eq=False)
        cls._class_field_flags = {
            f.name: {'read': bool(f.metadata.get('read', False)), 'write': bool(f.metadata.get('write', False))}
            for f in fields(cls)
        }
        _all_config_subclasses.add(cls)
        # Record the directory of the file that defines this subclass so that
        # field type aliases (e.g. RegisterList) can resolve relative paths.
        _mod = sys.modules.get(cls.__module__)
        cls._source_dir = (
            __import__('os').path.dirname(__import__('os').path.abspath(_mod.__file__))
            if _mod and hasattr(_mod, '__file__') else None
        )
        # Wrap __post_init__ to pop the parent stack after the body runs.
        # The push happens once in Config.__post_init__; we must pop exactly
        # once even when super().__post_init__() chains through multiple
        # wrapped levels.  We use the stack depth as a guard: only the
        # outermost wrapper (the one that sees the depth *after* the push)
        # performs the pop.
        original_post_init = getattr(cls, '__post_init__', None)
        if original_post_init is None:
            raise RuntimeError(f"Config subclass {cls.__name__} must have a __post_init__ method (inherited or defined)")
        def wrapped_post_init(self, _orig=original_post_init):
            from .config import Config
            depth = len(Config._parent_stack)
            try:
                _orig(self)
            finally:
                # Only pop if the stack grew during our call (i.e. we are the
                # outermost wrapper that owns this push/pop pair).
                if len(Config._parent_stack) > depth:
                    Config._current_parent = Config._parent_stack.pop()

        cls.__post_init__ = wrapped_post_init


@dataclass_transform(
    kw_only_default=False,
    order_default=False,
    frozen_default=False,
    field_specifiers=(field, cfg_field),
)
@dataclass(repr=False, eq=False)
class Config:
    """
    Base class for hierarchical configuration dataclasses.

    Must inherit directly from object. Subclasses are automatically treated as dataclasses
    via ``__init_subclass__`` — no decorator is needed.

    This class provides automatic path tracking, command-line attribute override support,
    and custom repr formatting based on field metadata.

    Attributes:
        parent: Optional parent Config object for hierarchical path construction.
        children: List of child Config instances.
        name: Name of this configuration node (used in path construction).
        path: Computed hierarchical path (e.g., "parent/child/field").

    Class Variables:
        _current_parent: Currently active parent Config (used during initialization).
        _parent_stack: Stack of parent Configs for nested initialization.
        _registry_by_path: Global registry of all Config instances by path.
        _registry_by_class: Global registry of Config instances grouped by class.
        _registry_by_name: Global registry of Config instances grouped by name.
        _attribute_arg_values: Command-line attribute overrides.

    The __post_init__ method automatically:
        1. Constructs the hierarchical path based on parent and name
        2. Checks for command-line overrides for each field
        3. Casts and applies override values with proper type conversion

    Example:
        >>> from config_tree import Config, cfg_field, HexInt
        >>>
        >>> class CPUConfig(Config):
        ...     frequency: int = 1000000
        ...     cores: int = 4
        >>>
        >>> class MemConfig(Config):
        ...     base_addr: HexInt = cfg_field(default=0x80000000, inlined_dump=True)
        ...     size: HexInt = cfg_field(default=0x10000, inlined_dump=True)
        >>>
        >>> mem = MemConfig("memory")
        >>> print(mem)  # Will display: MemConfig(base_addr=0x8000_0000, size=0x0001_0000)
    """

    name: str = field(default="", repr=False)
    label: str | None = field(default=None, repr=False)
    path: str = field(init=False, repr=False)
    parent: Config | None = field(default=None, repr=False, init=False)
    children: list[Config] = field(default_factory=list, repr=False, init=False)
    _current_parent: ClassVar[Config | None] = None
    _parent_stack: ClassVar[list[Config | None]] = []
    _registry_by_path: ClassVar[dict[str, Config]] = {}
    _registry_by_class: ClassVar[dict[Type["Config"], set[Config]]] = {}
    _registry_by_name: ClassVar[dict[str, set[Config]]] = {}
    _registry_by_label: ClassVar[dict[str, Config]] = {}
    _attribute_arg_values: ClassVar[dict[str, str]] = {}
    _defer_parent_init: ClassVar[bool] = False
    _class_inst_counter: ClassVar[int] = 0
    _class_field_flags: ClassVar[dict[str, dict[str, bool]]] = {}
    dump_as_table: ClassVar[bool] = False

    # -------------------------------------------------------------------------
    # Subclass hook — automatically applied to every Config subclass
    # -------------------------------------------------------------------------

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _wrap_config_subclass(cls)

    # -------------------------------------------------------------------------
    # Special methods
    # -------------------------------------------------------------------------

    def __post_init__(self):
        # Auto-assign name if not provided, using class name and instance counter
        if not self.name:
            self.name = pascal_to_snake(f"{type(self).__name__}{type(self)._class_inst_counter}")
            type(self)._class_inst_counter += 1
        # Deep-copy the class-level field flags so each instance has its own mutable dict.
        self._field_flags: dict[str, dict[str, bool]] = {
            k: dict(v) for k, v in type(self)._class_field_flags.items()
        }
        Config._parent_stack.append(Config._current_parent)
        if not self._defer_parent_init:
            self._do_adopt(Config._current_parent)
        else:
            self.path = self.name  # Temporary path, no registrations yet
        Config._current_parent = self

    def __hash__(self) -> int:
        return object.__hash__(self)

    def __getitem__(self, key):
        return self.get_ref(key)

    @override
    def __repr__(self) -> str:
        parts: list[str] = []
        try:
            type_hints = get_type_hints(type(self), include_extras=True)
        except Exception:
            type_hints = {}
        for f in fields(self):
            if f.repr and hasattr(self, f.name):
                if f.metadata.get("inlined_dump") == True:
                    value = getattr(self, f.name)
                    fmt = f.metadata.get("format")
                    if isinstance(value, ConfigFieldTypeAliasInterface):
                        value = str(value)
                    else:
                        formatter = None
                        if f.name in type_hints:
                            formatter = get_field_alias_formatter(type_hints[f.name])
                        if formatter and isinstance(value, int):
                            value = formatter.format(value)
                        elif fmt == "hex" and isinstance(value, int):
                            value = hex_grouped(value)
                    parts.append(f"{f.name}={value}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def __get_path(self) -> str | None:
        return self.path

    # -------------------------------------------------------------------------
    # Lifecycle / initialization
    # -------------------------------------------------------------------------

    def _do_adopt(self, parent: 'Config | None') -> None:
        """Internal: set up parent relationship and register in global registries."""
        self.parent = parent
        if parent is not None:
            parent.children.append(self)
            parent_path = parent.__get_path()
            if parent_path == '/':
                self.path = '/' + self.name
            elif parent_path is not None and parent_path != '':
                self.path = parent_path + '/' + self.name
            else:
                self.path = self.name
        else:
            self.path = '/' if self.name == '/' else self.name
        if self.path != '':
            if self.path in Config._registry_by_path:
                raise ValueError(f"Duplicate configuration path: {self.path}")
            Config._registry_by_path[self.path] = self
        Config._registry_by_class.setdefault(type(self), set()).add(self)
        Config._registry_by_name.setdefault(self.name, set()).add(self)
        if self.label is not None:
            if self.label in Config._registry_by_label:
                raise ValueError(f"Duplicate configuration label: {self.label}")
            Config._registry_by_label[self.label] = self
        # Apply field overrides now that path is finalized
        for f in fields(self):
            path = self.__get_path()
            if path:
                path = path + '/' + f.name
            else:
                path = f.name
            if f.init:
                cmd_value = self._attribute_arg_values.get(path)
                if cmd_value is not None:
                    casted = cast_to_type(cmd_value, f.type, config=self)
                    setattr(self, f.name, casted)
        # Run validation with overridden parameters.
        self.validate('ignore')

    @property
    def base_addresses(self) -> list[int]:
        """Base addresses for this config.

        The default implementation returns an empty list.
        :class:`MemoryMapped` overrides this to return ``[self.base]``.
        """
        return []

    def adopt(self, parent: 'Config') -> None:
        """
        Adopt this config into a parent, completing deferred initialization.

        Only valid for configs created with _defer_parent_init = True.

        Args:
            parent: The parent Config to adopt this config into.

        Raises:
            ValueError: If this config was not created with deferred init,
                       or if it has already been adopted.
        """
        if not self._defer_parent_init:
            raise ValueError(f"Config {self.path} was not created with deferred parent init")
        if self.parent is not None:
            raise ValueError(f"Config {self.path} has already been adopted")
        self._do_adopt(parent)

    # -------------------------------------------------------------------------
    # Class methods - registry & setup
    # -------------------------------------------------------------------------

    @classmethod
    def reset(cls) -> None:
        cls._registry_by_path.clear()
        cls._registry_by_class.clear()
        cls._registry_by_name.clear()
        cls._registry_by_label.clear()
        cls._current_parent = None
        cls._parent_stack.clear()
        cls._attribute_arg_values.clear()
        cls._class_inst_counter = 0
        # Restore all subclass _class_field_flags to their metadata-derived defaults.
        for subclass in _all_config_subclasses:
            subclass._class_field_flags = {
                f.name: {'read': bool(f.metadata.get('read', False)), 'write': bool(f.metadata.get('write', False))}
                for f in fields(subclass)
            }

    @classmethod
    @contextlib.contextmanager
    def set_current_parent(cls, parent: 'Config | None'):
        """Context manager that temporarily sets the current parent for auto-adoption.

        Configs created (via ``__post_init__``) while this context is active are
        automatically adopted under *parent*.

        Args:
            parent: The :class:`Config` instance to use as the adoption parent,
                    or ``None`` to clear the current parent.
        """
        previous = cls._current_parent
        cls._current_parent = parent
        try:
            yield
        finally:
            cls._current_parent = previous

    @classmethod
    def override_fields(cls, attributes: list[str]) -> None:
        for prop in attributes:
            key, value = prop.split('=', 1)
            cls._attribute_arg_values[key] = value

    @classmethod
    def get_config_by_path(cls, path: str) -> Config | None:
        return cls._registry_by_path.get(path)

    @classmethod
    def get_configs_by_path(cls, path_glob: str) -> set["Config"]:
        return set(cfg for path, cfg in cls._registry_by_path.items() if fnmatch.fnmatch(path, path_glob))

    @classmethod
    def get_single_config_by_path(cls, path_glob: str) -> "Config":
        paths = set(cfg for path, cfg in cls._registry_by_path.items() if fnmatch.fnmatch(path, path_glob))
        if len(paths) == 0:
            raise ValueError(f"No config found matching path glob: {path_glob}")
        elif len(paths) > 1:
            raise ValueError(f"Multiple configs found matching path glob: {path_glob} -> {[cfg.path for cfg in paths]}")
        return paths.pop()

    @classmethod
    def get_configs_by_class(cls) -> set["Config"]:
        return set(cls._registry_by_class.get(cls, set()))

    @classmethod
    def get_config_by_label(cls, label: str) -> "Config | None":
        """Retrieve a Config instance by its unique label.

        Args:
            label: The label to look up.

        Returns:
            The Config instance with that label, or None if not found.
        """
        return cls._registry_by_label.get(label)

    # -------------------------------------------------------------------------
    # Tree search
    # -------------------------------------------------------------------------

    def find_from(
        self,
        fn: Callable[["Config"], bool],
        direct_only: bool = False,
    ):
        """Search this config and its descendants for nodes matching *fn*.

        When *fn* matches a node **and** *direct_only* is True the search does
        not recurse into that node's children (the match is a "leaf" hit).
        When *fn* does not match, or *direct_only* is False, the search
        continues into the node's children.

        Args:
            fn: Predicate applied to each Config node.
            direct_only: If True, matching nodes are not recursed into.
        Yields:
            Each Config node for which *fn(node)* is True.
        """
        yield from self._find_from_walk(fn, direct_only)

    def _find_from_walk(
        self,
        fn: Callable[["Config"], bool],
        direct_only: bool,
    ):
        matched = fn(self)
        if matched:
            yield self
        if not matched or not direct_only:
            for child in self.children:
                yield from child._find_from_walk(fn, direct_only)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validators(self) -> list:
        return []

    def _validate_inst_fields(self, none_policy: NonePolicy = 'fail') -> None:
        for f in fields(self):
            if not f.init or isinstance(getattr(self, f.name), Config):
                continue
            value = getattr(self, f.name)
            # Skip None check if field's default is None (meaning None is allowed)
            if value is None:
                if none_policy == 'fail':
                    # None is allowed if the field's default is explicitly None
                    if f.default is None:
                        continue
                    raise ValueError(f"Field '{f.name}' in config '{self.path}' cannot be None")
                elif none_policy in ('ignore', 'propagate'):
                    # With ignore or propagate policy, skip None validation
                    continue
            alias_handler = get_field_alias_formatter(f.type)
            if alias_handler:
                value = alias_handler.validate(value, f, config=self)
                setattr(self, f.name, value)

    def _validate_inst(self, none_policy: NonePolicy = 'fail') -> None:
        self._validate_inst_fields(none_policy)
        for validator in self._validators():
            validator.evaluate(none_policy)

    @class_or_instance_method
    def validate(cls_or_instance, none_policy: NonePolicy = 'fail'):
        if isinstance(cls_or_instance, type) and issubclass(cls_or_instance, Config):
            for instance in cls_or_instance.get_configs_by_class():
                instance.validate(none_policy)
        elif isinstance(cls_or_instance, Config):
            cls_or_instance._validate_inst(none_policy)
        else:
            raise ValueError(f"validate() must be called on Config class or instance")

    # -------------------------------------------------------------------------
    # Instance methods
    # -------------------------------------------------------------------------

    @class_or_instance_method
    def set_field_rw(
        cls_or_instance,
        field_name: str,
        read: bool | None = None,
        write: bool | None = None,
    ) -> None:
        """Set read/write visibility flags for a field.

        Instance call updates only that instance's ``_field_flags``.
        Class call updates class seed flags and all existing instances, so future
        instances inherit the updated defaults.

        Args:
            field_name: Field name to update.
            read: Optional read flag value.
            write: Optional write flag value.

        Raises:
            ValueError: If neither ``read`` nor ``write`` is provided.
        """
        if read is None and write is None:
            raise ValueError("At least one of 'read' or 'write' must be provided")

        def _apply(flags: dict[str, dict[str, bool]]) -> None:
            entry = flags.setdefault(field_name, {})
            if read is not None:
                entry['read'] = read
            if write is not None:
                entry['write'] = write

        if isinstance(cls_or_instance, Config):
            _apply(cls_or_instance._field_flags)
        else:
            _apply(cls_or_instance._class_field_flags)
            for inst in Config._registry_by_class.get(cls_or_instance, set()):
                _apply(inst._field_flags)

    @class_or_instance_method
    def get_ref(cls_or_instance, field_name: str) -> ConfigFieldRef:
        cls_or_instance.set_field_rw(field_name, read=True)
        return ConfigFieldRef(config=cls_or_instance, field_name=field_name)

    @property
    def refs(self) -> ConfigRefProxy:
        """Proxy for accessing config fields as references.

        Instead of writing:
            debug_ref = config.get_ref("debug")
            condition = config.get_ref("enabled") == True

        You can write:
            debug_ref = config.refs.debug
            condition = config.refs.enabled == True

        Returns:
            ConfigRefProxy: Proxy that converts attribute access to ConfigFieldRef.

        Example:
            >>> config = MyConfig("test", value=42)
            >>> cond = config.refs.value > 10  # Returns GreaterThanCondition
            >>> cond.evaluate()  # True
        """
        return ConfigRefProxy(self)

    @classmethod
    def dump_columns(cls) -> list[tuple[str, str]]:
        """Return (header, rich_style) pairs for the config field table.

        Override in a subclass to add, remove, or reorder columns.  The
        returned list must match the tuple produced by :meth:`dump_field_row`.
        """
        return [
            ("Field",       "green"),
            ("Type",        "yellow"),
            ("Value",       "cyan"),
            ("Export",      "magenta"),
            ("Description", "dim"),
        ]

    def dump_field_row(self, f: Field, show_all: bool, type_hints: dict[str, Any]) -> tuple[str, ...] | None:
        """Return one formatted row matching :meth:`dump_columns`, or ``None`` to skip.

        This default implementation decides whether a field is shown and formats
        type/value/access cells. Subclasses can override this method to choose
        exactly which fields are dumped and how each row is rendered.

        Args:
            f: The dataclass :class:`~dataclasses.Field` descriptor.
            show_all: If ``True``, include fields even when not marked readable.
            type_hints: Type hints for this config class, including extras.
        """
        flags = self._field_flags.get(f.name, {})
        if not show_all and not flags.get('read', False):
            return None

        if not hasattr(self, f.name):
            return None

        value = getattr(self, f.name)

        type_str = getattr(f.type, '__name__', str(f.type))
        if f.name in type_hints:
            field_type = type_hints[f.name]
            origin = get_origin(field_type)
            if origin is not None:
                args = get_args(field_type)
                if origin is Annotated:
                    type_str = args[0].__name__ if hasattr(args[0], '__name__') else str(args[0])
                else:
                    type_str = f"{origin.__name__}[{', '.join(arg.__name__ if hasattr(arg, '__name__') else str(arg) for arg in args)}]"

        fmt = f.metadata.get("format")
        value_str = format_value(value, fmt, f.name, type_hints)

        rw_parts = []
        if flags.get('read'):
            rw_parts.append('R')
        if flags.get('write'):
            rw_parts.append('W')
        rw_str = '/'.join(rw_parts) if rw_parts else '-'

        desc = f.metadata.get("description", "")
        return (f.name, type_str, value_str, rw_str, desc)

    def dump(
        self,
        console: Console | None = None,
        show_all: bool = False,
        expand_lists: bool = False,
    ) -> None:
        if console is None:
            console = Console()
        tree = build_config_tree(self, show_all=show_all, expand_lists=expand_lists)
        console.print(tree)

    def generate_memory_map(
        root: Config,
        output_path: str | None = None,
        *,
        prefix: str | None = None,
        recurse: bool = True,
    ) -> str:
        """Generate a C memory-map header from a RouterConfig tree.

        Args:
            root: The root RouterConfig to start traversal from.
            output_path: If provided, write the header to this file path.
            prefix: Initial prefix for define names.
            recurse: If True, recursively generate defines for sub-routers.
                        If False, only generate defines for the root router's mappings.
        Returns:
            The generated header content as a string.
        """
        from .header_gen import generate_memory_map
        return generate_memory_map(root, output_path=output_path, prefix=prefix, recurse=recurse)

    def gen_hal(self, path: str, *fields) -> str:
        """Generate a C HAL register accessor header.

        Args:
            path: Output file path.
            *fields: Any mix of :class:`RegisterList` and :class:`CommandList`
                instances.  They are separated by type internally.

        Returns:
            The generated header content as a string.
        """
        from .register_field_types import RegisterList, CommandList
        from .hal_gen import generate_registers, generate_commands, SPDX, GAP_MACROS
        from code_block import CodeBlock
        import os

        registers = []
        commands = []
        for f in fields:
            if isinstance(f, RegisterList):
                registers.extend(f)
            elif isinstance(f, CommandList):
                for cmdmap in f:
                    commands.append(cmdmap)
            else:
                raise TypeError(f'Expected RegisterList or CommandList, got {type(f).__name__}')

        name = (self.label if self.label else self.name).upper()

        cb = CodeBlock()
        cb.write_raw(SPDX)
        cb.write_raw('')
        cb.write_raw('#pragma once')
        cb.write_raw('')
        cb.write_raw('#ifndef LANGUAGE_ASSEMBLY')
        cb.write_raw('')
        for line in GAP_MACROS.split('\n'):
            cb.write_raw(line)
        cb.write_raw('')
        cb.write_raw('#endif')

        if registers:
            generate_registers(cb, name, registers)
        if commands:
            generate_commands(cb, name, commands)

        cb.write_raw('')
        content = str(cb)

        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(content)

        return content

    def _collect_irqs_for(self, target: Config) -> dict[str, int]:
        """Collect IRQ numbers from InterruptMapping links pointing at this config."""
        irqs = {}
        for child in self._find_from_walk(lambda c: isinstance(c, HasIrq), direct_only=False):
            for f in fields(child):
                if f.type is IrqNumber:
                    if child != target:
                        name = f"{child.name}_{f.name}"
                    else:
                        name = f.name
                    irqs[name] = getattr(child, f.name)
        return irqs

# Bootstrap: apply dataclass machinery to Config itself.
# __init_subclass__ is only called for subclasses, not for the defining class.
_wrap_config_subclass(Config, is_base=True)

class HasSize:
    """Mixin indicating the class has a ``size`` attribute.

    The annotation is only visible to type checkers — at runtime HasSize
    has no attributes, so it won't shadow a dataclass field, a property,
    or any other descriptor named ``size``.
    """
    if TYPE_CHECKING:
        @property
        def size(self) -> int: ...

class HasIrq(with_type_hint(Config)):
    """Mixin indicating the class has one or more interrupt requests (IRQs).
    """
    @property
    def irqs(self) -> list[int]:
        """List of IRQ numbers associated with this config node."""
        irqs = []
        for f in fields(self):
            if isinstance(f.type, IrqNumber):
                irqs.append(getattr(self, f.name))
        return irqs            

@dataclass(repr=False, eq=False)
class MemoryMapped(HasSize, with_type_hint(Config)):
    """Mixin marking a Config as memory-mapped.

    Inherit alongside ``Config`` to participate in memory-map generation.
    The memory map is produced by iterating over all ``MemoryMapped``
    instances in the config tree.

    Attributes:
        base: Base address of the mapped region (``cfg_field``, ``fmt="hex"``).
        size: Size of the mapped region in bytes (``cfg_field``, ``fmt="hex"``).
    """

    #: Base address of the mapped region.
    base: int|None = cfg_field(default=0, read=True, fmt="hex", desc=(
        "Base address of the mapping"
    ))
    #: Size of the mapped region in bytes.
    size: int|None = cfg_field(default=0, read=True, fmt="hex", desc=(
        "Size of the mapping"
    ))

    @property
    def base_addresses(self) -> list[int]:
        """Base addresses of this memory-mapped config.

        Returns a single-element list with this config's ``base`` if it is
        set, otherwise an empty list.
        """
        if self.base:
            return [self.base]
        return []



__all__ = [
    'Config',
    'class_or_instance_method',
    'cfg_field',
    'ConfigFieldTypeAliasInterface',
    'ConfigRefProxy',
    'get_field_alias_formatter',
    'cast_to_type',
    'hex_grouped',
    'HasSize',
    'HasIrq',
    'MemoryMapped',
]
