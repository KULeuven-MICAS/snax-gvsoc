"""
Pytest tests for Condition classes and boolean expression construction.

Tests cover:
- ConstantValue wrapping
- Equality and inequality comparisons with constants
- Comparison operations (lt, le, gt, ge)
- Logical operations (and, or)
- ConfigFieldRef functionality
- Complex boolean expressions
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from config_tree.expression import (
    ConstantValue,
    EqualityCondition,
    InequalityCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
    LogicalAnd,
    LogicalOr,
    ConfigFieldRef,
    ConditionError,
    ConditionEvaluator
)
from config_tree import Config, cfg_field


class TestConstantValue:
    """Tests for ConstantValue wrapping."""

    def test_constant_value_creation(self):
        """Test creating ConstantValue with various types."""
        const_int = ConstantValue(42)
        assert const_int.value == 42
        
        const_str = ConstantValue("hello")
        assert const_str.value == "hello"
        
        const_bool = ConstantValue(True)
        assert const_bool.value is True
        
        const_float = ConstantValue(3.14)
        assert const_float.value == 3.14

    def test_constant_value_immutable(self):
        """Test that ConstantValue is immutable (frozen)."""
        const = ConstantValue(42)
        with pytest.raises(AttributeError):
            const.value = 100


class TestEqualityComparisons:
    """Tests for equality and inequality comparisons."""

    def test_equality_with_constant(self):
        """Test equality comparison with a constant value."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref == 42
        
        assert isinstance(condition, EqualityCondition)
        assert condition.left == field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_inequality_with_constant(self):
        """Test inequality comparison with a constant value."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref != 100
        
        assert isinstance(condition, InequalityCondition)
        assert condition.left == field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 100

    def test_equality_with_string_constant(self):
        """Test equality comparison with a string constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            name: str = "default"
        
        field_ref = ConfigFieldRef(TestConfig, 'name')
        condition = field_ref == "test"
        
        assert isinstance(condition, EqualityCondition)
        assert condition.right.value == "test"

    def test_equality_with_bool_constant(self):
        """Test equality comparison with a boolean constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            enabled: bool = False
        
        field_ref = ConfigFieldRef(TestConfig, 'enabled')
        condition = field_ref == True
        
        assert isinstance(condition, EqualityCondition)
        assert condition.right.value is True

    def test_equality_with_condition(self):
        """Test equality comparison between two conditions."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        condition = field_ref1 == field_ref2
        
        assert isinstance(condition, EqualityCondition)
        assert condition.left == field_ref1
        assert condition.right == field_ref2
        assert not isinstance(condition.right, ConstantValue)


class TestComparisonOperations:
    """Tests for less than, greater than, etc. comparisons."""

    def test_less_than_with_constant(self):
        """Test less than comparison with a constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref < 100
        
        assert isinstance(condition, LessThanCondition)
        assert condition.left == field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 100

    def test_less_than_or_equal_with_constant(self):
        """Test less than or equal comparison with a constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref <= 100
        
        assert isinstance(condition, LessThanOrEqualCondition)
        assert condition.right.value == 100

    def test_greater_than_with_constant(self):
        """Test greater than comparison with a constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref > 10
        
        assert isinstance(condition, GreaterThanCondition)
        assert condition.right.value == 10

    def test_greater_than_or_equal_with_constant(self):
        """Test greater than or equal comparison with a constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = field_ref >= 10
        
        assert isinstance(condition, GreaterThanOrEqualCondition)
        assert condition.right.value == 10

    def test_comparison_with_float(self):
        """Test comparison operations with float constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            ratio: float = 0.5
        
        field_ref = ConfigFieldRef(TestConfig, 'ratio')
        
        condition1 = field_ref < 1.0
        assert condition1.right.value == 1.0
        
        condition2 = field_ref >= 0.1
        assert condition2.right.value == 0.1


class TestLogicalOperations:
    """Tests for logical AND and OR operations."""

    def test_logical_and_simple(self):
        """Test simple logical AND operation."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        
        condition = (field_ref1 == 42).logical_and(field_ref2 == 100)
        
        assert isinstance(condition, LogicalAnd)
        assert len(condition.conditions) == 2
        assert isinstance(condition.conditions[0], EqualityCondition)
        assert isinstance(condition.conditions[1], EqualityCondition)

    def test_logical_or_simple(self):
        """Test simple logical OR operation."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        
        condition = (field_ref1 == 42).logical_or(field_ref2 == 100)
        
        assert isinstance(condition, LogicalOr)
        assert len(condition.conditions) == 2

    def test_logical_and_chaining(self):
        """Test chaining multiple AND operations."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
            value3: int = 200
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        field_ref3 = ConfigFieldRef(TestConfig, 'value3')
        
        # Chain multiple ANDs - should flatten into single LogicalAnd
        condition = (field_ref1 == 42).logical_and(field_ref2 == 100).logical_and(field_ref3 == 200)
        
        assert isinstance(condition, LogicalAnd)
        assert len(condition.conditions) == 3

    def test_logical_or_chaining(self):
        """Test chaining multiple OR operations."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
            value3: int = 200
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        field_ref3 = ConfigFieldRef(TestConfig, 'value3')
        
        # Chain multiple ORs - should flatten into single LogicalOr
        condition = (field_ref1 == 42).logical_or(field_ref2 == 100).logical_or(field_ref3 == 200)
        
        assert isinstance(condition, LogicalOr)
        assert len(condition.conditions) == 3

    def test_mixed_logical_operations(self):
        """Test mixing AND and OR operations."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value1: int = 42
            value2: int = 100
            value3: int = 200
        
        field_ref1 = ConfigFieldRef(TestConfig, 'value1')
        field_ref2 = ConfigFieldRef(TestConfig, 'value2')
        field_ref3 = ConfigFieldRef(TestConfig, 'value3')
        
        # (value1 == 42 AND value2 == 100) OR value3 == 200
        and_condition = (field_ref1 == 42).logical_and(field_ref2 == 100)
        or_condition = and_condition.logical_or(field_ref3 == 200)
        
        assert isinstance(or_condition, LogicalOr)
        assert len(or_condition.conditions) == 2
        assert isinstance(or_condition.conditions[0], LogicalAnd)
        assert isinstance(or_condition.conditions[1], EqualityCondition)


