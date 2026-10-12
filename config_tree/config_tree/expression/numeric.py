# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Numeric and value expression classes for arithmetic and bitwise operations."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

from .base import Expression, NonePolicy

if TYPE_CHECKING:
    from .comparison import (
        LessThanCondition,
        LessThanOrEqualCondition,
        GreaterThanCondition,
        GreaterThanOrEqualCondition,
    )


class ValueExpression(Expression):
    """Base class for expressions that evaluate to non-boolean values.
    
    Supports comparison operators that produce BooleanExpressions:
    - ==, != for equality (inherited from Expression base class)
    - <, <=, >, >= for ordering
    
    Subclasses (like NumericExpression) may add arithmetic and bitwise operators.
    """
    
    def __lt__(self, value) -> LessThanCondition:
        from .comparison import LessThanCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return LessThanCondition(self.as_operand(), value.as_operand())

    def __le__(self, value) -> LessThanOrEqualCondition:
        from .comparison import LessThanOrEqualCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return LessThanOrEqualCondition(self.as_operand(), value.as_operand())

    def __gt__(self, value) -> GreaterThanCondition:
        from .comparison import GreaterThanCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return GreaterThanCondition(self.as_operand(), value.as_operand())

    def __ge__(self, value) -> GreaterThanOrEqualCondition:
        from .comparison import GreaterThanOrEqualCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return GreaterThanOrEqualCondition(self.as_operand(), value.as_operand())

    # Reflected (reverse) operations for when constant is on the left side
    # (__req__ and __rne__ are inherited from Expression base class)
    
    def __rlt__(self, value) -> GreaterThanCondition:
        from .comparison import GreaterThanCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return GreaterThanCondition(self.as_operand(), value.as_operand())

    def __rle__(self, value) -> GreaterThanOrEqualCondition:
        from .comparison import GreaterThanOrEqualCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return GreaterThanOrEqualCondition(self.as_operand(), value.as_operand())

    def __rgt__(self, value) -> LessThanCondition:
        from .comparison import LessThanCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return LessThanCondition(self.as_operand(), value.as_operand())

    def __rge__(self, value) -> LessThanOrEqualCondition:
        from .comparison import LessThanOrEqualCondition
        
        if not isinstance(value, Expression):
            value = ConstantValue(value)
        
        return LessThanOrEqualCondition(self.as_operand(), value.as_operand())


class NumericExpression(ValueExpression):
    """Expression that evaluates to a numeric value.
    
    Supports arithmetic operators (+, -, *, /, //, %, **) and
    bitwise operators (&, |, ^, ~, <<, >>).
    
    Example:
        >>> # Arithmetic
        >>> expr = field_ref + 10
        >>> expr = field_ref * 2
        
        >>> # Bitwise
        >>> expr = field_ref & 0xFF
        >>> expr = field_ref | 0x100
    """
    
    # Arithmetic operators
    def __add__(self, other) -> ArithmeticExpression:
        if isinstance(other, str):
            return super().__add__(other)
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a + b, "+")

    def __radd__(self, other) -> ArithmeticExpression:
        if isinstance(other, str):
            return super().__radd__(other)
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a + b, "+")

    def __sub__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a - b, "-")

    def __rsub__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a - b, "-")

    def __mul__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a * b, "*")

    def __rmul__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a * b, "*")

    def __truediv__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a / b, "/")

    def __rtruediv__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a / b, "/")

    def __floordiv__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a // b, "//")

    def __rfloordiv__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a // b, "//")

    def __mod__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a % b, "%")

    def __rmod__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a % b, "%")

    def __pow__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(self.as_operand(), other.as_operand(), lambda a, b: a ** b, "**")

    def __rpow__(self, other) -> ArithmeticExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return ArithmeticExpression(other.as_operand(), self.as_operand(), lambda a, b: a ** b, "**")

    def __neg__(self) -> UnaryArithmeticExpression:
        return UnaryArithmeticExpression(self.as_operand(), lambda a: -a, "-")

    def __pos__(self) -> UnaryArithmeticExpression:
        return UnaryArithmeticExpression(self.as_operand(), lambda a: +a, "+")

    def __abs__(self) -> UnaryArithmeticExpression:
        return UnaryArithmeticExpression(self.as_operand(), lambda a: abs(a), "abs")

    # Bitwise operators
    def __and__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(self.as_operand(), other.as_operand(), lambda a, b: a & b, "&")

    def __rand__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(other.as_operand(), self.as_operand(), lambda a, b: a & b, "&")

    def __or__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(self.as_operand(), other.as_operand(), lambda a, b: a | b, "|")

    def __ror__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(other.as_operand(), self.as_operand(), lambda a, b: a | b, "|")

    def __xor__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(self.as_operand(), other.as_operand(), lambda a, b: a ^ b, "^")

    def __rxor__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(other.as_operand(), self.as_operand(), lambda a, b: a ^ b, "^")

    def __invert__(self) -> UnaryBitwiseExpression:
        return UnaryBitwiseExpression(self.as_operand(), lambda a: ~a, "~")

    def __lshift__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(self.as_operand(), other.as_operand(), lambda a, b: a << b, "<<")

    def __rlshift__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(other.as_operand(), self.as_operand(), lambda a, b: a << b, "<<")

    def __rshift__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(self.as_operand(), other.as_operand(), lambda a, b: a >> b, ">>")

    def __rrshift__(self, other) -> BitwiseExpression:
        if not isinstance(other, Expression):
            other = ConstantValue(other)
        
        return BitwiseExpression(other.as_operand(), self.as_operand(), lambda a, b: a >> b, ">>")


