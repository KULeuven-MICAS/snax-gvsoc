"""
Pytest tests for Config class and related functionality.

Tests cover:
- Basic Config creation and initialization
- Hierarchical configurations with parent-child relationships
- Command-line attribute overrides via override_fields()
- Type casting for various types (primitives, collections, enums)
- Field metadata (description, format, dump options)
- Hex formatting with grouping
- Path computation and registry
"""

import pytest
from dataclasses import dataclass, field
from enum import Enum
from config_tree.fields import cfg_field
from config_tree import Config
from config_tree.dump import build_config_tree
from config_tree.field_type_alias import cast_to_type
from config_tree.utils import hex_grouped, parse_bool


class TestBasicConfigCreation:
    """Tests for basic Config object creation and initialization."""

    def test_simple_config_creation(self):
        """Test creating a simple Config without any fields."""
        class SimpleConfig(Config):
            pass
        
        config = SimpleConfig('simple')
        assert config.path == 'simple'
        assert config.parent is None
        assert config.name == 'simple'

    def test_config_with_name(self):
        """Test creating a Config with a name."""
        class NamedConfig(Config):
            pass
        
        config = NamedConfig('test_config')
        assert config.name == 'test_config'
        assert config.path == 'test_config'

    def test_config_with_simple_fields(self):
        """Test Config with basic field types."""
        class BasicFieldConfig(Config):
            value: int = 42
            name_field: str = "default"
            enabled: bool = True
        
        config = BasicFieldConfig('basic')
        assert config.value == 42
        assert config.name_field == "default"
        assert config.enabled is True

    def test_config_with_cfg_field(self):
        """Test Config using cfg_field for field definitions."""
        class CfgFieldConfig(Config):
            size: int = cfg_field(
                default=0x1000,
                desc="Memory size in bytes",
                fmt="hex",
                read=True
            )
            enabled: bool = cfg_field(
                default=False,
                desc="Enable feature",
                read=True
            )
        
        config = CfgFieldConfig('cfg_test')
        assert config.size == 0x1000
        assert config.enabled is False


class TestHierarchicalConfig:
    """Tests for parent-child Config hierarchies."""

    def test_parent_child_relationship(self):
        """Test Config with parent-child relationship."""
        
        class ChildConfig(Config):
            pass

        class ParentConfig(Config):
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig('child')


        # Create parent without entering context
        parent = ParentConfig('parent')
        assert parent.path == 'parent'
        
        assert parent.child.parent is parent
        assert parent.child.path == 'parent/child'

    def test_nested_config_hierarchy(self):
        """Test deeply nested Config hierarchy."""

        class Level2(Config):
            pass

        class Level1(Config):
            def __post_init__(self):
                super().__post_init__()
                self.level2_0 = Level2('level2_0')
                self.level2_1 = Level2('level2_1')

        class Level0(Config):
            def __post_init__(self):
                super().__post_init__()
                self.level1_0 = Level1('level1_0')
                self.level1_1 = Level1('level1_1')
        
        level0_configs = [Level0(f'level0_{i}') for i in range(2)]
        
        # Verify paths for all levels
        for i, level0 in enumerate(level0_configs):
            assert level0.path == f'level0_{i}'
            
            for j in range(2):
                level1 = getattr(level0, f'level1_{j}')
                assert level1.path == f'level0_{i}/level1_{j}'
                
                for k in range(2):
                    level2 = getattr(level1, f'level2_{k}')
                    assert level2.path == f'level0_{i}/level1_{j}/level2_{k}'

    def test_complex_hierarchical_config(self):
        """Test complex hierarchical config similar to snitch_testbench_config."""
        class MemoryConfig(Config):
            size: int = cfg_field(default=0, fmt="hex", desc="Memory size in bytes")
            atomics: bool = cfg_field(default=False, desc="Support atomic operations")
            latency: int = cfg_field(default=0, desc="Memory latency")
        
        class RouterConfig(Config):
            synchronous: bool = cfg_field(default=False, desc="Synchronous mode")
            bandwidth: int = cfg_field(default=0, desc="Bandwidth in bytes/cycle")
        
        class SystemConfig(Config):
            base_addr: int = cfg_field(default=0x8000_0000, fmt="hex", desc="Base address")
            mem: MemoryConfig = cfg_field(init=False, desc="Memory configuration")
            router: RouterConfig = cfg_field(init=False, desc="Router configuration")
            
            def __post_init__(self):
                super().__post_init__()
                self.mem = MemoryConfig('mem', size=0x10_0000, atomics=True, latency=10)
                self.router = RouterConfig('router', synchronous=True, bandwidth=4)
        
        system = SystemConfig('system')
        assert system.base_addr == 0x8000_0000
        assert system.mem.size == 0x10_0000
        assert system.mem.atomics is True
        assert system.mem.latency == 10
        assert system.mem.path == 'system/mem'
        assert system.router.synchronous is True
        assert system.router.bandwidth == 4
        assert system.router.path == 'system/router'


