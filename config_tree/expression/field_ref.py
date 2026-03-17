# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Configuration field reference expression."""

from __future__ import annotations
from dataclasses import dataclass, fields
from typing import Type, TYPE_CHECKING

from .base import NonePolicy, ConditionResultList
from .numeric import NumericExpression

if TYPE_CHECKING:
    from ..config import Config


@dataclass(frozen=True, eq=False)
class ConfigFieldRef(NumericExpression):
    """Reference to a field in a configuration instance or class.
    
    Can reference either a specific config instance or a config class.
    When referencing a class, evaluation returns a ConditionResultList containing
    the field values from all instances of that class.
    
    Extends NumericExpression to support arithmetic and bitwise operations
    on field values.
    
    Typically created using Config.get_ref() or instance.get_ref() rather than
    constructing directly.
    
    Example:
        >>> # Instance reference
        >>> cfg = MyConfig(name='test', value=42)
        >>> ref = cfg.get_ref('value')
        >>> ref.evaluate()  # Returns 42
        
        >>> # Class reference (all instances)
        >>> ref = MyConfig.get_ref('value')
        >>> ref.evaluate()  # Returns ConditionResultList of all values
        
        >>> # Bitwise operations
        >>> masked = cfg.get_ref('value') & 0xFF
        >>> shifted = cfg.get_ref('value') << 2
    
    Attributes:
        config: Either a Config class or a Config instance.
        field_name: The name of the field to reference.
    """
    config: Type["Config"] | "Config"  # Can be a Config class or instance
    field_name: str

    def __repr__(self) -> str:
        """Return full path notation for config field reference."""
        from ..config import Config  # Import here to avoid circular import
        
        # Get config name (instance or class name)
        if isinstance(self.config, Config):
            config_name = self.config.name
        elif isinstance(self.config, type) and issubclass(self.config, Config):
            config_name = self.config.__name__.lower()
        else:
            config_name = "unknown"
        
        # Get parent chain for hierarchical path
        path_parts = []
        if isinstance(self.config, Config):
            # Build path from instance hierarchy
            current = self.config
            while current is not None:
                path_parts.insert(0, current.name)
                current = getattr(current, '_parent', None)
        else:
            # For class references, just use class name
            path_parts = [config_name]
        
        # Add field name
        path_parts.append(self.field_name)
        
        return '/'.join(path_parts)

    def _get_field_value(self, cfg: "Config", none_policy: NonePolicy = 'fail'):
        """Get the field value from a config instance, respecting build-time vs run-time semantics.

        The ``write`` flag on a field signals that its value is only resolved at run time (e.g. via
        kconfig or CLI).  This creates two distinct evaluation modes:

        * ``none_policy='fail'`` (default) — used when emitting define values.  The ``write`` check
          is intentionally skipped so that the concrete Python default is always returned.  This
          makes the Python default the visible build-time ceiling (e.g. ``#define FOO_MAX 3``).

        * ``none_policy='propagate'`` — used by the builder when evaluating conditions.  A writable
          field returns ``None`` (indeterminate) regardless of its Python default, causing the
          condition to be deferred and emitted as a run-time conditional block.
        """
        field_header = next((f for f in fields(cfg) if f.name == self.field_name), None)
        if field_header is None:
            raise ValueError(f"Field '{self.field_name}' not found in config '{cfg.name}'")
        # For non-'fail' policies, writable fields are indeterminate at build time.
        # Do NOT apply this for 'fail' (define emission): the Python default is the build-time ceiling.
        if none_policy != 'fail' and field_header.metadata.get("write", False):
            return None
        return getattr(cfg, self.field_name, None)

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Evaluate the field reference to get the field value(s).
        
        Args:
            none_policy: How to handle None field values:
                - 'fail': Include None values in results
                - 'ignore': Filter out None values from results
                - 'propagate': Return None values as-is for three-valued logic
        
        Returns:
            For instance references: The field value from the instance.
            For class references: ConditionResultList containing field values
                from all instances of the class.
        
        Raises:
            ValueError: If config is neither a Config class nor instance.
        """
        from ..config import Config  # Import here to avoid circular import
        if isinstance(self.config, type) and issubclass(self.config, Config):
            results = [self._get_field_value(cfg, none_policy) for cfg in self.config.get_configs_by_class()]
            if none_policy == 'ignore':
                results = filter(None, results)
            return ConditionResultList(results)
        if isinstance(self.config, Config):
            return self._get_field_value(self.config, none_policy)
        raise ValueError(f"Invalid config reference: {self.config}")

    def to_c(self, symbols=None) -> str:
        """Render this field reference as a C symbol name.

        Looks up ``(id(self.config), self.field_name)`` in *symbols* to
        find the C define name that was emitted by the header generator.

        Falls back to a path-based name if the reference is not in the
        symbol table.
        """
        if symbols is not None:
            key = (id(self.config), self.field_name)
            c_name = symbols.get(key)
            if c_name is not None:
                return c_name

        # Fallback: construct from config path + field name
        from ..config import Config
        if isinstance(self.config, Config):
            path = self.config.label if self.config.label is not None else self.config.path.replace('/', '_')
        else:
            path = self.config.__name__
        return f'{path}_{self.field_name}'.upper()