@dataclass(frozen=True, eq=False)
class ConstantValue(NumericExpression):
    """Wraps a constant value for use in expressions.
    
    Automatically created when using operators with constants. Users typically
    don't need to create these directly. Extends NumericExpression to support
    all arithmetic and bitwise operations.
    
    Example:
        >>> # These automatically wrap constants in ConstantValue:
        >>> field_ref == 42
        >>> field_ref > "test"
        >>> True == field_ref  # Reflected operator
    """
    value: Any

    def __repr__(self) -> str:
        """Return string representation of the constant value."""
        if isinstance(self.value, str):
            return repr(self.value)  # Use repr for strings to get quotes
        elif isinstance(self.value, int) and self.value > 255:
            # Format large integers as hex for readability
            return hex(self.value)
        else:
            return str(self.value)

    def evaluate(self, none_policy: NonePolicy = 'fail'):
        """Return the wrapped constant value.
        
        Args:
            none_policy: Ignored for constants (always returns the value).
        
        Returns:
            The wrapped constant value.
        """
        return self.value

    def to_c(self, symbols=None) -> str:
        if isinstance(self.value, int):
            if self.value >= 256:
                return hex(self.value)
            return str(self.value)
        return str(self.value)


@dataclass(frozen=True, eq=False)
class ArithmeticExpression(NumericExpression):
    """Binary arithmetic expression (+, -, *, /, //, %, **).
    
    Created when using arithmetic operators on NumericExpression instances.
    
    Attributes:
        left: The left operand expression.
        right: The right operand expression.
        op: The operation function.
        op_symbol: String representation of the operator.
    """
    left: Expression
    right: Expression
    op: Callable[[Any, Any], Any]
    op_symbol: str

    def __repr__(self) -> str:
        """Return Python-like syntax for arithmetic expression."""
        # Add parentheses for nested expressions to maintain precedence
        left_str = repr(self.left)
        right_str = repr(self.right)
        
        # Add parentheses around expressions with lower precedence
        if isinstance(self.left, ArithmeticExpression) and self.op_symbol in ('*', '/', '//', '%', '**'):
            if self.left.op_symbol in ('+', '-'):
                left_str = f"({left_str})"
        
        if isinstance(self.right, ArithmeticExpression):
            # Right associativity and precedence handling
            if self.op_symbol in ('*', '/', '//', '%', '**'):
                if self.right.op_symbol in ('+', '-'):
                    right_str = f"({right_str})"
            elif self.op_symbol in ('+', '-') and self.right.op_symbol in ('+', '-'):
                # Subtraction requires parentheses for right subexpressions
                if self.op_symbol == '-':
                    right_str = f"({right_str})"
        
        return f"{left_str} {self.op_symbol} {right_str}"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        left_val = self.left.evaluate(none_policy)
        right_val = self.right.evaluate(none_policy)
        if left_val is None or right_val is None:
            return None
        return self.op(left_val, right_val)

    def to_c(self, symbols=None) -> str:
        left_str = self.left.to_c(symbols)
        right_str = self.right.to_c(symbols)
        if isinstance(self.left, ArithmeticExpression) and self.op_symbol in ('*', '/', '//', '%', '**'):
            if self.left.op_symbol in ('+', '-'):
                left_str = f'({left_str})'
        if isinstance(self.right, ArithmeticExpression):
            if self.op_symbol in ('*', '/', '//', '%', '**'):
                if self.right.op_symbol in ('+', '-'):
                    right_str = f'({right_str})'
            elif self.op_symbol == '-' and self.right.op_symbol in ('+', '-'):
                right_str = f'({right_str})'
        return f'{left_str} {self.op_symbol} {right_str}'