class TestCommandLineAttributes:
    """Tests for command-line attribute override functionality."""

    def setup_method(self):
        """Clear attribute overrides before each test."""
        import config_tree
        config_tree._Config__attribute_arg_values = {}

    def teardown_method(self):
        """Clear attribute overrides after each test."""
        import config_tree
        config_tree._Config__attribute_arg_values = {}

    def test_override_fields_simple(self):
        """Test setting simple attributes via command line."""
        # Just verify override_fields works by testing with a config
        class SimpleAttrConfig(Config):
            value: int = 42
            name_attr: str = "default"
        
        Config.override_fields(['simple_attr/value=100', 'simple_attr/name_attr=test'])
        config = SimpleAttrConfig('simple_attr')
        assert config.value == 100
        assert config.name_attr == "test"

    def test_attribute_override_int(self):
        """Test overriding integer field from command line."""
        class IntConfig(Config):
            value: int = 42
        
        Config.override_fields(['int_cfg/value=100'])
        config = IntConfig('int_cfg')
        assert config.value == 100

    def test_attribute_override_bool(self):
        """Test overriding boolean field from command line."""
        class BoolConfig(Config):
            enabled: bool = False
        
        Config.override_fields(['bool_cfg/enabled=true'])
        config = BoolConfig('bool_cfg')
        assert config.enabled is True

    def test_attribute_override_hex(self):
        """Test overriding hex value from command line."""
        class HexConfig(Config):
            address: int = 0x1000
        
        Config.override_fields(['hex_cfg/address=0x8000_0000'])
        config = HexConfig('hex_cfg')
        assert config.address == 0x80000000

    def test_attribute_override_nested_path(self):
        """Test overriding nested config attributes."""
        class InnerConfig(Config):
            value: int = 10
        
        class OuterConfig(Config):
            inner: InnerConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.inner = InnerConfig('inner')
        
        Config.override_fields(['outer/inner/value=99'])
        config = OuterConfig('outer')
        assert config.inner.value == 99


class TestDeferredParentInit:
    """Tests for deferred parent initialization."""

    def setup_method(self):
        """Clear registries and attribute overrides before each test."""

    def test_deferred_parent_override_uses_final_path(self):
        """Test that field overrides for deferred configs use the final path after adopt()."""
        from typing import ClassVar

        class ParentConfig(Config):
            pass

        class DeferredChild(Config):
            _defer_parent_init: ClassVar[bool] = True
            value: int = 10

        # Set override for the *final* path (after adoption)
        Config.override_fields(['parent/child/value=42'])

        # Create parent
        parent = ParentConfig('parent')

        # Create deferred child - at this point path is just 'child', not 'parent/child'
        child = DeferredChild('child')
        
        # Value should still be default because override path doesn't match temporary path
        assert child.value == 10
        assert child.path == 'child'
        assert child.parent is None

        # Now adopt into parent - this should trigger the override
        child.adopt(parent)
        
        # After adoption, path is correct and override should have been applied
        assert child.path == 'parent/child'
        assert child.value == 42
        assert child.parent is parent

    def test_deferred_config_not_registered_before_adopt(self):
        """Test that deferred configs are not in registries until adopt() is called."""
        from typing import ClassVar

        class DeferredConfig(Config):
            _defer_parent_init: ClassVar[bool] = True

        child = DeferredConfig('deferred')
        
        # Should not be in registry before adopt
        assert Config.get_config_by_path('deferred') is None
        assert child not in Config.get_configs_by_class()

    def test_adopt_registers_config(self):
        """Test that adopt() properly registers config in all registries."""
        from typing import ClassVar

        class ParentConfig(Config):
            pass

        class DeferredConfig(Config):
            _defer_parent_init: ClassVar[bool] = True

        parent = ParentConfig('parent')
        child = DeferredConfig('child')
        
        child.adopt(parent)
        
        # Should now be in registries
        assert Config.get_config_by_path('parent/child') is child
        assert child in DeferredConfig.get_configs_by_class()
        assert child in parent.children


