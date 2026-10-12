# SPDX-License-Identifier: Apache-2.0

"""Test cfg_field with default_factory parameter."""

from __future__ import annotations

import pytest

from config_tree import Config, cfg_field


class TestCfgFieldDefaultFactory:
    """Tests for cfg_field default_factory parameter."""

    def test_default_factory_list(self):
        """Test default_factory with list."""
        class ListConfig(Config):
            items: list[int] = cfg_field(default_factory=list, desc="List of items")
        
        # Create two instances - they should have separate lists
        config1 = ListConfig("config1")
        config2 = ListConfig("config2")
        
        assert config1.items == []
        assert config2.items == []
        
        # Modify one list - the other should not be affected
        config1.items.append(1)
        assert config1.items == [1]
        assert config2.items == []

    def test_default_factory_dict(self):
        """Test default_factory with dict."""
        class DictConfig(Config):
            mapping: dict[str, int] = cfg_field(default_factory=dict, desc="Mapping")
        
        config1 = DictConfig("config1")
        config2 = DictConfig("config2")
        
        assert config1.mapping == {}
        assert config2.mapping == {}
        
        config1.mapping["key"] = 42
        assert config1.mapping == {"key": 42}
        assert config2.mapping == {}

    def test_default_factory_lambda(self):
        """Test default_factory with lambda."""
        class LambdaConfig(Config):
            values: list[int] = cfg_field(default_factory=lambda: [1, 2, 3], desc="Initial values")
        
        config = LambdaConfig("config")
        assert config.values == [1, 2, 3]
        
        # Modify the list
        config.values.append(4)
        assert config.values == [1, 2, 3, 4]
        
        # Create another instance - should have fresh list
        config2 = LambdaConfig("config2")
        assert config2.values == [1, 2, 3]

    def test_default_factory_with_init_true(self):
        """Test default_factory with init=True (default)."""
        class InitConfig(Config):
            items: list[str] = cfg_field(default_factory=list, desc="Items")
        
        # Should be able to pass items in __init__
        config = InitConfig("config", items=["a", "b"])
        assert config.items == ["a", "b"]
        
        # Without passing, should use factory
        config2 = InitConfig("config2")
        assert config2.items == []

    def test_default_factory_with_init_false(self):
        """Test default_factory with init=False."""
        class NoInitConfig(Config):
            items: list[str] = cfg_field(default_factory=list, init=False, desc="Items")
        
        config = NoInitConfig("config")
        assert config.items == []

    def test_cannot_have_both_default_and_default_factory(self):
        """Test that specifying both default and default_factory raises an error."""
        with pytest.raises(ValueError, match="Cannot specify both default and default_factory"):
            class BadConfig(Config):
                value: int = cfg_field(default=42, default_factory=lambda: 100, desc="Bad field")

    def test_default_factory_with_dump(self):
        """Test that default_factory works with dump=True."""
        class DumpConfig(Config):
            items: list[int] = cfg_field(default_factory=list, read=True, desc="Items to dump")
        
        config = DumpConfig("config")
        config.items.extend([1, 2, 3])
        
        # Should be dumpable
        assert config.items == [1, 2, 3]

    def test_default_factory_with_inlined_dump(self):
        """Test that default_factory works with inlined_dump=True."""
        class InlinedConfig(Config):
            items: list[int] = cfg_field(default_factory=list, inlined_dump=True, desc="Items")
        
        config = InlinedConfig("config")
        config.items.extend([1, 2, 3])
        
        repr_str = repr(config)
        assert "InlinedConfig" in repr_str
        assert "items" in repr_str

    def test_default_factory_callable(self):
        """Test default_factory with a regular function."""
        def create_default_set():
            return {1, 2, 3}
        
        class SetConfig(Config):
            values: set[int] = cfg_field(default_factory=create_default_set, desc="Set of values")
        
        config1 = SetConfig("config1")
        config2 = SetConfig("config2")
        
        assert config1.values == {1, 2, 3}
        assert config2.values == {1, 2, 3}
        
        config1.values.add(4)
        assert config1.values == {1, 2, 3, 4}
        assert config2.values == {1, 2, 3}

    def test_default_factory_complex_object(self):
        """Test default_factory with complex nested structure."""
        class ComplexConfig(Config):
            data: dict[str, list[int]] = cfg_field(
                default_factory=lambda: {"a": [1], "b": [2]},
                desc="Nested structure"
            )
        
        config = ComplexConfig("config")
        assert config.data == {"a": [1], "b": [2]}
        
        config.data["a"].append(10)
        config.data["c"] = [3]
        assert config.data == {"a": [1, 10], "b": [2], "c": [3]}
        
        # New instance should have fresh data
        config2 = ComplexConfig("config2")
        assert config2.data == {"a": [1], "b": [2]}
