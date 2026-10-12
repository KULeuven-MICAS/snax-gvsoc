# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Base classes and utilities for the expression system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

# Type alias for none_policy parameter
NonePolicy = Literal['fail', 'ignore', 'propagate']


class ConditionResultList(list[Any]):
    """Special list type to distinguish class-level evaluation results.
    
    When a condition involves a class-level ConfigFieldRef (e.g., MyConfig.get_ref('field')),
    the evaluation returns a ConditionResultList containing results for all instances
    of that class. This allows BinaryCondition to distinguish between instance-level
    and class-level evaluation contexts.
    """
    pass


class ConditionError(Exception):
    """Custom exception for errors in condition evaluation."""
    pass


class ExpressionRegistry:
    """Global registry for named expressions.
    
    Maps (file, name) tuples to Expression instances. Used for symbolic
    reference generation in build files.
    """
    
    _registry: dict[tuple[str, str], 'Expression'] = {}
    
    @classmethod
    def register(cls, expression: 'Expression') -> None:
        """Register a named expression.
        
        Args:
            expression: Expression with name and file set.
        
        Raises:
            ValueError: If expression lacks name or file, or if key already exists.
        """
        if not expression.name or not expression.file:
            raise ValueError("Expression must have both name and file set")
        
        key = (expression.file, expression.name)
        if key in cls._registry:
            if cls._registry[key] is not expression:
                raise ValueError(
                    f"Expression name conflict: {expression.name} in {expression.file} "
                    "is already registered to a different expression"
                )
        else:
            cls._registry[key] = expression
    
    @classmethod
    def get(cls, file: str, name: str) -> 'Expression | None':
        """Get a registered expression by file and name.
        
        Args:
            file: File path where the expression was defined.
            name: Variable name.
        
        Returns:
            The expression if found, None otherwise.
        """
        return cls._registry.get((file, name))
    
    @classmethod
    def get_all(cls) -> dict[tuple[str, str], 'Expression']:
        """Get all registered expressions.
        
        Returns:
            Dictionary mapping (file, name) to Expression.
        """
        return cls._registry.copy()
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered expressions."""
        cls._registry.clear()
    
    @classmethod
    def get_by_file(cls, file: str) -> dict[str, 'Expression']:
        """Get all expressions defined in a specific file.
        
        Args:
            file: File path to filter by.
        
        Returns:
            Dictionary mapping name to Expression for the given file.
        """
        return {name: expr for (f, name), expr in cls._registry.items() if f == file}


class Expression(ABC):
    """Abstract base class for all expression types.
    
    Expressions can be evaluated to produce a value. The type of value depends
    on the expression subclass (boolean, numeric, etc.).
    
    Attributes:
        name: Optional variable name this expression was assigned to.
        file: Optional file path where this expression was defined.
    """
    
    name: str | None = None
    file: str | None = None

    def structurally_equal(self, other: object) -> bool:
        """Compare two expressions for structural equality.

        ``__eq__`` is overloaded to create :class:`EqualityCondition` expressions,
        so this method provides a separate structural comparison of the expression
        tree that is used internally for container condition-coalescing decisions.

        Two expressions are structurally equal when they have the same type and
        all their dataclass fields are recursively structurally equal.  Non-expression
        fields are compared with ``==``.  ``None`` is only equal to ``None``.

        Args:
            other: The object to compare against.

        Returns:
            ``True`` if both expressions represent the same expression tree.
        """
        if other is None:
            return False
        if type(self) is not type(other):
            return False
        from dataclasses import fields as _dc_fields, is_dataclass
        if not is_dataclass(self):
            return self is other
        for f in _dc_fields(self):  # type: ignore[arg-type]
            v1 = getattr(self, f.name)
            v2 = getattr(other, f.name)
            if isinstance(v1, Expression):
                if not v1.structurally_equal(v2):
                    return False
            elif isinstance(v1, list) and isinstance(v2, list):
                if len(v1) != len(v2):
                    return False
                for a, b in zip(v1, v2):
                    if isinstance(a, Expression):
                        if not a.structurally_equal(b):
                            return False
                    else:
                        # Non-expression scalars: use identity-safe plain equality
                        if a is not b and a != b:  # noqa: SIM300
                            return False
            else:
                # Non-expression scalars (str, int, Config instance/class, etc.)
                if v1 is not v2 and v1 != v2:  # noqa: SIM300
                    return False
        return True

    def set_name(self, name: str, file: str) -> None:
        """Set the variable name and file for this expression.
        
        Args:
            name: Variable name this expression was assigned to.
            file: File path where the variable was defined.
        """
        # Use object.__setattr__ to bypass frozen dataclass restrictions
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'file', file)
        # Register with the global registry
        ExpressionRegistry.register(self)
    
    def get_reference(self) -> str | None:
        """Get the symbolic reference for this expression.
        
        Returns:
            A string like "file.name" if named, None otherwise.
        """
        if self.name and self.file:
            return f"{self.file}.{self.name}"
        return None
    
    def __str__(self) -> str:
        """Return string representation, using symbolic reference if available."""
        ref = self.get_reference()
        if ref:
            return f"<Expression: {self.name}>"
        return repr(self)

    def as_operand(self) -> 'Expression':
        """Return the expression to use as an operand in composite expressions.
        
        Override in subclasses that need to substitute a different expression
        (e.g., references instead of wrapper expressions like AssignmentExpression).
        
        Returns:
            self by default, or a substituted expression in subclasses.
        """
        return self

    def __add__(self, other):
        if isinstance(other, str):
            return self.suffix(other)
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return self.prefix(other)
        return NotImplemented

    def to_c(self, symbols: dict[tuple[int, str], str] | None = None) -> str:
        """Render this expression as a C code string.

        Args:
            symbols: Optional mapping from ``(id(config), field_name)`` to the
                emitted C define name.  Used by :class:`ConfigFieldRef` to
                resolve references to their header-generator symbol names.

        Raises:
            NotImplementedError: If the concrete subclass does not support C
                rendering.
        """
        raise NotImplementedError(
            f'{type(self).__name__} does not support to_c()')

    @abstractmethod
    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        """Evaluate this expression to produce a value.
        
        Args:
            none_policy: How to handle None values in field references.
        
        Returns:
            The evaluated value (type depends on expression subclass).
        """
        pass
    
    def __eq__(self, value):
        """Create equality comparison expression.
        
        Args:
            value: Value to compare with (Expression or constant).
            
        Returns:
            EqualityCondition expression.
        """
        from .comparison import EqualityCondition
        from .numeric import ConstantValue
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return EqualityCondition(self.as_operand(), value.as_operand())

    def __ne__(self, value):
        """Create inequality comparison expression.
        
        Args:
            value: Value to compare with (Expression or constant).
            
        Returns:
            InequalityCondition expression.
        """
        from .comparison import InequalityCondition
        from .numeric import ConstantValue
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return InequalityCondition(self.as_operand(), value.as_operand())
    
    # Reflected (reverse) operations for when constant is on the left side
    def __req__(self, value):
        """Create equality comparison (reflected)."""
        from .comparison import EqualityCondition
        from .numeric import ConstantValue
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return EqualityCondition(value.as_operand(), self.as_operand())

    def __rne__(self, value):
        """Create inequality comparison (reflected)."""
        from .comparison import InequalityCondition
        from .numeric import ConstantValue
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return InequalityCondition(value.as_operand(), self.as_operand())

    def logical_and(self, other: 'Expression') -> 'Expression':
        """Combine this expression with another using logical AND.
        
        Args:
            other: The expression to AND with this one.
        
        Returns:
            LogicalAnd: A new expression that is true when both are true.
        """
        from .boolean import LogicalAnd
        
        left = self.as_operand()
        right = other.as_operand()
        
        # Flatten if left side is already LogicalAnd
        if isinstance(left, LogicalAnd):
            return LogicalAnd(conditions=left.conditions + [right])
        return LogicalAnd(conditions=[left, right])

    def logical_or(self, other: 'Expression') -> 'Expression':
        """Combine this expression with another using logical OR.
        
        Args:
            other: The expression to OR with this one.
        
        Returns:
            LogicalOr: A new expression that is true when either is true.
        """
        from .boolean import LogicalOr
        
        left = self.as_operand()
        right = other.as_operand()
        
        # Flatten if left side is already LogicalOr
        if isinstance(left, LogicalOr):
            return LogicalOr(conditions=left.conditions + [right])
        return LogicalOr(conditions=[left, right])

    def logical_not(self) -> 'Expression':
        """Negate this expression with logical NOT.
        
        Returns:
            LogicalNot: A new expression that is true when this is false.
        """
        from .boolean import LogicalNot
        return LogicalNot(condition=self.as_operand())

    def map(self, fn: 'Expression') -> 'Expression':
        """Apply a lambda expression to each element of a list-valued expression."""
        from .functional import MapExpression, LambdaFunctionExpression

        if not isinstance(fn, LambdaFunctionExpression):
            raise TypeError(f"map() expects a lambda built with Expressions.fn(...), got {type(fn).__name__}")
        return MapExpression(source=self.as_operand(), fn=fn)

    def upper(self) -> 'Expression':
        """Convert expression value to upper-case string."""
        from .functional import UpperExpression
        return UpperExpression(source=self.as_operand())

    def lower(self) -> 'Expression':
        """Convert expression value to lower-case string."""
        from .functional import LowerExpression
        return LowerExpression(source=self.as_operand())

    def prefix(self, value: str) -> 'Expression':
        """Prefix expression value (as string) with *value*."""
        from .functional import StringConcatExpression
        from .numeric import ConstantValue
        return StringConcatExpression(left=ConstantValue(value), right=self.as_operand())

    def suffix(self, value: str) -> 'Expression':
        """Suffix expression value (as string) with *value*."""
        from .functional import StringConcatExpression
        from .numeric import ConstantValue
        return StringConcatExpression(left=self.as_operand(), right=ConstantValue(value))

    def to_tuple(self, value: Any) -> 'Expression':
        """Create a ``(key, value)`` tuple expression from this key expression."""
        from .functional import TupleExpression
        from .numeric import ConstantValue

        tuple_value = value if isinstance(value, Expression) else ConstantValue(value)
        return TupleExpression(key=self.as_operand(), value=tuple_value)

    def as_define(self, *, value: Any = 1) -> 'Expression':
        """Create a define tuple expression ``(key, value)``.

        Preferred alias for :meth:`to_tuple` in build-system contexts.
        """
        return self.to_tuple(value)
