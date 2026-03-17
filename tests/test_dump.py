# SPDX-License-Identifier: Apache-2.0

"""Test the config dump functionality."""

import pytest
from io import StringIO

from config_tree import Config, cfg_field, HexInt
from rich.console import Console


class TestConfigDump:
    """Tests for Config.dump() method."""

    def test_simple_config_dump(self):
        """Test dumping a simple config with basic fields."""
        class SimpleConfig(Config):
            value: int = cfg_field(default=42, read=True, desc="Test value")
            name_field: str = cfg_field(default="test", read=True, desc="Name field")
        
        config = SimpleConfig("simple")
        
        # Capture output
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console)
        output = string_io.getvalue()
        
        # Verify output contains expected elements
        assert "SimpleConfig" in output
        assert "simple" in output
        assert "value" in output
        assert "42" in output
        assert "Test value" in output

    def test_hex_field_dump(self):
        """Test that hex fields are formatted correctly."""
        class HexConfig(Config):
            base_addr: HexInt = cfg_field(default=0x80000000, read=True, desc="Base address")
            size: int = cfg_field(default=0x10000, read=True, fmt="hex", desc="Size")
        
        config = HexConfig("hex_config")
        
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console)
        output = string_io.getvalue()
        
        # Should contain hex formatted values
        assert "0x" in output
        assert "base_addr" in output
        assert "size" in output

    def test_hierarchical_config_dump(self):
        """Test dumping a hierarchical config structure."""
        class ChildConfig(Config):
            value: int = cfg_field(default=100, read=True, desc="Child value")
        
        class ParentConfig(Config):
            frequency: int = cfg_field(default=1000000, read=True, desc="Frequency")
            child: ChildConfig = cfg_field(init=False, desc="Child config")
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig("child")
        
        parent = ParentConfig("parent")
        
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        parent.dump(console=console)
        output = string_io.getvalue()
        
        # Should contain both parent and child
        assert "ParentConfig" in output
        assert "ChildConfig" in output
        assert "frequency" in output
        assert "value" in output

    def test_dump_with_show_all(self):
        """Test that show_all parameter shows fields without dump=True."""
        class TestConfig(Config):
            dumped: int = cfg_field(default=1, read=True, desc="Dumped field")
            not_dumped: int = cfg_field(default=2, read=False, desc="Not dumped field")
        
        config = TestConfig("test")
        
        # Without show_all
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console, show_all=False)
        output = string_io.getvalue()
        
        assert "dumped" in output
        assert "not_dumped" not in output
        
        # With show_all
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console, show_all=True)
        output = string_io.getvalue()
        
        assert "dumped" in output
        assert "not_dumped" in output

    def test_dump_with_list_of_configs(self):
        """Test dumping a config with a list of child configs."""
        class ItemConfig(Config):
            item_value: int = cfg_field(default=0, read=True, desc="Item value")
        
        class ContainerConfig(Config):
            items: list[ItemConfig] = cfg_field(init=False, desc="List of items")
            
            def __post_init__(self):
                super().__post_init__()
                self.items = [
                    ItemConfig(f"item_{i}", item_value=i*10)
                    for i in range(3)
                ]
        
        container = ContainerConfig("container")
        
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        container.dump(console=console)
        output = string_io.getvalue()
        
        # Should show all items
        assert "ContainerConfig" in output
        assert "ItemConfig" in output
        assert "item_0" in output
        assert "item_1" in output
        assert "item_2" in output

    def test_dump_bool_values(self):
        """Test that boolean values are formatted with colors."""
        class BoolConfig(Config):
            enabled: bool = cfg_field(default=True, read=True, desc="Enabled flag")
            disabled: bool = cfg_field(default=False, read=True, desc="Disabled flag")
        
        config = BoolConfig("bool_config")
        
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console)
        output = string_io.getvalue()
        
        # Should format booleans
        assert "enabled" in output
        assert "disabled" in output

    def test_dump_complex_types(self):
        """Test dumping configs with lists, tuples, sets, and dicts."""
        class ComplexConfig(Config):
            my_list: list[int] = cfg_field(default_factory=lambda: [1, 2, 3], read=True, desc="A list")
            my_tuple: tuple[str, ...] = cfg_field(default=("a", "b"), read=True, desc="A tuple")
            my_dict: dict[str, int] = cfg_field(default_factory=lambda: {"key": 42}, read=True, desc="A dict")
        
        config = ComplexConfig("complex")
        
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console)
        output = string_io.getvalue()
        
        assert "ComplexConfig" in output
        assert "my_list" in output
        assert "my_tuple" in output
        assert "my_dict" in output

    def test_dump_field_row_override_controls_fields_and_formatting(self):
        """Test that subclasses can fully control dumped rows via dump_field_row."""
        class CustomDumpConfig(Config):
            visible: int = cfg_field(default=7, read=False, desc="Visible via custom row")
            hidden: int = cfg_field(default=9, read=True, desc="Hidden via custom row")

            @classmethod
            def dump_columns(cls) -> list[tuple[str, str]]:
                return [
                    ("Custom Field", "green"),
                    ("Custom Value", "cyan"),
                ]

            def dump_field_row(self, f, show_all: bool, type_hints: dict) -> tuple[str, ...] | None:
                if f.name == "visible":
                    return ("ONLY_VISIBLE", f"<{getattr(self, f.name)}>")
                return None

        config = CustomDumpConfig("custom")

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        config.dump(console=console, show_all=False)
        output = string_io.getvalue()

        assert "ONLY_VISIBLE" in output
        assert "<7>" in output
        assert "hidden" not in output
        assert "Custom Field" in output
        assert "Custom Value" in output
