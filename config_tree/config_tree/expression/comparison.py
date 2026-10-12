# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Comparison expression classes that produce boolean results."""

from __future__ import annotations
from dataclasses import dataclass

from .base import Expression, NonePolicy, ConditionResultList
from .boolean import BooleanExpression


@dataclass(frozen=True, eq=False)
class BinaryCondition(BooleanExpression):
    """Base class for binary comparison operations.
    
    Handles evaluation logic for comparing two expressions, including special
    handling for class-level field references (ConditionResultList) and None values.
    
    Attributes:
        left: The left operand expression.
        right: The right operand expression.
    """
    left: Expression
    right: Expression

    def _op(self, left_val, right_val):
        """Perform the actual comparison operation.
        
        Args:
            left_val: The evaluated left value.
            right_val: The evaluated right value.
        
        Returns:
            bool: The result of the comparison.
        
        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(f"_op() not implemented for {type(self).__name__}")

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        left = self.left.evaluate(none_policy)
        right = self.right.evaluate(none_policy)
        if isinstance(left, ConditionResultList):
            if isinstance(right, ConditionResultList):
               if none_policy == 'ignore':
                    return all(self._op(l, r) if l is not None and r is not None else True for l in left for r in right)
               if none_policy == 'propagate':
                    if any(l is None or r is None for l in left for r in right):
                        return None
               return all(self._op(l, r) for l in left for r in right)
            if none_policy == 'ignore':
                if right is None:
                    return True
                return all(self._op(l, right) if l is not None else True for l in left)
            if none_policy == 'propagate':
                if right is None or any(l is None for l in left):
                    return None
            return all(self._op(l, right) for l in left)
        if isinstance(right, ConditionResultList):
            if none_policy == 'ignore':
                if left is None:
                    return True
                return all(self._op(left, r) if r is not None else True for r in right)
            if none_policy == 'propagate':
                if left is None or any(r is None for r in right):
                    return None
            return all(self._op(left, r) for r in right)
        if none_policy == 'ignore' and (left is None or right is None):
            return True
        if none_policy == 'propagate' and (left is None or right is None):
            return None
        return self._op(left, right)


@dataclass(frozen=True, eq=False)
class EqualityCondition(BinaryCondition):
    """Condition that checks if two values are equal (==)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for equality comparison."""
        return f"{repr(self.left)} == {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val == right_val


@dataclass(frozen=True, eq=False)
class InequalityCondition(BinaryCondition):
    """Condition that checks if two values are not equal (!=)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for inequality comparison."""
        return f"{repr(self.left)} != {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val != right_val


@dataclass(frozen=True, eq=False)
class LessThanCondition(BinaryCondition):
    """Condition that checks if left value is less than right value (<)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for less than comparison."""
        return f"{repr(self.left)} < {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val < right_val


@dataclass(frozen=True, eq=False)
class LessThanOrEqualCondition(BinaryCondition):
    """Condition that checks if left value is less than or equal to right value (<=)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for less than or equal comparison."""
        return f"{repr(self.left)} <= {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val <= right_val


@dataclass(frozen=True, eq=False)
class GreaterThanCondition(BinaryCondition):
    """Condition that checks if left value is greater than right value (>)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for greater than comparison."""
        return f"{repr(self.left)} > {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val > right_val


@dataclass(frozen=True, eq=False)
class GreaterThanOrEqualCondition(BinaryCondition):
    """Condition that checks if left value is greater than or equal to right value (>=)."""

    def __repr__(self) -> str:
        """Return Python-like syntax for greater than or equal comparison."""
        return f"{repr(self.left)} >= {repr(self.right)}"

    def _op(self, left_val, right_val):
        return left_val >= right_val