class TestTypeCasting:
    """Tests for type casting functionality."""

    def test_cast_to_int(self):
        """Test casting strings to integers."""
        assert cast_to_type('42', int) == 42
        assert cast_to_type('-10', int) == -10
        assert cast_to_type('0', int) == 0

    def test_cast_to_hex_int(self):
        """Test casting hex strings to integers."""
        assert cast_to_type('0x100', int) == 256
        assert cast_to_type('0x1000_0000', int) == 268435456
        assert cast_to_type('0xFFFF', int) == 65535

    def test_cast_to_bool(self):
        """Test casting strings to booleans."""
        assert cast_to_type('true', bool) is True
        assert cast_to_type('True', bool) is True
        assert cast_to_type('1', bool) is True
        assert cast_to_type('yes', bool) is True
        assert cast_to_type('false', bool) is False
        assert cast_to_type('False', bool) is False
        assert cast_to_type('0', bool) is False
        assert cast_to_type('no', bool) is False

    def test_cast_to_float(self):
        """Test casting strings to floats."""
        assert cast_to_type('3.14', float) == 3.14
        assert cast_to_type('0.0', float) == 0.0
        assert cast_to_type('-2.5', float) == -2.5

    def test_cast_to_str(self):
        """Test casting values to strings."""
        assert cast_to_type('hello', str) == 'hello'
        assert cast_to_type(42, str) == '42'

    def test_cast_to_list(self):
        """Test casting to list types."""
        result = cast_to_type('[1,2,3]', list[int])
        assert result == [1, 2, 3]
        
        result = cast_to_type('["a","b","c"]', list[str])
        assert result == ["a", "b", "c"]

    def test_cast_to_set(self):
        """Test casting to set types."""
        result = cast_to_type('[1,2,3]', set[int])
        assert result == {1, 2, 3}

    def test_cast_to_tuple(self):
        """Test casting to tuple types."""
        result = cast_to_type('[1,2,3]', tuple[int])
        assert result == (1, 2, 3)

    def test_cast_to_dict(self):
        """Test casting JSON to dict."""
        # Use dict[str, Any] with type arguments
        from typing import Any
        result = cast_to_type('{"key": "value", "num": 42}', dict[str, Any])
        assert result == {"key": "value", "num": 42}

    def test_cast_to_enum(self):
        """Test casting to enum types."""
        class Color(Enum):
            RED = 1
            GREEN = 2
            BLUE = 3
        
        assert cast_to_type('RED', Color) == Color.RED
        assert cast_to_type('1', Color) == Color.RED

    def testparse_bool_variations(self):
        """Test various boolean string representations."""
        # True values
        for val in ['1', 'true', 'True', 'TRUE', 't', 'yes', 'Yes', 'y', 'on']:
            assert parse_bool(val) is True
        
        # False values
        for val in ['0', 'false', 'False', 'FALSE', 'f', 'no', 'No', 'n', 'off']:
            assert parse_bool(val) is False

    def testparse_bool_invalid(self):
        """Test parsing invalid boolean values."""
        with pytest.raises(ValueError):
            parse_bool('invalid')
        
        with pytest.raises(ValueError):
            parse_bool('maybe')


class TestHexFormatting:
    """Tests for hex formatting with grouping."""

    def testhex_grouped_basic(self):
        """Test basic hex grouping."""
        assert hex_grouped(0x12345678) == '0x1234_5678'
        assert hex_grouped(0xABCDEF) == '0xab_cdef'
        assert hex_grouped(0x1000) == '0x1000'

    def testhex_grouped_large_numbers(self):
        """Test hex grouping with large numbers."""
        assert hex_grouped(0x123456789ABCDEF) == '0x123_4567_89ab_cdef'
        assert hex_grouped(0x80000000) == '0x8000_0000'

    def testhex_grouped_small_numbers(self):
        """Test hex grouping with small numbers."""
        assert hex_grouped(0x0) == '0x0'
        assert hex_grouped(0xF) == '0xf'
        assert hex_grouped(0xFF) == '0xff'

    def testhex_grouped_custom_group_size(self):
        """Test hex grouping with custom group size."""
        assert hex_grouped(0xABCDEF, group=2) == '0xab_cd_ef'
        assert hex_grouped(0x12345678, group=3) == '0x12_345_678'