@dataclass(frozen=True, eq=False)
class UnaryArithmeticExpression(NumericExpression):
    """Unary arithmetic expression (-, +, abs).
    
    Created when using unary arithmetic operators on NumericExpression instances.
    
    Attributes:
        operand: The operand expression.
        op: The operation function.
        op_symbol: String representation of the operator.
    """
    operand: Expression
    op: Callable[[Any], Any]
    op_symbol: str

    def __repr__(self) -> str:
        """Return Python-like syntax for unary arithmetic expression."""
        operand_str = repr(self.operand)
        # Add parentheses for complex expressions
        if isinstance(self.operand, (ArithmeticExpression, BitwiseExpression)):
            operand_str = f"({operand_str})"
        return f"{self.op_symbol}{operand_str}"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        val = self.operand.evaluate(none_policy)
        if val is None:
            return None
        return self.op(val)

    def to_c(self, symbols=None) -> str:
        operand_str = self.operand.to_c(symbols)
        if isinstance(self.operand, (ArithmeticExpression, BitwiseExpression)):
            operand_str = f'({operand_str})'
        return f'{self.op_symbol}{operand_str}'


@dataclass(frozen=True, eq=False)
class BitwiseExpression(NumericExpression):
    """Binary bitwise expression (&, |, ^, <<, >>).
    
    Created when using bitwise operators on NumericExpression instances.
    
    Attributes:
        left: The left operand expression.
        right: The right operand expression.
        op: The operation function.
        op_symbol: String representation of the operator.
    """
    left: Expression
    right: Expression
    op: Callable[[Any, Any], Any]
    op_symbol: str

    def __repr__(self) -> str:
        """Return Python-like syntax for bitwise expression."""
        left_str = repr(self.left)
        right_str = repr(self.right)
        
        # Add parentheses around arithmetic expressions
        if isinstance(self.left, ArithmeticExpression):
            left_str = f"({left_str})"
        if isinstance(self.right, ArithmeticExpression):
            right_str = f"({right_str})"
        
        return f"{left_str} {self.op_symbol} {right_str}"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        left_val = self.left.evaluate(none_policy)
        right_val = self.right.evaluate(none_policy)
        if left_val is None or right_val is None:
            return None
        return self.op(left_val, right_val)

    def to_c(self, symbols=None) -> str:
        left_str = self.left.to_c(symbols)
        right_str = self.right.to_c(symbols)
        if isinstance(self.left, ArithmeticExpression):
            left_str = f'({left_str})'
        if isinstance(self.right, ArithmeticExpression):
            right_str = f'({right_str})'
        return f'{left_str} {self.op_symbol} {right_str}'


@dataclass(frozen=True, eq=False)
class UnaryBitwiseExpression(NumericExpression):
    """Unary bitwise expression (~).
    
    Created when using the bitwise NOT operator on NumericExpression instances.
    
    Attributes:
        operand: The operand expression.
        op: The operation function.
        op_symbol: String representation of the operator.
    """
    operand: Expression
    op: Callable[[Any], Any]
    op_symbol: str

    def __repr__(self) -> str:
        """Return Python-like syntax for unary bitwise expression."""
        operand_str = repr(self.operand)
        # Add parentheses for complex expressions
        if isinstance(self.operand, (ArithmeticExpression, BitwiseExpression)):
            operand_str = f"({operand_str})"
        return f"{self.op_symbol}{operand_str}"

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        val = self.operand.evaluate(none_policy)
        if val is None:
            return None
        return self.op(val)

    def to_c(self, symbols=None) -> str:
        operand_str = self.operand.to_c(symbols)
        if isinstance(self.operand, (ArithmeticExpression, BitwiseExpression)):
            operand_str = f'({operand_str})'
        return f'{self.op_symbol}{operand_str}'


@dataclass(frozen=True, eq=False)
class MacroParam(NumericExpression):
    """A C macro parameter placeholder.

    Used in expression trees that will be rendered as C macro bodies via
    :meth:`to_c`.  Cannot be evaluated to a Python value.

    Example::

        id_ = MacroParam('id')
        sub = MacroParam('sub_id')
        expr = base_ref + id_ * size_ref + sub * 4
        # expr.to_c(symbols) → "SOC_FC_TIMER0_ADDR + (id) * SOC_FC_TIMER0_SIZE + (sub_id) * 4"
    """
    param_name: str

    def __repr__(self) -> str:
        return self.param_name

    def evaluate(self, none_policy: NonePolicy = 'fail') -> Any:
        raise ValueError(
            f'Cannot evaluate macro parameter {self.param_name!r} — '
            f'use to_c() to render as C code')

    def to_c(self, symbols=None) -> str:
        return f'({self.param_name})'
