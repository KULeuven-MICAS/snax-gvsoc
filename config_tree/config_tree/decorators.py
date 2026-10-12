# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Decorators for the configuration system.

This module provides helper classes for managing Config instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, Type, TypeVar, overload

_R = TypeVar("_R")


class class_or_instance_method(Generic[_R]):
    """Decorator that allows a method to be called on both class and instance.
    
    When called on an instance, passes the instance as the first parameter.
    When called on a class, passes the class as the first parameter.
    """

    def __init__(self, f: Callable[..., _R]) -> None:
        self.f = f

    @overload
    def __get__(self, instance: None, owner: type) -> Callable[..., _R]: ...
    @overload
    def __get__(self, instance: object, owner: type) -> Callable[..., _R]: ...

    def __get__(self, instance: object | None, owner: type) -> Callable[..., _R]:
        if instance is not None:
            class_or_instance = instance
        else:
            class_or_instance = owner

        def fn(*args: Any, **kwargs: Any) -> _R:
            return self.f(class_or_instance, *args, **kwargs)
        return fn

_T = TypeVar('_T')

def with_type_hint(baseclass: Type[_T]) -> Type[_T]:
    """Return *baseclass* for type checkers; ``object`` at runtime.

    Lets mixin classes declare ``self`` as a specific type (here ``Config``)
    without creating an actual inheritance relationship that would interfere
    with the dataclass machinery on ``Config`` subclasses.

    At runtime ``TYPE_CHECKING`` is ``False`` so ``object`` is returned and
    the *baseclass* argument (though evaluated) has no effect.
    """
    if TYPE_CHECKING:
        return baseclass
    return object  # type: ignore[return-value]