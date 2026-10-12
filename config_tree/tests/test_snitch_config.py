# SPDX-License-Identifier: Apache-2.0

"""Tests for Snitch configuration classes."""

import pytest

from tests.test_configs.snitch.memory_config import MemoryConfig
from tests.test_configs.snitch.snitch_core_config import SnitchCoreConfig
from tests.test_configs.snitch.snitch_testbench_config import (
    SnitchTestbenchConfig,
    SnitchTestbenchBoardConfig,
    SnitchTestbenchMultiBoardConfig,
)
from config_tree import Config, MemoryMapped


class TestMemoryConfig:
    """Tests for MemoryConfig class."""

    def test_memory_config_defaults(self):
        """Test MemoryConfig with default values."""
        mem = MemoryConfig('mem')
        assert mem.size == 0
        assert mem.atomics is False
        assert mem.latency == 0

    def test_memory_config_custom(self):
        """Test MemoryConfig with custom values."""
        mem = MemoryConfig('mem', size=0x10_0000, atomics=True, latency=10)
        assert mem.size == 0x10_0000
        assert mem.atomics is True
        assert mem.latency == 10


class TestSnitchCoreConfig:
    """Tests for SnitchCoreConfig class."""

    def test_snitch_core_config_defaults(self):
        """Test SnitchCoreConfig with default values."""
        core = SnitchCoreConfig('core')
        assert core.isa == 'rv32i'
        assert core.nb_outstanding == 4

    def test_snitch_core_config_custom(self):
        """Test SnitchCoreConfig with custom values."""
        core = SnitchCoreConfig('core', isa='rv32imfdca', nb_outstanding=8)
        assert core.isa == 'rv32imfdca'
        assert core.nb_outstanding == 8


class TestSnitchTestbenchConfig:
    """Tests for Snitch testbench configuration classes."""

    def test_snitch_testbench_config_creation(self):
        """Test SnitchTestbenchConfig instantiation and hierarchy."""
        config = SnitchTestbenchConfig('testbench')
        
        # Check default values
        assert config.base_addr == 0x8000_0000
        
        # Check that child configs are created
        assert isinstance(config.core, SnitchCoreConfig)
        assert isinstance(config.mem_l0, MemoryConfig)
        assert isinstance(config.mem_l1, MemoryConfig)
        assert isinstance(config.mem_l2, MemoryConfig)
        
        # Check memory configurations
        assert config.mem_l0.size == 0x10_0000
        assert config.mem_l0.atomics is True
        assert config.mem_l0.latency == 0
        
        assert config.mem_l1.latency == 10
        assert config.mem_l2.latency == 1000

    def test_snitch_testbench_board_config(self):
        """Test SnitchTestbenchBoardConfig."""
        board = SnitchTestbenchBoardConfig('board')
        
        assert board.frequency == 10000000
        assert board.base_addr == 0x8000_0000
        assert isinstance(board.soc, SnitchTestbenchConfig)
        assert board.soc.base_addr == 0x8000_0000

    def test_snitch_testbench_board_config_custom(self):
        """Test SnitchTestbenchBoardConfig with custom values."""
        board = SnitchTestbenchBoardConfig('board', frequency=20000000, base_addr=0x9000_0000)
        
        assert board.frequency == 20000000
        assert board.base_addr == 0x9000_0000
        assert board.soc.base_addr == 0x9000_0000

    def test_snitch_testbench_multi_board_config(self):
        """Test SnitchTestbenchMultiBoardConfig."""
        multi = SnitchTestbenchMultiBoardConfig('multi')
        
        assert multi.nb_boards == 2
        assert len(multi.boards) == 2
        
        # Check that boards are properly created
        for i, board in enumerate(multi.boards):
            assert isinstance(board, SnitchTestbenchBoardConfig)
            assert board.base_addr == 0x8000_0000 + i * 0x3000_0000

    def test_snitch_testbench_multi_board_config_custom(self):
        """Test SnitchTestbenchMultiBoardConfig with custom board count."""
        multi = SnitchTestbenchMultiBoardConfig('multi', nb_boards=4)
        
        assert multi.nb_boards == 4
        assert len(multi.boards) == 4
        
        # Verify base addresses increment correctly
        for i, board in enumerate(multi.boards):
            expected_addr = 0x8000_0000 + i * 0x3000_0000
            assert board.base_addr == expected_addr

    def test_hierarchy_parent_child_relationships(self):
        """Test parent-child relationships in the config hierarchy."""
        board = SnitchTestbenchBoardConfig('board')
        
        # Check parent-child relationships
        assert board.soc.parent is board
        assert board.soc.core.parent is board.soc
        assert board.soc.mem_l0.parent is board.soc
        
    def test_config_path_names(self):
        """Test that configs have correct path names."""
        board = SnitchTestbenchBoardConfig('board')
        
        assert board.soc.name == 'soc'
        assert board.soc.core.name == 'core'
        assert board.soc.mem_l0.name == 'mem_l0'
        assert board.soc.mem_l1.name == 'mem_l1'
        assert board.soc.mem_l2.name == 'mem_l2'


class TestMemoryMappedDiscovery:
    """Tests for MemoryMapped discovery via tree walking."""

    def test_memory_config_base_addresses(self):
        """A MemoryConfig with base set returns it in base_addresses."""
        mem = MemoryConfig('mem', size=0x10_0000, base=0x8000_0000)
        assert mem.base_addresses == [0x8000_0000]

    def test_memory_config_no_base_has_empty_addresses(self):
        """A MemoryConfig with base=0 has empty base_addresses."""
        mem = MemoryConfig('mem', size=0x10_0000)
        assert mem.base_addresses == []

    def test_find_memory_mapped_in_tree(self):
        """MemoryMapped configs can be found by walking the tree."""
        config = SnitchTestbenchConfig('testbench')
        memory_mapped = list(config.find_from(
            fn=lambda c: isinstance(c, MemoryMapped),
            direct_only=False,
        ))
        # Should find the memory configs that mix in MemoryMapped
        assert len(memory_mapped) > 0

    def test_plain_config_base_addresses_empty(self):
        """A plain Config (not MemoryMapped) has empty base_addresses."""
        cfg = Config('plain')
        assert cfg.base_addresses == []