class TestConfigRepr:
    """Tests for Config __repr__ functionality."""

    def test_repr_with_inlined_dump(self):
        """Test repr showing fields marked for inlined dump."""
        class ReprConfig(Config):
            visible: int = cfg_field(default=42, inlined_dump=True)
            hidden: int = field(default=100, repr=False)  # Use field with repr=False
        
        config = ReprConfig('repr_test')
        repr_str = repr(config)
        assert 'visible=42' in repr_str
        assert 'hidden' not in repr_str

    def test_repr_with_hex_format(self):
        """Test repr with hex formatting."""
        class HexReprConfig(Config):
            address: int = cfg_field(default=0x80000000, fmt="hex", inlined_dump=True)
        
        config = HexReprConfig('hex_repr')
        repr_str = repr(config)
        assert '0x8000_0000' in repr_str


class TestRealWorldScenarios:
    """Tests based on real-world config patterns from snitch testbench."""

    def setup_method(self):
        """Clear attribute overrides and registry before each test."""
        import config_tree
        config_tree._Config__attribute_arg_values = {}

    def teardown_method(self):
        """Clear attribute overrides and registry after each test."""
        import config_tree
        config_tree._Config__attribute_arg_values = {}

    def test_memory_config_pattern(self):
        """Test memory configuration pattern from snitch testbench."""
        class MemoryConfig(Config):
            size: int = cfg_field(default=0, fmt="hex", read=True, desc="Memory size in bytes")
            atomics: bool = cfg_field(default=False, read=True, desc="Support atomics")
            latency: int = cfg_field(default=0, read=True, desc="Extra latency")
        
        mem = MemoryConfig('mem_l0', size=0x10_0000, atomics=True, latency=10)
        assert mem.size == 0x10_0000
        assert mem.atomics is True
        assert mem.latency == 10
        assert mem.path == 'mem_l0'

    def test_router_config_pattern(self):
        """Test router configuration pattern from snitch testbench."""
        class RouterConfig(Config):
            synchronous: bool = cfg_field(default=False, read=True, desc="Synchronous mode")
            max_input_pending_size: int = cfg_field(default=0, read=True, desc="FIFO size")
            bandwidth: int = cfg_field(default=0, read=True, desc="Bandwidth in bytes/cycle")
        
        router = RouterConfig('router', synchronous=True, max_input_pending_size=4, bandwidth=8)
        assert router.synchronous is True
        assert router.max_input_pending_size == 4
        assert router.bandwidth == 8

    def test_router_mapping_pattern(self):
        """Test router mapping configuration pattern."""
        class RouterMapping(Config):
            base: int = cfg_field(default=0, read=True, fmt="hex", desc="Base address")
            size: int = cfg_field(default=0, read=True, fmt="hex", desc="Mapping size")
            remove_base: bool = cfg_field(default=True, read=True, desc="Remove base on propagation")
            latency: int = cfg_field(default=0, read=True, desc="Global latency")
        
        mapping = RouterMapping(
            'mem_l0_mapping',
            base=0x8000_0000,
            size=0x10_0000,
            remove_base=True,
            latency=0
        )
        
        assert mapping.base == 0x80000000
        assert mapping.size == 0x100000
        assert mapping.remove_base is True
        assert mapping.latency == 0

    def test_testbench_config_pattern(self):
        """Test full testbench configuration pattern."""
        class MemoryConfig(Config):
            size: int = cfg_field(default=0, fmt="hex", read=True)
            atomics: bool = cfg_field(default=False, read=True)
            latency: int = cfg_field(default=0, read=True)
        
        class RouterConfig(Config):
            synchronous: bool = cfg_field(default=False, read=True)
            bandwidth: int = cfg_field(default=0, read=True)
        
        class TestbenchConfig(Config):
            base_addr: int = cfg_field(default=0x8000_0000, fmt="hex", read=True, inlined_dump=True)
            has_async: bool = cfg_field(default=True, read=True)
            mem_l0: MemoryConfig = cfg_field(init=False)
            mem_l1: MemoryConfig = cfg_field(init=False)
            router_sync: RouterConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.mem_l0 = MemoryConfig('mem_l0', size=0x10_0000, atomics=True, latency=0)
                self.mem_l1 = MemoryConfig('mem_l1', size=0x10_0000, atomics=True, latency=10)
                self.router_sync = RouterConfig('router_sync', synchronous=True)
        
        config = TestbenchConfig('testbench')
        assert config.base_addr == 0x80000000
        assert config.has_async is True
        assert config.mem_l0.size == 0x100000
        assert config.mem_l0.atomics is True
        assert config.mem_l0.path == 'testbench/mem_l0'
        assert config.mem_l1.latency == 10
        assert config.mem_l1.path == 'testbench/mem_l1'
        assert config.router_sync.synchronous is True
        assert config.router_sync.path == 'testbench/router_sync'

    def test_multi_level_config_with_overrides(self):
        """Test multi-level config with command-line overrides."""
        class LeafConfig(Config):
            value: int = 100
        
        class BranchConfig(Config):
            leaf: LeafConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.leaf = LeafConfig('leaf')
        
        class RootConfig(Config):
            branch: BranchConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.branch = BranchConfig('branch')
        
        # Set override before creating config
        Config.override_fields(['root/branch/leaf/value=999'])
        config = RootConfig('root')
        
        assert config.branch.leaf.value == 999
        assert config.branch.leaf.path == 'root/branch/leaf'


