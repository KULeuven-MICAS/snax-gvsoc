# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Boolean expression classes for logical operations."""

from __future__ import annotations
from dataclasses import dataclass

from .base import Expression, NonePolicy, ConditionResultList, ConditionError

class BooleanExpression(Expression):
    """Base class for expressions that evaluate to boolean values.
    
    Supports explicit logical operations via methods (not operators):
    - logical_and(): Combine with AND
    - logical_or(): Combine with OR  
    - logical_not(): Negate
    
    Does NOT implement __and__, __or__, __invert__ - these are reserved
    for bitwise operations on numeric expressions.
    
    Example:
        >>> # Build conditions using explicit logical methods
        >>> condition = (field_ref > 10).logical_and(field_ref < 100)
        >>> condition = (field_ref == 'active').logical_or(field_ref == 'pending')
        >>> condition = (field_ref > 10).logical_not()
    """
    
    def evaluate(self, none_policy: NonePolicy = 'fail') -> bool | None:
        """Evaluate this expression to a boolean result.
        
        Args:
            none_policy: How to handle None values in field references:
                - 'fail': Any None field value causes the condition to fail (default)
                - 'ignore': None field values are skipped (always pass for that field)
                - 'propagate': None values propagate through with three-valued logic:
                    - OR(None, True) = True, OR(None, False) = None
                    - AND(None, False) = False, AND(None, True) = None
                    - NOT(None) = None
        
        Returns:
            bool | None: True if the condition is satisfied, False otherwise.
            Returns None when using 'propagate' policy and result is indeterminate.
            For class-level conditions, returns True only if all instances satisfy it.
        
        Raises:
            NotImplementedError: If evaluate() is not implemented by the subclass.
        """
        raise NotImplementedError(f"evaluate() not implemented for {type(self).__name__}")

    def logical_and(self, other: BooleanExpression) -> LogicalAnd:
        """Combine this expression with another using logical AND.
        
        Args:
            other: The expression to AND with this one.
        
        Returns:
            LogicalAnd: A new expression that is true when both are true.
        """
        left = self.as_operand()
        right = other.as_operand()
        
        # Flatten if left side is already LogicalAnd
        if isinstance(left, LogicalAnd):
            return LogicalAnd(conditions=left.conditions + [right])
        return LogicalAnd(conditions=[left, right])

    def logical_or(self, other: BooleanExpression) -> LogicalOr:
        """Combine this expression with another using logical OR.
        
        Args:
            other: The expression to OR with this one.
        
        Returns:
            LogicalOr: A new expression that is true when either is true.
        """
        left = self.as_operand()
        right = other.as_operand()
        
        # Flatten if left side is already LogicalOr
        if isinstance(left, LogicalOr):
            return LogicalOr(conditions=left.conditions + [right])
        return LogicalOr(conditions=[left, right])

    def logical_not(self) -> LogicalNot:
        """Negate this expression.
        
        Returns:
            LogicalNot: A new expression that is true when this is false.
        """
        return LogicalNot(condition=self.as_operand())

    def message(self, msg: str = None) -> ConditionEvaluator:
        """Attach a custom error message to this expression.
        
        When the returned ConditionEvaluator is evaluated, it will raise a
        ConditionError with the specified message if the expression fails.
        
        Args:
            msg: Optional custom error message. If None, a default message
                 showing the failed condition will be generated.
        
        Returns:
            ConditionEvaluator: A new expression that raises an exception on failure.
        
        Example:
            >>> condition = (field_ref > 10).message("Value must be greater than 10")
            >>> condition.evaluate()  # Raises ConditionError if field_ref <= 10
            
            >>> # With default message
            >>> condition = (field_ref == 'active').message()
            >>> condition.evaluate()  # Raises ConditionError with default message
        """
        return ConditionEvaluator(self, msg)




