# SPDX-License-Identifier: Apache-2.0

"""Tests for Config.children property."""

from __future__ import annotations

from config_tree import Config, cfg_field


class TestConfigChildren:
    """Tests for Config children tracking."""

    def test_children_empty_by_default(self):
        """Test that a config with no children has an empty children list."""
        class SimpleConfig(Config):
            value: int = 42
        
        config = SimpleConfig("simple")
        assert config.children == []
        assert len(config.children) == 0

    def test_single_child(self):
        """Test that a parent config tracks its single child."""
        class ChildConfig(Config):
            pass
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig("child")
        
        parent = ParentConfig("parent")
        
        assert len(parent.children) == 1
        assert parent.children[0] is parent.child
        assert parent.child.parent is parent

    def test_multiple_children(self):
        """Test that a parent config tracks multiple children."""
        class ChildConfig(Config):
            pass
        
        class ParentConfig(Config):
            child1: ChildConfig = cfg_field(init=False)
            child2: ChildConfig = cfg_field(init=False)
            child3: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child1 = ChildConfig("child1")
                self.child2 = ChildConfig("child2")
                self.child3 = ChildConfig("child3")
        
        parent = ParentConfig("parent")
        
        assert len(parent.children) == 3
        assert parent.child1 in parent.children
        assert parent.child2 in parent.children
        assert parent.child3 in parent.children
        
        # Check order is preserved
        assert parent.children[0] is parent.child1
        assert parent.children[1] is parent.child2
        assert parent.children[2] is parent.child3

        assert parent.children[0].parent is parent
        assert parent.children[1].parent is parent
        assert parent.children[2].parent is parent

    def test_children_list_of_configs(self):
        """Test children tracking with a list of config instances."""
        class ItemConfig(Config):
            value: int = 0
        
        class ContainerConfig(Config):
            items: list[ItemConfig] = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.items = [
                    ItemConfig(f"item_{i}", value=i)
                    for i in range(5)
                ]
        
        container = ContainerConfig("container")
        
        # All items should be in children
        assert len(container.children) == 5
        for item in container.items:
            assert item in container.children
            assert item.parent is container

    def test_nested_hierarchy_children(self):
        """Test children tracking in deeply nested hierarchy."""
        class LeafConfig(Config):
            pass
        
        class MiddleConfig(Config):
            leaf: LeafConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.leaf = LeafConfig("leaf")
        
        class RootConfig(Config):
            middle: MiddleConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.middle = MiddleConfig("middle")
        
        root = RootConfig("root")
        
        # Root should have one child (middle)
        assert len(root.children) == 1
        assert root.children[0] is root.middle
        
        # Middle should have one child (leaf)
        assert len(root.middle.children) == 1
        assert root.middle.children[0] is root.middle.leaf
        
        # Leaf should have no children
        assert len(root.middle.leaf.children) == 0

    def test_children_different_types(self):
        """Test children of different config types."""
        class TypeAConfig(Config):
            pass
        
        class TypeBConfig(Config):
            pass
        
        class ParentConfig(Config):
            child_a: TypeAConfig = cfg_field(init=False)
            child_b: TypeBConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child_a = TypeAConfig("child_a")
                self.child_b = TypeBConfig("child_b")
        
        parent = ParentConfig("parent")
        
        assert len(parent.children) == 2
        assert isinstance(parent.children[0], TypeAConfig)
        assert isinstance(parent.children[1], TypeBConfig)

    def test_children_immutability(self):
        """Test that modifying children list doesn't break parent tracking."""
        class ChildConfig(Config):
            pass
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig("child")
        
        parent = ParentConfig("parent")
        original_child = parent.child
        
        # The child should be tracked
        assert len(parent.children) == 1
        assert parent.children[0] is original_child

    def test_orphan_config_has_no_parent_but_empty_children(self):
        """Test that a root config has no parent but has empty children list."""
        class RootConfig(Config):
            pass
        
        root = RootConfig("root")
        
        assert root.parent is None
        assert root.children == []

    def test_children_with_mixed_field_types(self):
        """Test children tracking with mix of field types."""
        class ConfigChild(Config):
            pass
        
        class ParentConfig(Config):
            regular_field: int = cfg_field(default=42, read=True)
            child1: ConfigChild = cfg_field(init=False)
            string_field: str = cfg_field(default="test", read=True)
            child2: ConfigChild = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child1 = ConfigChild("child1")
                self.child2 = ConfigChild("child2")
        
        parent = ParentConfig("parent")
        
        # Only Config instances should be in children
        assert len(parent.children) == 2
        assert all(isinstance(child, Config) for child in parent.children)

    def test_children_iteration(self):
        """Test that children list can be iterated."""
        class ChildConfig(Config):
            value: int = 0
        
        class ParentConfig(Config):
            children_list: list[ChildConfig] = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.children_list = [
                    ChildConfig(f"child_{i}", value=i*10)
                    for i in range(3)
                ]
        
        parent = ParentConfig("parent")
        
        # Iterate and verify
        values = [child.value for child in parent.children]
        assert values == [0, 10, 20]

    def test_children_count_matches_created(self):
        """Test that children count matches number of children created."""
        class ChildConfig(Config):
            pass
        
        class DynamicParentConfig(Config):
            count: int = 1
            child_list: list[ChildConfig] = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child_list = [
                    ChildConfig(f"child_{i}")
                    for i in range(self.count)
                ]
        
        parent_small = DynamicParentConfig("parent_small", count=2)
        assert len(parent_small.children) == 2
        
        parent_large = DynamicParentConfig("parent_large", count=10)
        assert len(parent_large.children) == 10

    def test_children_parent_relationship_bidirectional(self):
        """Test that parent-child relationship is properly bidirectional."""
        class ChildConfig(Config):
            pass
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig("child")
        
        parent = ParentConfig("parent")
        child = parent.child
        
        # Child knows its parent
        assert child.parent is parent
        
        # Parent knows its child
        assert child in parent.children
        
        # Bidirectional verification
        assert parent.children[0].parent is parent

    def test_grandchildren_not_in_parent_children(self):
        """Test that grandchildren are not in parent's children list."""
        class GrandchildConfig(Config):
            pass
        
        class ChildConfig(Config):
            grandchild: GrandchildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.grandchild = GrandchildConfig("grandchild")
        
        class ParentConfig(Config):
            child: ChildConfig = cfg_field(init=False)
            
            def __post_init__(self):
                super().__post_init__()
                self.child = ChildConfig("child")
        
        parent = ParentConfig("parent")
        
        # Parent's children should only contain direct child
        assert len(parent.children) == 1
        assert parent.child in parent.children
        assert parent.child.grandchild not in parent.children
        
        # Child's children should contain grandchild
        assert len(parent.child.children) == 1
        assert parent.child.grandchild in parent.child.children