class TestConfigRetrieval:
    """Tests for Config retrieval methods."""

    def test_get_configs_by_class_single(self):
        """Test retrieving configs by class with single instance."""
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test')
        configs = MyConfig.get_configs_by_class()
        
        assert len(configs) == 1
        assert cfg in configs

    def test_get_configs_by_class_multiple(self):
        """Test retrieving configs by class with multiple instances."""
        class MyConfig(Config):
            value: int = 1
        
        cfg1 = MyConfig('test1', value=10)
        cfg2 = MyConfig('test2', value=20)
        cfg3 = MyConfig('test3', value=30)
        
        configs = MyConfig.get_configs_by_class()
        
        assert len(configs) == 3
        assert cfg1 in configs
        assert cfg2 in configs
        assert cfg3 in configs

    def test_get_configs_by_class_different_classes(self):
        """Test that get_configs_by_class only returns instances of the specific class."""
        class ConfigA(Config):
            value: int = 1
        
        class ConfigB(Config):
            value: int = 2
        
        a1 = ConfigA('a1')
        a2 = ConfigA('a2')
        b1 = ConfigB('b1')
        
        configs_a = ConfigA.get_configs_by_class()
        configs_b = ConfigB.get_configs_by_class()
        
        assert len(configs_a) == 2
        assert len(configs_b) == 1
        assert a1 in configs_a
        assert a2 in configs_a
        assert b1 not in configs_a
        assert b1 in configs_b

    def test_get_configs_by_class_empty(self):
        """Test get_configs_by_class with no instances."""
        class EmptyConfig(Config):
            value: int = 1
        
        configs = EmptyConfig.get_configs_by_class()
        assert len(configs) == 0
        assert isinstance(configs, set)

    def test_get_config_by_path_exact_match(self):
        """Test retrieving a config by exact path."""
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test_config', value=42)
        
        retrieved = Config.get_config_by_path('test_config')
        assert retrieved is cfg
        assert retrieved.value == 42

    def test_get_config_by_path_hierarchical(self):
        """Test retrieving a config by hierarchical path."""
        class ChildConfig(Config):
            value: int = 1
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig('child', value=100)
        
        parent = ParentConfig('parent')
        
        retrieved_parent = Config.get_config_by_path('parent')
        retrieved_child = Config.get_config_by_path('parent/child')
        
        assert retrieved_parent is parent
        assert retrieved_child is parent.child
        assert retrieved_child.value == 100

    def test_get_config_by_path_not_found(self):
        """Test get_config_by_path returns None for non-existent path."""
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('exists')
        
        retrieved = Config.get_config_by_path('does_not_exist')
        assert retrieved is None

    def test_get_configs_by_path_wildcard_simple(self):
        """Test get_configs_by_path with simple wildcard."""
        class MyConfig(Config):
            value: int = 1
        
        cfg1 = MyConfig('test1')
        cfg2 = MyConfig('test2')
        cfg3 = MyConfig('other')
        
        configs = Config.get_configs_by_path('test*')
        
        assert len(configs) == 2
        assert cfg1 in configs
        assert cfg2 in configs
        assert cfg3 not in configs

    def test_get_configs_by_path_wildcard_middle(self):
        """Test get_configs_by_path with wildcard in the middle."""
        class MyConfig(Config):
            value: int = 1
        
        class ParentConfig(Config):
            child: MyConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = MyConfig('child')
        
        p1 = ParentConfig('parent1')
        p2 = ParentConfig('parent2')
        standalone = MyConfig('standalone')
        
        # Match parent*/child
        configs = Config.get_configs_by_path('parent*/child')
        
        assert len(configs) == 2
        assert p1.child in configs
        assert p2.child in configs
        assert standalone not in configs

    def test_get_configs_by_path_question_mark(self):
        """Test get_configs_by_path with ? wildcard (single character)."""
        class MyConfig(Config):
            value: int = 1
        
        cfg1 = MyConfig('test1')
        cfg2 = MyConfig('test2')
        cfg3 = MyConfig('test10')
        
        configs = Config.get_configs_by_path('test?')
        
        assert len(configs) == 2
        assert cfg1 in configs
        assert cfg2 in configs
        assert cfg3 not in configs

    def test_get_configs_by_path_char_range(self):
        """Test get_configs_by_path with character range."""
        class MyConfig(Config):
            value: int = 1
        
        cfga = MyConfig('testa')
        cfgb = MyConfig('testb')
        cfgz = MyConfig('testz')
        
        configs = Config.get_configs_by_path('test[ab]')
        
        assert len(configs) == 2
        assert cfga in configs
        assert cfgb in configs
        assert cfgz not in configs

    def test_get_configs_by_path_hierarchical_wildcard(self):
        """Test get_configs_by_path with hierarchical paths and wildcards."""
        class GrandchildConfig(Config):
            value: int = 1
        
        class ChildConfig(Config):
            grandchild: GrandchildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.grandchild = GrandchildConfig('grandchild')
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig('child')
        
        p1 = ParentConfig('root1')
        p2 = ParentConfig('root2')
        
        # Match all grandchildren
        configs = Config.get_configs_by_path('*/child/grandchild')
        
        assert len(configs) == 2
        assert p1.child.grandchild in configs
        assert p2.child.grandchild in configs

    def test_get_configs_by_path_match_all(self):
        """Test get_configs_by_path with * to match everything."""
        class MyConfig(Config):
            value: int = 1
        
        cfg1 = MyConfig('test1')
        cfg2 = MyConfig('test2')
        cfg3 = MyConfig('other')
        
        configs = Config.get_configs_by_path('*')
        
        assert len(configs) >= 3  # At least our configs
        assert cfg1 in configs
        assert cfg2 in configs
        assert cfg3 in configs

    def test_get_configs_by_path_no_match(self):
        """Test get_configs_by_path returns empty set when no matches."""
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test')
        
        configs = Config.get_configs_by_path('nonexistent*')
        
        assert len(configs) == 0
        assert isinstance(configs, set)

    def test_get_configs_by_path_exact_no_wildcard(self):
        """Test get_configs_by_path with exact match (no wildcard)."""
        class MyConfig(Config):
            value: int = 1
        
        cfg1 = MyConfig('exact_match')
        cfg2 = MyConfig('other')
        
        configs = Config.get_configs_by_path('exact_match')
        
        assert len(configs) == 1
        assert cfg1 in configs
        assert cfg2 not in configs