@dataclass(frozen=True, eq=False)
class ConditionEvaluator(BooleanExpression):
    """Condition wrapper that raises an exception with a custom message on failure.
    
    This class wraps an existing condition and evaluates it. If the condition
    is satisfied, it returns True. If the condition fails, it raises a
    ConditionError with either a custom message or a default message showing
    the failed condition.
    
    Typically created using the `message()` method on a condition rather than
    constructing directly.
    
    Attributes:
        condition: The underlying condition to evaluate.
        message: Custom error message to use on failure. If None, a default
                 message is generated.
    
    Example:
        >>> # Create a condition with validation message
        >>> config = MyConfig(name='test', value=5)
        >>> condition = (config.get_ref('value') > 10).message("Invalid value: must be > 10")
        >>> 
        >>> try:
        ...     condition.evaluate()
        ... except ConditionError as e:
        ...     print(e)  # Prints: Invalid value: must be > 10
        
        >>> # Multiple conditions with messages
        >>> range_check = ((config.get_ref('value') >= 0).message("Value must be non-negative")
        ...                .logical_and((config.get_ref('value') <= 100).message("Value must not exceed 100")))
    """
    condition: BooleanExpression
    message: str

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Evaluate the condition and raise ConditionError on failure.
        
        Args:
            none_policy: How to handle None values, passed to the underlying condition.
        
        Returns:
            bool | None: True if the condition is satisfied, None if indeterminate.
        
        Raises:
            ConditionError: If the condition evaluates to False, with either the
                           custom message or a default message showing the condition.
        """
        result = self.condition.evaluate(none_policy)
        if result is True:
            return True
        elif result is None:
            return None
        else:
            raise ConditionError(self.message or f"Condition failed: {self.condition}")


@dataclass(frozen=True, eq=False)
class LogicalAnd(BooleanExpression):
    """Expression that combines multiple boolean expressions with logical AND.
    
    All expressions must be true for the LogicalAnd to be true.
    Created using the logical_and() method.
    
    Example:
        >>> condition = (field > 10).logical_and(field < 100).logical_and(enabled > 0)
    
    Attributes:
        conditions: List of boolean expressions to AND together.
    """
    conditions: list[BooleanExpression]

    def __repr__(self) -> str:
        """Return Python-like syntax for AND expression."""
        parts = []
        for cond in self.conditions:
            # Add parentheses around OR expressions for precedence
            if isinstance(cond, LogicalOr):
                parts.append(f"({repr(cond)})")
            else:
                parts.append(repr(cond))
        return ' and '.join(parts)

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Evaluate all conditions with AND logic.
        
        Args:
            none_policy: Passed to each condition's evaluate method.
        
        Returns:
            bool | None: True only if all conditions are true, False if any is false.
            With 'propagate' policy: returns None if no condition is false but
            at least one is None (indeterminate).
        """
        has_none = False
        for cond in self.conditions:
            result = cond.evaluate(none_policy)
            if isinstance(result, ConditionResultList):
                if not all(result):
                    return False
                if none_policy == 'propagate' and any(r is None for r in result):
                    has_none = True
                continue
            if result is None:
                if none_policy == 'propagate':
                    has_none = True
                continue
            if not result:
                return False
        if has_none:
            return None
        return True


@dataclass(frozen=True, eq=False)
class LogicalOr(BooleanExpression):
    """Expression that combines multiple boolean expressions with logical OR.
    
    At least one expression must be true for the LogicalOr to be true.
    Created using the logical_or() method.
    
    Example:
        >>> condition = (status == 'active').logical_or(status == 'pending').logical_or(status == 'retry')
    
    Attributes:
        conditions: List of boolean expressions to OR together.
    """
    conditions: list[BooleanExpression]

    def __repr__(self) -> str:
        """Return Python-like syntax for OR expression."""
        return ' or '.join(repr(cond) for cond in self.conditions)

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Evaluate all conditions with OR logic.
        
        Args:
            none_policy: Passed to each condition's evaluate method.
        
        Returns:
            bool | None: True if any condition is true, False if all are false.
            With 'propagate' policy: returns None if no condition is true but
            at least one is None (indeterminate).
        """
        has_none = False
        for cond in self.conditions:
            result = cond.evaluate(none_policy)
            if isinstance(result, ConditionResultList):
                if all(result):
                    return True
                if none_policy == 'propagate' and any(r is None for r in result):
                    has_none = True
                continue
            if result is None:
                if none_policy == 'propagate':
                    has_none = True
                continue
            if result:
                return True
        if has_none:
            return None
        return False


@dataclass(frozen=True, eq=False)
class LogicalNot(BooleanExpression):
    """Expression that negates another boolean expression.
    
    Created using the logical_not() method.
    
    Example:
        >>> condition = (field.get_ref('count') > 0).logical_not()
    
    Attributes:
        condition: The boolean expression to negate.
    """
    condition: BooleanExpression

    def __repr__(self) -> str:
        """Return Python-like syntax for NOT expression."""
        # Add parentheses around OR/AND expressions
        if isinstance(self.condition, (LogicalOr, LogicalAnd)):
            return f"not ({repr(self.condition)})"
        return f"not {repr(self.condition)}"

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Evaluate the negation of the wrapped condition.
        
        Args:
            none_policy: Passed to the wrapped condition's evaluate method.
        
        Returns:
            bool | None: Negation of the wrapped condition's result.
            With 'propagate' policy: returns None if the wrapped result is None.
        """
        result = self.condition.evaluate(none_policy)
        if result is None and none_policy == 'propagate':
            return None
        if isinstance(result, ConditionResultList):
            if none_policy == 'propagate' and any(r is None for r in result):
                return None
            return not all(result)
        return not result
