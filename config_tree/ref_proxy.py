# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Reference proxy for automatic config field to reference conversion.

This module provides ConfigRefProxy for accessing config fields as references
through attribute access, enabling cleaner syntax for building conditions.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .expression import ConfigFieldRef


# Fields that should not be converted to references (internal/system fields)
_PROXY_EXCLUDED_FIELDS = frozenset({
    'path', 'parent', 'children', 'links', 'name', 'label',
    'refs',  # Prevent infinite recursion
})


class ConfigRefProxy:
    """Proxy that converts attribute access to ConfigFieldRef objects.
    
    Instead of writing:
        debug_ref = config.get_ref("debug")
        condition = config.get_ref("enabled")
    
    You can write:
        debug_ref = config.refs.debug
        condition = config.refs.enabled
    
    This proxy intercepts attribute access and returns ConfigFieldRef objects
    for config fields, enabling cleaner syntax for building conditions and
    expressions.
    
    Attributes:
        _config: The Config instance being proxied.
    
    Example:
        >>> config = MyConfig("test", debug=True, value=42)
        >>> 
        >>> # Old syntax
        >>> cond = config.get_ref("debug")
        >>> 
        >>> # New syntax with proxy
        >>> cond = config.refs.debug
        >>> 
        >>> # Works with all comparison operators
        >>> cond = config.refs.value > 10
        >>> cond = config.refs.value <= 100
        >>> 
        >>> # Works in builder.if_() contexts
        >>> with builder.if_(builder.config.refs.enabled):
        ...     lib = SourceContainer(name="conditional").add(["src.c"]).compile().link()
        >>> 
        >>> # Combine conditions with logical methods
        >>> cond = config.refs.debug.logical_and(config.refs.value > 0)
    
    Note:
        Python's `and`/`or` operators cannot be overloaded - they always
        short-circuit and evaluate to booleans. Use `.logical_and()` and
        `.logical_or()` methods instead for combining conditions.
    """
    
    __slots__ = ('_config',)
    
    def __init__(self, config: 'Config'):
        """Initialize the proxy with a Config instance.
        
        Args:
            config: The Config instance to proxy attribute access for.
        """
        object.__setattr__(self, '_config', config)
    
    def __getattr__(self, name: str) -> 'ConfigFieldRef':
        """Convert attribute access to a ConfigFieldRef.
        
        Args:
            name: The field name to create a reference for.
        
        Returns:
            ConfigFieldRef for the specified field.
        
        Raises:
            AttributeError: If the field doesn't exist on the config.
        """
        config = object.__getattribute__(self, '_config')
        
        # Check if the attribute exists on the config
        if not hasattr(config, name):
            raise AttributeError(
                f"'{type(config).__name__}' has no field '{name}'"
            )
        
        # Return a field reference
        return config.get_ref(name)
    
    def __setattr__(self, name: str, value) -> None:
        """Prevent setting attributes through the proxy.
        
        Args:
            name: The attribute name.
            value: The value to set.
        
        Raises:
            AttributeError: Always - proxy is read-only.
        """
        raise AttributeError(
            "ConfigRefProxy is read-only. Set values on the config directly."
        )
    
    def __repr__(self) -> str:
        """Return a string representation of the proxy."""
        config = object.__getattribute__(self, '_config')
        return f"ConfigRefProxy({config.path})"