class TestConfigLabel:
    """Tests for Config label functionality."""

    def test_config_with_label(self):
        """Test creating a config with a label."""
        
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test', label='my_label')
        
        assert cfg.label == 'my_label'

    def test_config_without_label(self):
        """Test that label defaults to None."""
        
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test')
        
        assert cfg.label is None

    def test_get_config_by_label(self):
        """Test retrieving config by label."""
        
        class MyConfig(Config):
            value: int = 1
        
        cfg = MyConfig('test', label='unique_label')
        
        found = Config.get_config_by_label('unique_label')
        
        assert found is cfg

    def test_get_config_by_label_not_found(self):
        """Test that get_config_by_label returns None for non-existent label."""
        
        class MyConfig(Config):
            value: int = 1
        
        MyConfig('test', label='some_label')
        
        found = Config.get_config_by_label('nonexistent')
        
        assert found is None

    def test_duplicate_label_raises_error(self):
        """Test that duplicate labels raise ValueError."""
        
        class MyConfig(Config):
            value: int = 1
        
        MyConfig('test1', label='duplicate')
        
        with pytest.raises(ValueError, match="Duplicate configuration label: duplicate"):
            MyConfig('test2', label='duplicate')

    def test_same_label_different_classes_raises_error(self):
        """Test that duplicate labels raise error even across different classes."""
        
        class ConfigA(Config):
            a: int = 1
        
        class ConfigB(Config):
            b: int = 2
        
        ConfigA('a', label='shared')
        
        with pytest.raises(ValueError, match="Duplicate configuration label: shared"):
            ConfigB('b', label='shared')

    def test_label_reset_clears_registry(self):
        """Test that reset clears the label registry."""
        
        class MyConfig(Config):
            value: int = 1
        
        MyConfig('test', label='my_label')
        assert Config.get_config_by_label('my_label') is not None
        
        Config.reset()  # Test that reset clears label registry
        
        assert Config.get_config_by_label('my_label') is None
        # Can reuse label after reset
        cfg2 = MyConfig('test2', label='my_label')
        assert Config.get_config_by_label('my_label') is cfg2

    def test_deferred_config_label(self):
        """Test that labels work with deferred parent init."""
        
        class ParentConfig(Config):
            pass
        
        class ChildConfig(Config):
            _defer_parent_init = True
            value: int = 1
        
        parent = ParentConfig('parent')
        child = ChildConfig('child', label='deferred_label')
        child.adopt(parent)
        
        found = Config.get_config_by_label('deferred_label')
        assert found is child


