# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""Expression system for configuration validation and filtering.

This module provides a flexible expression system that allows building complex
expressions using Python operators. Expressions can reference configuration
fields and be evaluated against config instances or classes.

Key Features:
    - Expression hierarchy: Expression -> BooleanExpression, NumericExpression
    - BooleanExpression: Logical operations via explicit methods (logical_and, logical_or, logical_not)
    - NumericExpression: Arithmetic (+, -, *, /, etc.) and bitwise (&, |, ^, ~, <<, >>) operators
    - Comparison operators (==, !=, <, <=, >, >=) produce BooleanExpressions
    - Field references to config instances or classes
    - Evaluation with flexible None-handling policies
    - Class-level evaluation returns results for all instances

Example:
    >>> class MyConfig(Config):
    ...     value: int = 0
    ...     enabled: bool = True
    
    >>> # Create some instances
    >>> cfg1 = MyConfig(name='cfg1', value=10)
    >>> cfg2 = MyConfig(name='cfg2', value=20)
    
    >>> # Build a condition using explicit logical methods
    >>> condition = (cfg1.get_ref('value') > 5).logical_and(cfg1.get_ref('enabled'))
    
    >>> # Evaluate on instance
    >>> condition.evaluate()  # Returns True or False
    
    >>> # Class-level condition
    >>> class_condition = MyConfig.get_ref('value') > 15
    >>> class_condition.evaluate()  # Returns True if all instances satisfy
    
    >>> # Bitwise operations (on NumericExpression only)
    >>> bitwise_expr = cfg1.get_ref('value') & 0xFF
"""

from .base import (
    NonePolicy,
    ConditionResultList,
    ConditionError,
    Expression,
    ExpressionRegistry,
)

from .boolean import (
    BooleanExpression,
    LogicalAnd,
    LogicalOr,
    LogicalNot,
    ConditionEvaluator,
)

from .comparison import (
    BinaryCondition,
    EqualityCondition,
    InequalityCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
)

from .numeric import (
    ValueExpression,
    NumericExpression,
    ConstantValue,
    ArithmeticExpression,
    UnaryArithmeticExpression,
    BitwiseExpression,
    UnaryBitwiseExpression,
    MacroParam,
)

from .field_ref import ConfigFieldRef
from .environment import EnvironmentVariableExpression, env
from .define_ops import ListToTuplesExpression, list_to_tuples
from .functional import (
    Expressions,
    LambdaRefExpression,
    LambdaFunctionExpression,
    MapExpression,
    StringExpression,
    StringConcatExpression,
    UpperExpression,
    LowerExpression,
    TupleExpression,
)

__all__ = [
    # Base
    "NonePolicy",
    "ConditionResultList",
    "ConditionError",
    "Expression",
    "ExpressionRegistry",
    # Boolean
    "BooleanExpression",
    "LogicalAnd",
    "LogicalOr",
    "LogicalNot",
    "ConditionEvaluator",
    # Comparison
    "BinaryCondition",
    "EqualityCondition",
    "InequalityCondition",
    "LessThanCondition",
    "LessThanOrEqualCondition",
    "GreaterThanCondition",
    "GreaterThanOrEqualCondition",
    # Numeric
    "ValueExpression",
    "NumericExpression",
    "ConstantValue",
    "ArithmeticExpression",
    "UnaryArithmeticExpression",
    "BitwiseExpression",
    "UnaryBitwiseExpression",
    "MacroParam",
    # Field ref
    "ConfigFieldRef",
    # Environment
    "EnvironmentVariableExpression",
    "env",
    "ListToTuplesExpression",
    "list_to_tuples",
    # Functional
    "Expressions",
    "LambdaRefExpression",
    "LambdaFunctionExpression",
    "MapExpression",
    "UpperExpression",
    "LowerExpression",
    "StringExpression",
    "StringConcatExpression",
    "TupleExpression",
]