class TestConfigFieldRef:
    """Tests for ConfigFieldRef functionality."""

    def test_config_field_ref_creation(self):
        """Test creating ConfigFieldRef with class and field name."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        assert field_ref.config == TestConfig
        assert field_ref.field_name == 'value'

    def test_config_field_ref_with_instance(self):
        """Test creating ConfigFieldRef with config instance."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        config = TestConfig('test')
        field_ref = ConfigFieldRef(config, 'value')
        
        assert field_ref.config == config
        assert field_ref.field_name == 'value'

    def test_config_field_ref_immutable(self):
        """Test that ConfigFieldRef is immutable (frozen)."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        with pytest.raises(AttributeError):
            field_ref.field_name = 'other'

    def test_config_field_get_ref(self):
        """Test creating ConfigFieldRef using get_ref method."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        config = TestConfig('test')
        instance_field_ref = config.get_ref('value')
        class_field_ref = TestConfig.get_ref('value')

        
        assert instance_field_ref.config == config
        assert instance_field_ref.field_name == 'value'
        assert class_field_ref.config == TestConfig
        assert class_field_ref.field_name == 'value'


class TestComplexExpressions:
    """Tests for complex boolean expressions."""

    def test_complex_expression_1(self):
        """Test complex expression: (value > 10) AND (value < 100)."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        condition = (field_ref > 10).logical_and(field_ref < 100)
        
        assert isinstance(condition, LogicalAnd)
        assert len(condition.conditions) == 2
        assert isinstance(condition.conditions[0], GreaterThanCondition)
        assert isinstance(condition.conditions[1], LessThanCondition)

    def test_complex_expression_2(self):
        """Test complex expression with multiple fields and operations."""
        @dataclass(eq=False)
        class TestConfig(Config):
            min_val: int = 10
            max_val: int = 100
            enabled: bool = True
        
        min_ref = ConfigFieldRef(TestConfig, 'min_val')
        max_ref = ConfigFieldRef(TestConfig, 'max_val')
        enabled_ref = ConfigFieldRef(TestConfig, 'enabled')
        
        # (min_val >= 0 AND max_val <= 200) AND enabled == True
        range_check = (min_ref >= 0).logical_and(max_ref <= 200)
        full_condition = range_check.logical_and(enabled_ref == True)
        
        assert isinstance(full_condition, LogicalAnd)
        assert len(full_condition.conditions) == 3

    def test_complex_expression_3(self):
        """Test expression with OR at top level."""
        @dataclass(eq=False)
        class TestConfig(Config):
            mode: str = "normal"
            override: bool = False
        
        mode_ref = ConfigFieldRef(TestConfig, 'mode')
        override_ref = ConfigFieldRef(TestConfig, 'override')
        
        # mode == "debug" OR override == True
        condition = (mode_ref == "debug").logical_or(override_ref == True)
        
        assert isinstance(condition, LogicalOr)
        assert len(condition.conditions) == 2

    def test_nested_logical_operations(self):
        """Test deeply nested logical operations."""
        @dataclass(eq=False)
        class TestConfig(Config):
            a: int = 1
            b: int = 2
            c: int = 3
            d: int = 4
        
        a_ref = ConfigFieldRef(TestConfig, 'a')
        b_ref = ConfigFieldRef(TestConfig, 'b')
        c_ref = ConfigFieldRef(TestConfig, 'c')
        d_ref = ConfigFieldRef(TestConfig, 'd')
        
        # ((a == 1 AND b == 2) OR c == 3) AND d == 4
        ab_condition = (a_ref == 1).logical_and(b_ref == 2)
        abc_condition = ab_condition.logical_or(c_ref == 3)
        full_condition = abc_condition.logical_and(d_ref == 4)
        
        assert isinstance(full_condition, LogicalAnd)
        # The LogicalAnd should have flattened the last AND
        assert len(full_condition.conditions) == 2
        assert isinstance(full_condition.conditions[0], LogicalOr)
        assert isinstance(full_condition.conditions[1], EqualityCondition)


class TestConstantTypes:
    """Tests for various constant types in conditions."""

    def test_integer_constants(self):
        """Test conditions with integer constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 42
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        
        conditions = [
            field_ref == 0,
            field_ref == -10,
            field_ref == 1000000,
            field_ref != 42
        ]
        
        for cond in conditions:
            assert isinstance(cond.right, ConstantValue)
            assert isinstance(cond.right.value, int)

    def test_string_constants(self):
        """Test conditions with string constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            name: str = "default"
        
        field_ref = ConfigFieldRef(TestConfig, 'name')
        
        conditions = [
            field_ref == "test",
            field_ref == "",
            field_ref != "other"
        ]
        
        for cond in conditions:
            assert isinstance(cond.right, ConstantValue)
            assert isinstance(cond.right.value, str)

    def test_boolean_constants(self):
        """Test conditions with boolean constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            enabled: bool = False
        
        field_ref = ConfigFieldRef(TestConfig, 'enabled')
        
        cond_true = field_ref == True
        cond_false = field_ref == False
        
        assert cond_true.right.value is True
        assert cond_false.right.value is False

    def test_hex_integer_constants(self):
        """Test conditions with hex integer constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            address: int = 0x1000
        
        field_ref = ConfigFieldRef(TestConfig, 'address')
        condition = field_ref == 0x8000_0000
        
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 0x80000000

    def test_none_constant(self):
        """Test conditions with None constant."""
        @dataclass(eq=False)
        class TestConfig(Config):
            optional_value: int = None
        
        field_ref = ConfigFieldRef(TestConfig, 'optional_value')
        condition = field_ref == None
        
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value is None


class TestReflectedOperators:
    """Tests for reflected (reverse) comparison operators with constants on the left."""

    def test_reflected_equality(self):
        """Test constant == condition creates correct EqualityCondition.
        
        Note: Python's equality doesn't use __req__; it calls __eq__ on the
        right operand, so both '42 == field_ref' and 'field_ref == 42' produce
        the same structure with field_ref on the left.
        """
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left side - Python calls field_ref.__eq__(42)
        condition = 42 == field_ref
        
        assert isinstance(condition, EqualityCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_inequality(self):
        """Test constant != condition creates correct InequalityCondition.
        
        Note: Python's inequality doesn't use __rne__; it calls __ne__ on the
        right operand, so both '42 != field_ref' and 'field_ref != 42' produce
        the same structure with field_ref on the left.
        """
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left side - Python calls field_ref.__ne__(42)
        condition = 42 != field_ref
        
        assert isinstance(condition, InequalityCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_less_than(self):
        """Test constant < condition creates correct GreaterThanCondition."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left: 42 < field means field > 42
        condition = 42 < field_ref
        
        assert isinstance(condition, GreaterThanCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_less_than_or_equal(self):
        """Test constant <= condition creates correct GreaterThanOrEqualCondition."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left: 42 <= field means field >= 42
        condition = 42 <= field_ref
        
        assert isinstance(condition, GreaterThanOrEqualCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_greater_than(self):
        """Test constant > condition creates correct LessThanCondition."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left: 42 > field means field < 42
        condition = 42 > field_ref
        
        assert isinstance(condition, LessThanCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_greater_than_or_equal(self):
        """Test constant >= condition creates correct LessThanOrEqualCondition."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        # Constant on the left: 42 >= field means field <= 42
        condition = 42 >= field_ref
        
        assert isinstance(condition, LessThanOrEqualCondition)
        assert condition.left is field_ref
        assert isinstance(condition.right, ConstantValue)
        assert condition.right.value == 42

    def test_reflected_with_strings(self):
        """Test reflected operators work with string constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            name: str = "default"
        
        field_ref = ConfigFieldRef(TestConfig, 'name')
        
        # Python calls field_ref.__eq__("test") for both expressions
        eq_cond = "test" == field_ref
        assert isinstance(eq_cond, EqualityCondition)
        assert eq_cond.left is field_ref
        assert eq_cond.right.value == "test"
        
        ne_cond = "test" != field_ref
        assert isinstance(ne_cond, InequalityCondition)
        assert ne_cond.left is field_ref
        assert ne_cond.right.value == "test"

    def test_reflected_with_boolean(self):
        """Test reflected operators work with boolean constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            enabled: bool = False
        
        field_ref = ConfigFieldRef(TestConfig, 'enabled')
        
        # Python calls field_ref.__eq__(True) for both expressions
        eq_cond = True == field_ref
        assert isinstance(eq_cond, EqualityCondition)
        assert eq_cond.left is field_ref
        assert eq_cond.right.value is True
        
        ne_cond = False != field_ref
        assert isinstance(ne_cond, InequalityCondition)
        assert ne_cond.left is field_ref
        assert ne_cond.right.value is False

    def test_reflected_with_hex(self):
        """Test reflected operators work with hex integer constants."""
        @dataclass(eq=False)
        class TestConfig(Config):
            address: int = 0x1000
        
        field_ref = ConfigFieldRef(TestConfig, 'address')
        
        # Equality: Python calls field_ref.__eq__(constant)
        eq_cond = 0x8000_0000 == field_ref
        assert isinstance(eq_cond, EqualityCondition)
        assert eq_cond.left is field_ref
        assert eq_cond.right.value == 0x80000000
        
        # Comparison: Python reverses to field_ref < 0x100
        gt_cond = 0x100 > field_ref  # field < 0x100
        assert isinstance(gt_cond, LessThanCondition)
        assert gt_cond.left is field_ref
        assert gt_cond.right.value == 0x100

    def test_reflected_in_logical_expression(self):
        """Test reflected operators work in logical expressions."""
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
            flag: bool = True
        
        value_ref = ConfigFieldRef(TestConfig, 'value')
        flag_ref = ConfigFieldRef(TestConfig, 'flag')
        
        # Complex expression: (100 > value) AND (True == flag)
        condition = (100 > value_ref).logical_and(True == flag_ref)
        
        assert isinstance(condition, LogicalAnd)
        assert isinstance(condition.conditions[0], LessThanCondition)
        assert isinstance(condition.conditions[1], EqualityCondition)

    def test_reflected_symmetry(self):
        """Test that reflected and normal operators produce equivalent results.
        
        For equality, both 'field_ref == 42' and '42 == field_ref' create the
        same structure because Python calls field_ref.__eq__(42) in both cases.
        For comparisons, Python properly reverses the operator, so '42 < field_ref'
        becomes 'field_ref > 42'.
        """
        @dataclass(eq=False)
        class TestConfig(Config):
            value: int = 10
        
        field_ref = ConfigFieldRef(TestConfig, 'value')
        
        # Equality: both produce identical structures
        normal_eq = field_ref == 42
        reflected_eq = 42 == field_ref
        
        assert isinstance(normal_eq, EqualityCondition)
        assert isinstance(reflected_eq, EqualityCondition)
        # Both have field_ref on the left, constant on the right
        assert normal_eq.left is field_ref
        assert reflected_eq.left is field_ref
        assert isinstance(normal_eq.right, ConstantValue)
        assert isinstance(reflected_eq.right, ConstantValue)
        assert normal_eq.right.value == 42
        assert reflected_eq.right.value == 42
        
        # Comparison: operator gets reversed 
        normal_lt = field_ref < 100      # field < 100
        reflected_gt = 100 > field_ref   # field < 100 (reversed from constant > field)
        
        assert isinstance(normal_lt, LessThanCondition)
        assert isinstance(reflected_gt, LessThanCondition)
        # Both should be semantically equivalent
        assert normal_lt.left is field_ref
        assert reflected_gt.left is field_ref
        assert normal_lt.right.value == 100
        assert reflected_gt.right.value == 100


class TestConditionEvaluation:
    """Tests for direct evaluation of conditions on config instances and classes."""

    def test_evaluate_instance_field(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = 5
            bar: int = 10
        cfg = MyConfig("a")
        cond = cfg.get_ref('foo') == 5
        assert cond.evaluate() is True
        cond2 = cfg.get_ref('bar') > 20
        assert cond2.evaluate() is False

    def test_evaluate_class_field(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = 1
        # Create multiple instances
        a = MyConfig("a", foo=1)
        b = MyConfig("b", foo=1)
        c = MyConfig("c", foo=2)
        cond = MyConfig.get_ref('foo') == 1
        # Only a and b match, so should be False
        assert cond.evaluate() is False
        # Now set all to 1
        c.foo = 1
        assert cond.evaluate() is True

    def test_evaluate_none_policy_fail(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = None
        cfg = MyConfig("a")
        cond = cfg.get_ref('foo') == 1
        # None field, should fail
        assert cond.evaluate(none_policy='fail') is False

    def test_evaluate_none_policy_ignore(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = None
        cfg = MyConfig("a")
        cond = cfg.get_ref('foo') == 1
        # None field, should pass (ignore)
        assert cond.evaluate(none_policy='ignore') is True

    def test_evaluate_logical_and_or(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = 1
            bar: int = 2
        cfg = MyConfig("a")
        cond = (cfg.get_ref('foo') == 1).logical_and(cfg.get_ref('bar') == 2)
        assert cond.evaluate() is True
        cond2 = (cfg.get_ref('foo') == 1).logical_or(cfg.get_ref('bar') == 3)
        assert cond2.evaluate() is True
        cond3 = (cfg.get_ref('foo') == 0).logical_or(cfg.get_ref('bar') == 3)
        assert cond3.evaluate() is False

    def test_evaluate_class_with_none(self):
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = None
        a = MyConfig("a", foo=None)
        b = MyConfig("b", foo=1)
        cond = MyConfig.get_ref('foo') == 1
        # With 'fail', should be False (a.foo is None)
        assert cond.evaluate(none_policy='fail') is False
        # With 'ignore', should be True (None fields ignored)
        assert cond.evaluate(none_policy='ignore') is True

    def test_evaluate_class_vs_class(self):
        """Test comparing two class-level field references."""
        @dataclass(eq=False)
        class ConfigA(Config):
            value: int = 1
        
        @dataclass(eq=False)
        class ConfigB(Config):
            value: int = 1
        
        # Create instances
        a1 = ConfigA("a1", value=5)
        a2 = ConfigA("a2", value=5)
        b1 = ConfigB("b1", value=5)
        b2 = ConfigB("b2", value=5)
        
        # All values equal
        cond = ConfigA.get_ref('value') == ConfigB.get_ref('value')
        assert cond.evaluate() is True
        
        # Change one value
        a1.value = 10
        assert cond.evaluate() is False

    def test_evaluate_class_vs_instance(self):
        """Test comparing class-level ref to instance-level ref."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = 1
        
        instance = MyConfig("single", value=5)
        a = MyConfig("a", value=5)
        b = MyConfig("b", value=5)
        
        # Class ref vs instance ref
        cond = MyConfig.get_ref('value') == instance.get_ref('value')
        assert cond.evaluate() is True  # All instances have value=5
        
        # Change class instance
        a.value = 10
        assert cond.evaluate() is False  # Not all match instance

    def test_evaluate_instance_vs_class(self):
        """Test comparing instance-level ref to class-level ref."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = 1
        
        instance = MyConfig("single", value=5)
        a = MyConfig("a", value=5)
        b = MyConfig("b", value=5)
        
        # Instance ref vs class ref
        cond = instance.get_ref('value') == MyConfig.get_ref('value')
        assert cond.evaluate() is True
        
        b.value = 7
        assert cond.evaluate() is False

    def test_evaluate_class_vs_constant(self):
        """Test comparing class-level ref to constant."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = 1
        
        a = MyConfig("a", value=10)
        b = MyConfig("b", value=10)
        c = MyConfig("c", value=10)
        
        # All instances equal to constant
        cond = MyConfig.get_ref('value') == 10
        assert cond.evaluate() is True
        
        # One doesn't match
        c.value = 5
        assert cond.evaluate() is False

    def test_evaluate_class_comparison_operators(self):
        """Test all comparison operators with class refs."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = 1
        
        a = MyConfig("a", value=5)
        b = MyConfig("b", value=10)
        c = MyConfig("c", value=15)
        
        # Less than - all must be less than 20
        assert (MyConfig.get_ref('value') < 20).evaluate() is True
        assert (MyConfig.get_ref('value') < 10).evaluate() is False  # b=10 not < 10
        
        # Less than or equal
        assert (MyConfig.get_ref('value') <= 15).evaluate() is True
        assert (MyConfig.get_ref('value') <= 14).evaluate() is False
        
        # Greater than
        assert (MyConfig.get_ref('value') > 3).evaluate() is True
        assert (MyConfig.get_ref('value') > 5).evaluate() is False  # a=5 not > 5
        
        # Greater than or equal
        assert (MyConfig.get_ref('value') >= 5).evaluate() is True
        assert (MyConfig.get_ref('value') >= 6).evaluate() is False
        
        # Inequality
        assert (MyConfig.get_ref('value') != 100).evaluate() is True
        a.value = 100
        assert (MyConfig.get_ref('value') != 100).evaluate() is False  # a=100

    def test_evaluate_logical_and_with_class_refs(self):
        """Test LogicalAnd with class-level references."""
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = 1
            bar: int = 1
        
        a = MyConfig("a", foo=5, bar=10)
        b = MyConfig("b", foo=5, bar=10)
        
        # Both conditions true for all instances
        cond = (MyConfig.get_ref('foo') == 5).logical_and(MyConfig.get_ref('bar') == 10)
        assert cond.evaluate() is True
        
        # First fails
        a.foo = 1
        assert cond.evaluate() is False
        
        # Reset and make second fail
        a.foo = 5
        b.bar = 20
        assert cond.evaluate() is False

    def test_evaluate_logical_or_with_class_refs(self):
        """Test LogicalOr with class-level references."""
        @dataclass(eq=False)
        class MyConfig(Config):
            foo: int = 1
            bar: int = 1
        
        a = MyConfig("a", foo=5, bar=10)
        b = MyConfig("b", foo=5, bar=10)
        
        # First condition true for all
        cond = (MyConfig.get_ref('foo') == 5).logical_or(MyConfig.get_ref('bar') == 999)
        assert cond.evaluate() is True
        
        # Both fail
        a.foo = 1
        b.foo = 1
        a.bar = 1
        b.bar = 1
        assert cond.evaluate() is False

    def test_evaluate_mixed_class_instance_logical(self):
        """Test logical operations with mixed class and instance refs."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = 1
        
        instance = MyConfig("single", value=10)
        a = MyConfig("a", value=10)  # Changed to match instance
        b = MyConfig("b", value=10)  # Changed to match instance
        
        # Class ref AND instance ref - all instances have value=10
        cond = (MyConfig.get_ref('value') == 10).logical_and(instance.get_ref('value') == 10)
        assert cond.evaluate() is True
        
        # Change one instance
        a.value = 1
        assert cond.evaluate() is False

    def test_evaluate_empty_class(self):
        """Test evaluating condition on class with no instances."""
        @dataclass(eq=False)
        class EmptyConfig(Config):
            value: int = 1
        
        # No instances created
        cond = EmptyConfig.get_ref('value') == 10
        # Empty list - all() returns True
        assert cond.evaluate() is True

    def test_evaluate_class_partial_none_ignore(self):
        """Test class ref with some instances having None values, using ignore policy."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = None
        
        a = MyConfig("a", value=5)
        b = MyConfig("b", value=None)
        c = MyConfig("c", value=5)
        
        cond = MyConfig.get_ref('value') == 5
        # With 'fail', b.value=None fails
        assert cond.evaluate(none_policy='fail') is False
        # With 'ignore', None values are filtered out
        assert cond.evaluate(none_policy='ignore') is True

    def test_evaluate_class_all_none_ignore(self):
        """Test class ref with all instances having None values, using ignore policy."""
        @dataclass(eq=False)
        class MyConfig(Config):
            value: int = None
        
        a = MyConfig("a", value=None)
        b = MyConfig("b", value=None)
        
        cond = MyConfig.get_ref('value') == 5
        # With 'ignore', all None values filtered, empty list - all() returns True
        assert cond.evaluate(none_policy='ignore') is True

    def test_evaluate_complex_nested_mixed_refs(self):
        """Test complex nested conditions with mixed class and instance refs."""
        @dataclass(eq=False)
        class ConfigA(Config):
            x: int = 1
            y: int = 1
        
        @dataclass(eq=False)
        class ConfigB(Config):
            z: int = 1
        
        instance_a = ConfigA("inst_a", x=10, y=20)
        a1 = ConfigA("a1", x=5, y=10)
        a2 = ConfigA("a2", x=5, y=10)
        
        b1 = ConfigB("b1", z=30)
        b2 = ConfigB("b2", z=30)
        
        # ((ClassA.x == 5) AND (instance_a.y == 20)) OR (ClassB.z > 25)
        cond = (
            (ConfigA.get_ref('x') == 5).logical_and(instance_a.get_ref('y') == 20)
        ).logical_or(
            ConfigB.get_ref('z') > 25
        )
        assert cond.evaluate() is True
        
        # Break first part
        a1.x = 1
        # Second part still true
        assert cond.evaluate() is True
        
        # Break second part too
        b1.z = 1
        b2.z = 1
        assert cond.evaluate() is False

    def test_evaluate_class_comparison_with_inequality(self):
        """Test inequality comparisons between class refs."""
        @dataclass(eq=False)
        class ConfigA(Config):
            value: int = 1
        
        @dataclass(eq=False)
        class ConfigB(Config):
            value: int = 1
        
        a1 = ConfigA("a1", value=5)
        a2 = ConfigA("a2", value=10)
        b1 = ConfigB("b1", value=7)
        b2 = ConfigB("b2", value=12)
        
        # Check if all A values < all B values
        cond = ConfigA.get_ref('value') < ConfigB.get_ref('value')
        # a1=5 < b1=7 ✓, a1=5 < b2=12 ✓, a2=10 < b1=7 ✗
        assert cond.evaluate() is False
        
        # Make all A < all B
        a2.value = 3
        # a1=5 < b1=7 ✓, a1=5 < b2=12 ✓, a2=3 < b1=7 ✓, a2=3 < b2=12 ✓
        assert cond.evaluate() is True


class TestConditionMessage:
    """Tests for condition message and ConditionEvaluator."""

    def test_message_with_custom_message(self):
        """Test that message() creates a ConditionEvaluator with custom message."""
        
        class TestConfig(Config):
            value: int = 5
        
        cfg = TestConfig("test")
        condition = cfg.get_ref('value') > 10
        evaluator = condition.message("Value must be greater than 10")
        
        assert isinstance(evaluator, ConditionEvaluator)
        assert evaluator.condition == condition
        assert evaluator.message == "Value must be greater than 10"

    def test_message_with_none_message(self):
        """Test that message() with None creates evaluator with None message."""
        
        class TestConfig(Config):
            value: int = 5
        
        cfg = TestConfig("test")
        condition = cfg.get_ref('value') > 10
        evaluator = condition.message()
        
        assert isinstance(evaluator, ConditionEvaluator)
        assert evaluator.message is None

    def test_evaluator_returns_true_on_success(self):
        """Test that ConditionEvaluator returns True when condition succeeds."""
        
        class TestConfig(Config):
            value: int = 15
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('value') > 10).message("Value too small")
        
        result = condition.evaluate()
        assert result is True

    def test_evaluator_raises_with_custom_message(self):
        """Test that ConditionEvaluator raises ConditionError with custom message on failure."""
        
        class TestConfig(Config):
            value: int = 5
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('value') > 10).message("Value must be greater than 10")
        
        with pytest.raises(ConditionError) as exc_info:
            condition.evaluate()
        
        assert str(exc_info.value) == "Value must be greater than 10"

    def test_evaluator_raises_with_default_message(self):
        """Test that ConditionEvaluator raises ConditionError with default message when message is None."""
        
        class TestConfig(Config):
            value: int = 5
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('value') > 10).message()
        
        with pytest.raises(ConditionError) as exc_info:
            condition.evaluate()
        
        # Default message should contain "Condition failed:"
        assert "Condition failed:" in str(exc_info.value)

    def test_evaluator_with_complex_condition(self):
        """Test ConditionEvaluator with complex logical conditions."""
        
        class TestConfig(Config):
            value: int = 5
            enabled: bool = False
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('value') > 10).logical_and(cfg.get_ref('enabled') == True).message(
            "Value must be > 10 AND enabled must be True"
        )
        
        with pytest.raises(ConditionError) as exc_info:
            condition.evaluate()
        
        assert str(exc_info.value) == "Value must be > 10 AND enabled must be True"

    def test_evaluator_with_equality_condition(self):
        """Test ConditionEvaluator with equality condition."""
        
        class TestConfig(Config):
            status: str = "pending"
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('status') == 'active').message("Status must be active")
        
        with pytest.raises(ConditionError) as exc_info:
            condition.evaluate()
        
        assert str(exc_info.value) == "Status must be active"

    def test_evaluator_with_or_condition(self):
        """Test ConditionEvaluator with OR condition."""
        
        class TestConfig(Config):
            value: int = 50
        
        cfg = TestConfig("test")
        # This should pass because value=50 is in range
        condition = (cfg.get_ref('value') < 10).logical_or(cfg.get_ref('value') > 100).message(
            "Value must be < 10 or > 100"
        )
        
        with pytest.raises(ConditionError) as exc_info:
            condition.evaluate()
        
        assert str(exc_info.value) == "Value must be < 10 or > 100"

    def test_evaluator_immutable(self):
        """Test that ConditionEvaluator is immutable (frozen)."""
        
        class TestConfig(Config):
            value: int = 5
        
        cfg = TestConfig("test")
        evaluator = (cfg.get_ref('value') > 10).message("Test")
        
        with pytest.raises(AttributeError):
            evaluator.message = "New message"

    def test_evaluator_with_none_policy(self):
        """Test that ConditionEvaluator respects none_policy parameter."""
        
        class TestConfig(Config):
            value: int = None
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('value') > 10).message("Value required")
        
        # With 'ignore' policy, None should be ignored
        result = condition.evaluate(none_policy='ignore')
        assert result is True
        
        # With 'fail' policy (default), it should raise
        with pytest.raises(Exception):  # Will raise TypeError or similar
            condition.evaluate(none_policy='fail')


class TestPropagateNonePolicy:
    """Tests for the 'propagate' none_policy with three-valued logic."""

    def test_comparison_with_none_returns_none(self):
        """Test that comparisons with None return None under propagate policy."""
        
        class TestConfig(Config):
            value: int | None = None
        
        cfg = TestConfig("test")
        condition = cfg.get_ref('value') == 1
        
        result = condition.evaluate(none_policy='propagate')
        assert result is None

    def test_or_none_true_returns_true(self):
        """Test that OR(None, True) = True under propagate policy."""
        
        class TestConfig(Config):
            x: int | None = None
            y: int = 2
        
        cfg = TestConfig("test")
        # x == 1 is None (x is None), y == 2 is True
        condition = (cfg.get_ref('x') == 1).logical_or(cfg.get_ref('y') == 2)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is True

    def test_or_none_false_returns_none(self):
        """Test that OR(None, False) = None under propagate policy."""
        
        class TestConfig(Config):
            x: int | None = None
            y: int = 2
        
        cfg = TestConfig("test")
        # x == 1 is None (x is None), y == 3 is False
        condition = (cfg.get_ref('x') == 1).logical_or(cfg.get_ref('y') == 3)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is None

    def test_and_none_false_returns_false(self):
        """Test that AND(None, False) = False under propagate policy."""
        
        class TestConfig(Config):
            x: int | None = None
            y: int = 2
        
        cfg = TestConfig("test")
        # x == 1 is None (x is None), y == 3 is False
        condition = (cfg.get_ref('x') == 1).logical_and(cfg.get_ref('y') == 3)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is False

    def test_and_none_true_returns_none(self):
        """Test that AND(None, True) = None under propagate policy."""
        
        class TestConfig(Config):
            x: int | None = None
            y: int = 2
        
        cfg = TestConfig("test")
        # x == 1 is None (x is None), y == 2 is True
        condition = (cfg.get_ref('x') == 1).logical_and(cfg.get_ref('y') == 2)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is None

    def test_not_none_returns_none(self):
        """Test that NOT(None) = None under propagate policy."""
        
        class TestConfig(Config):
            x: int | None = None
        
        cfg = TestConfig("test")
        # x == 1 is None (x is None)
        condition = (cfg.get_ref('x') == 1).logical_not()
        
        result = condition.evaluate(none_policy='propagate')
        assert result is None

    def test_complex_expression_x_equals_1_or_y_equals_2(self):
        """Test complex expression: x == 1 or y == 2 where x is 1 and y is None should be True."""
        
        class TestConfig(Config):
            x: int = 1
            y: int | None = None
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('x') == 1).logical_or(cfg.get_ref('y') == 2)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is True

    def test_complex_expression_x_equals_1_and_y_equals_2_none(self):
        """Test complex expression: x == 1 and y == 2 where x is 1 and y is None should be None."""
        
        class TestConfig(Config):
            x: int = 1
            y: int | None = None
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('x') == 1).logical_and(cfg.get_ref('y') == 2)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is None

    def test_all_conditions_known_true(self):
        """Test that fully determinable True conditions return True."""
        
        class TestConfig(Config):
            x: int = 1
            y: int = 2
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('x') == 1).logical_and(cfg.get_ref('y') == 2)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is True

    def test_all_conditions_known_false(self):
        """Test that fully determinable False conditions return False."""
        
        class TestConfig(Config):
            x: int = 1
            y: int = 2
        
        cfg = TestConfig("test")
        condition = (cfg.get_ref('x') == 5).logical_or(cfg.get_ref('y') == 10)
        
        result = condition.evaluate(none_policy='propagate')
        assert result is False


class TestWritableFieldConditions:
    """Tests for writable field behavior with different none_policy settings."""

    def test_writable_field_returns_none_with_ignore_policy(self):
        """Test that writable fields return None when none_policy='ignore'."""
        
        class TestConfig(Config):
            # Field with default value but marked as writable (changeable)
            value: int = cfg_field(default=42, write=True)
        
        cfg = TestConfig("test")
        # Even though value is 42, writable fields should be treated as None
        ref = cfg.get_ref('value')
        result = ref.evaluate(none_policy='ignore')
        assert result is None

    def test_writable_field_returns_none_with_propagate_policy(self):
        """Test that writable fields return None when none_policy='propagate'."""
        
        class TestConfig(Config):
            value: int = cfg_field(default=42, write=True)
        
        cfg = TestConfig("test")
        ref = cfg.get_ref('value')
        result = ref.evaluate(none_policy='propagate')
        assert result is None

    def test_writable_field_returns_actual_value_with_fail_policy(self):
        """Test that writable fields return actual value when none_policy='fail'."""
        
        class TestConfig(Config):
            value: int = cfg_field(default=42, write=True)
        
        cfg = TestConfig("test")
        ref = cfg.get_ref('value')
        result = ref.evaluate(none_policy='fail')
        assert result == 42

    def test_writable_field_condition_propagates_none(self):
        """Test that conditions with writable fields propagate None correctly."""
        
        class TestConfig(Config):
            writable_value: int = cfg_field(default=10, write=True)
            fixed_value: int = 20
        
        cfg = TestConfig("test")
        
        # With propagate policy, writable field should cause condition to be None
        condition = cfg.get_ref('writable_value') == 10
        assert condition.evaluate(none_policy='propagate') is None
        
        # Mixed condition: writable AND fixed
        # AND(None, True) = None
        condition2 = (cfg.get_ref('writable_value') == 10).logical_and(cfg.get_ref('fixed_value') == 20)
        assert condition2.evaluate(none_policy='propagate') is None
        
        # Mixed condition: writable OR fixed
        # OR(None, True) = True
        condition3 = (cfg.get_ref('writable_value') == 10).logical_or(cfg.get_ref('fixed_value') == 20)
        assert condition3.evaluate(none_policy='propagate') is True

    def test_non_writable_field_returns_actual_value(self):
        """Test that non-writable fields always return their actual value."""
        
        class TestConfig(Config):
            value: int = cfg_field(default=42, write=False)
        
        cfg = TestConfig("test")
        ref = cfg.get_ref('value')
        
        # Non-writable fields should return actual value regardless of policy
        assert ref.evaluate(none_policy='fail') == 42
        assert ref.evaluate(none_policy='ignore') == 42
        assert ref.evaluate(none_policy='propagate') == 42


class TestExpressionRegistry:
    """Tests for ExpressionRegistry functionality."""
    
    def test_registry_register_and_get(self):
        """Test registering and retrieving expressions."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        expr = cfg.get_ref("value") > 5
        
        # Manually set name and register
        expr.set_name("test_expr", "/test/file.py")
        
        # Should be retrievable
        retrieved = ExpressionRegistry.get("/test/file.py", "test_expr")
        assert retrieved is expr
    
    def test_registry_clear(self):
        """Test clearing the registry."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        expr = cfg.get_ref("value") == 10
        expr.set_name("expr1", "/file1.py")
        
        # Registry should have entries
        assert len(ExpressionRegistry.get_all()) > 0
        
        # Clear and verify
        ExpressionRegistry.clear()
        assert len(ExpressionRegistry.get_all()) == 0
    
    def test_registry_get_by_file(self):
        """Test getting all expressions from a specific file."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        
        # Create multiple expressions in different files
        expr1 = cfg.get_ref("value") > 5
        expr1.set_name("expr1", "/file1.py")
        
        expr2 = cfg.get_ref("value") < 20
        expr2.set_name("expr2", "/file1.py")
        
        expr3 = cfg.get_ref("value") == 10
        expr3.set_name("expr3", "/file2.py")
        
        # Get expressions from file1
        file1_exprs = ExpressionRegistry.get_by_file("/file1.py")
        assert len(file1_exprs) == 2
        assert "expr1" in file1_exprs
        assert "expr2" in file1_exprs
        assert file1_exprs["expr1"] is expr1
        assert file1_exprs["expr2"] is expr2
        
        # Get expressions from file2
        file2_exprs = ExpressionRegistry.get_by_file("/file2.py")
        assert len(file2_exprs) == 1
        assert "expr3" in file2_exprs
    
    def test_registry_duplicate_registration(self):
        """Test that duplicate registration of the same expression is allowed."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        expr = cfg.get_ref("value") != 0
        
        # Register once
        expr.set_name("dup_expr", "/test.py")
        
        # Re-register same expression - should not raise
        expr.set_name("dup_expr", "/test.py")
        
        # Verify still accessible
        retrieved = ExpressionRegistry.get("/test.py", "dup_expr")
        assert retrieved is expr
    
    def test_registry_conflict_different_expression(self):
        """Test that registering different expression with same name raises error."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        
        # Register first expression
        expr1 = cfg.get_ref("value") > 5
        expr1.set_name("conflict", "/test.py")
        
        # Try to register different expression with same name
        expr2 = cfg.get_ref("value") < 5
        
        with pytest.raises(ValueError, match="already registered"):
            expr2.set_name("conflict", "/test.py")
    
    def test_expression_get_reference(self):
        """Test Expression.get_reference() method."""
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        expr = cfg.get_ref("value") >= 0
        
        # Before naming - no reference
        assert expr.get_reference() is None
        
        # After naming - should return reference
        expr.set_name("my_ref", "/path/to/file.py")
        assert expr.get_reference() == "/path/to/file.py.my_ref"
    
    def test_expression_without_name_raises_on_register(self):
        """Test that registering expression without name raises error."""
        from config_tree.expression import ExpressionRegistry
        
        
        class TestConfig(Config):
            value: int = 10
        
        cfg = TestConfig("test")
        expr = cfg.get_ref("value") <= 100
        
        # Try to register without setting name first
        with pytest.raises(ValueError, match="must have both name and file"):
            ExpressionRegistry.register(expr)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