class TestFieldFlagsFromRef:
    """Tests for _field_flags and read visibility tracking via get_ref()."""

    def test_set_field_rw_instance_updates_only_instance(self):
        class CfgSetA(Config):
            x: int = cfg_field(default=1)
        cfg1 = CfgSetA('s1')
        cfg2 = CfgSetA('s2')
        cfg1.set_field_rw('x', read=True, write=True)
        assert cfg1._field_flags['x']['read'] is True
        assert cfg1._field_flags['x']['write'] is True
        assert cfg2._field_flags['x']['read'] is False
        assert cfg2._field_flags['x']['write'] is False

    def test_set_field_rw_class_updates_class_and_instances(self):
        class CfgSetB(Config):
            x: int = cfg_field(default=1)
        cfg1 = CfgSetB('s1')
        cfg2 = CfgSetB('s2')
        CfgSetB.set_field_rw('x', read=True, write=True)
        assert CfgSetB._class_field_flags['x']['read'] is True
        assert CfgSetB._class_field_flags['x']['write'] is True
        assert cfg1._field_flags['x']['read'] is True
        assert cfg1._field_flags['x']['write'] is True
        assert cfg2._field_flags['x']['read'] is True
        assert cfg2._field_flags['x']['write'] is True

    def test_set_field_rw_requires_at_least_one_flag(self):
        class CfgSetC(Config):
            x: int = cfg_field(default=1)
        cfg = CfgSetC('s')
        with pytest.raises(ValueError, match="At least one"):
            cfg.set_field_rw('x')

    def test_field_flags_initialised_from_metadata(self):
        class CfgA(Config):
            x: int = cfg_field(default=1, read=True)
            y: int = cfg_field(default=2)
        cfg = CfgA('a')
        assert cfg._field_flags['x']['read'] is True
        assert cfg._field_flags['y']['read'] is False

    def test_instance_get_ref_sets_read_on_instance_only(self):
        class CfgB(Config):
            x: int = cfg_field(default=1)
        cfg1 = CfgB('b1')
        cfg2 = CfgB('b2')
        cfg1.get_ref('x')
        assert cfg1._field_flags['x']['read'] is True
        assert cfg2._field_flags['x']['read'] is False

    def test_instance_get_ref_does_not_affect_class_flags(self):
        class CfgC(Config):
            x: int = cfg_field(default=1)
        cfg = CfgC('c')
        cfg.get_ref('x')
        assert CfgC._class_field_flags['x']['read'] is False

    def test_class_get_ref_sets_read_on_class_and_existing_instances(self):
        class CfgD(Config):
            x: int = cfg_field(default=1)
        cfg1 = CfgD('d1')
        cfg2 = CfgD('d2')
        CfgD.get_ref('x')
        assert CfgD._class_field_flags['x']['read'] is True
        assert cfg1._field_flags['x']['read'] is True
        assert cfg2._field_flags['x']['read'] is True

    def test_class_get_ref_affects_future_instances(self):
        class CfgE(Config):
            x: int = cfg_field(default=1)
        CfgE.get_ref('x')
        cfg_new = CfgE('e_new')
        assert cfg_new._field_flags['x']['read'] is True

    def test_refs_proxy_sets_read(self):
        class CfgF(Config):
            x: int = cfg_field(default=42)
        cfg = CfgF('f')
        _ = cfg.refs.x
        assert cfg._field_flags['x']['read'] is True

    def test_reset_restores_class_field_flags(self):
        class CfgG(Config):
            x: int = cfg_field(default=1)
        CfgG.get_ref('x')
        assert CfgG._class_field_flags['x']['read'] is True
        Config.reset()
        assert CfgG._class_field_flags['x']['read'] is False

    def test_build_config_tree_shows_field_after_instance_get_ref(self):
        from io import StringIO
        from rich.console import Console
        class CfgH(Config):
            x: int = cfg_field(default=7)
        cfg = CfgH('h')
        buf = StringIO()
        Console(file=buf, no_color=True).print(build_config_tree(cfg))
        assert 'x' not in buf.getvalue()
        cfg.get_ref('x')
        buf2 = StringIO()
        Console(file=buf2, no_color=True).print(build_config_tree(cfg))
        assert 'x' in buf2.getvalue()

    def test_build_config_tree_hides_unreffed_field(self):
        from io import StringIO
        from rich.console import Console
        class CfgI(Config):
            visible: int = cfg_field(default=1, read=True)
            hidden: int = cfg_field(default=2)
        cfg = CfgI('i')
        buf = StringIO()
        Console(file=buf, no_color=True).print(build_config_tree(cfg))
        rendered = buf.getvalue()
        assert 'visible' in rendered
        assert 'hidden' not in rendered

    def test_build_config_tree_dump_as_table(self):
        """Children with dump_as_table=True render as a table, not tree nodes."""
        from io import StringIO
        from rich.console import Console

        class IrqEntry(Config):
            dump_as_table = True
            irq_num: int = cfg_field(default=0, read=True)

        class IrqParent(Config):
            def __post_init__(self):
                super().__post_init__()
                self.a = IrqEntry("a", irq_num=10)
                self.b = IrqEntry("b", irq_num=20)

        parent = IrqParent("parent")
        buf = StringIO()
        Console(file=buf, no_color=True).print(build_config_tree(parent))
        rendered = buf.getvalue()
        # Both children should appear as rows in a table
        assert 'IrqEntry' in rendered
        assert '2 items' in rendered
        assert 'a' in rendered
        assert 'b' in rendered
        assert '10' in rendered
        assert '20' in rendered

    def test_dump_as_table_false_remains_tree(self):
        """Children without dump_as_table remain as tree nodes."""
        from io import StringIO
        from rich.console import Console

        class TreeChild(Config):
            val: int = cfg_field(default=5, read=True)

        class TreeParent(Config):
            def __post_init__(self):
                super().__post_init__()
                self.child = TreeChild("child", val=5)

        parent = TreeParent("parent")
        buf = StringIO()
        Console(file=buf, no_color=True).print(build_config_tree(parent))
        rendered = buf.getvalue()
        # Should appear as a tree node, not a table
        assert 'TreeChild' in rendered
        assert 'items' not in rendered


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
