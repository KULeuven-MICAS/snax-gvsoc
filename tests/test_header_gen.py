"""Tests for header_gen: C memory-map header generation from Config tree."""

import sys
import os
import textwrap

import pytest

from config_tree import Config, cfg_field, HasSize, MemoryMapped, MemoryMappedDevice


# ---------------------------------------------------------------------------
# Minimal MemoryMapped configs for unit testing
# ---------------------------------------------------------------------------

class MiniMemory(MemoryMappedDevice):
    pass


class MiniPeripheral(MemoryMappedDevice):
    """A peripheral with address and size."""
    pass


class MiniRouter(MemoryMapped, Config):
    """A bus/router node that is itself MemoryMapped and contains children."""
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def soc_tree():
    """Build a minimal SoC config tree mirroring the GAP9 structure.

    Uses Config.set_current_parent() to establish proper parent-child
    relationships for MemoryMapped tree walking.
    """
    target = Config('target')
    with Config.set_current_parent(target):
        soc_axi = MiniRouter('soc_axi', base=0x1A00_0000, size=0x0600_0000)
        with Config.set_current_parent(soc_axi):
            l2_shared = MiniMemory('l2_shared', base=0x1C00_0000, size=0x19_0000)
            apb = MiniRouter(
                'soc_peripherals', base=0x1A10_0000, size=0x0100_0000, label='SOC',
            )
            with Config.set_current_parent(apb):
                fc_itc = MiniPeripheral('fc_itc', base=0x1A10_9000, size=0x1000)
                timer0 = MiniPeripheral('timer0', base=0x1A10_B000, size=0x0800)
                timer1 = MiniPeripheral('timer1', base=0x1A10_B800, size=0x0800)

    return target


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHeaderGen:

    def test_generates_pragma_once(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        assert '#pragma once' in output

    def test_top_level_base_defines(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # soc_axi children at top level get BASE defines
        assert '#define SOC_AXI_L2_SHARED_BASE' in output
        assert '0x1c000000' in output

    def test_size_defines(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        assert '#define SOC_AXI_L2_SHARED_SIZE' in output
        assert '0x00190000' in output

    def test_sub_router_offsets(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # apb (label='SOC') children should have OFFSET defines
        assert '#define SOC_FC_ITC_OFFSET' in output
        assert '0x00009000' in output
        assert '#define SOC_TIMER0_OFFSET' in output
        assert '0x0000b000' in output
        assert '#define SOC_TIMER1_OFFSET' in output
        assert '0x0000b800' in output

    def test_sub_router_base_expressions(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # Sub-router children use expressions
        expr_base_lines = [l for l in output.splitlines()
                           if '_BASE' in l and '+' in l]
        assert len(expr_base_lines) > 0
        for name in ['SOC_FC_ITC_BASE', 'SOC_TIMER0_BASE', 'SOC_TIMER1_BASE']:
            matches = [l for l in expr_base_lines if name in l]
            assert len(matches) == 1, f'{name} should be an expression'

    def test_sub_router_base_comments(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        assert '/* 0x1a109000 */' in output
        assert '/* 0x1a10b000 */' in output
        assert '/* 0x1a10b800 */' in output

    def test_label_resets_prefix(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # APB router has label="SOC", so children use SOC_ prefix
        assert '#define SOC_FC_ITC_OFFSET' in output
        assert '#define SOC_TIMER0_OFFSET' in output

    def test_peripherals_base_define(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        assert '#define SOC_AXI_SOC_PERIPHERALS_BASE' in output
        assert '0x1a100000' in output

    def test_peripherals_size(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # Match only the defining line (name immediately after #define)
        lines = [l for l in output.splitlines()
                 if l.strip().startswith('#define SOC_AXI_SOC_PERIPHERALS_SIZE')]
        assert len(lines) == 1
        assert '0x01000000' in lines[0]

    def test_label_base_alias(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # apb has label='SOC' → SOC_BASE should alias SOC_AXI_SOC_PERIPHERALS_BASE
        lines = [l for l in output.splitlines()
                 if l.strip().startswith('#define SOC_BASE')]
        assert len(lines) == 1
        assert 'SOC_AXI_SOC_PERIPHERALS_BASE' in lines[0]

    def test_label_size_alias(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        # apb has label='SOC' → SOC_SIZE should alias SOC_AXI_SOC_PERIPHERALS_SIZE
        lines = [l for l in output.splitlines()
                 if l.strip().startswith('#define SOC_SIZE')]
        assert len(lines) == 1
        assert 'SOC_AXI_SOC_PERIPHERALS_SIZE' in lines[0]

    def test_label_same_as_path_no_alias(self):
        """When a node's label equals its full path alias no self-referential define is emitted."""
        from config_tree.header_gen import generate_memory_map
        # fc_itc is a child of apb (label='SOC'), so its alias under prefix 'SOC_AXI'
        # would be SOC_FC_ITC.  Give fc_itc label='SOC_FC_ITC' so lp == alias.
        target = Config('target')
        with Config.set_current_parent(target):
            router = MiniRouter('soc_axi', base=0x1A00_0000, size=0x0600_0000)
            with Config.set_current_parent(router):
                apb = MiniRouter('soc_peripherals', base=0x1A10_0000, size=0x0100_0000, label='SOC')
                with Config.set_current_parent(apb):
                    MiniPeripheral('fc_itc', base=0x1A10_9000, size=0x1000, label='SOC_FC_ITC')
        output = generate_memory_map(target, prefix='SOC_AXI')
        # The label alias SOC_FC_ITC_BASE would equal SOC_FC_ITC_BASE — must not be emitted
        lines = [l for l in output.splitlines()
                 if l.strip().startswith('#define SOC_FC_ITC_BASE')]
        # Only the real define should exist, not a self-referential one
        assert len(lines) == 1
        assert 'SOC_FC_ITC_BASE' not in lines[0].split('( ', 1)[-1]

    def test_sub_router_child_sizes(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        assert '#define SOC_FC_ITC_SIZE' in output
        assert '#define SOC_TIMER0_SIZE' in output
        assert '#define SOC_TIMER1_SIZE' in output

    def test_write_to_file(self, soc_tree, tmp_path):
        from config_tree.header_gen import generate_memory_map
        out = tmp_path / 'memory_map.h'
        result = generate_memory_map(soc_tree, str(out), prefix='SOC_AXI')
        assert out.exists()
        assert out.read_text() == result

    def test_no_duplicate_defines(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree, prefix='SOC_AXI')
        lines = [l.strip() for l in output.splitlines() if l.strip().startswith('#define')]
        names = [l.split()[1] for l in lines]
        assert len(names) == len(set(names)), f'Duplicate defines: {[n for n in names if names.count(n) > 1]}'

    def test_default_prefix_from_root_name(self, soc_tree):
        from config_tree.header_gen import generate_memory_map
        output = generate_memory_map(soc_tree)  # no prefix → uses first MemoryMapped node's name
        assert '#define SOC_AXI_L2_SHARED_BASE' in output

    def test_child_outside_parent_raises(self):
        """Children whose base is outside the parent's range must raise."""
        from config_tree.header_gen import generate_memory_map
        target = Config('target')
        with Config.set_current_parent(target):
            router = MiniRouter('soc_axi', base=0x1A00_0000, size=0x0600_0000)
            with Config.set_current_parent(router):
                # soc_peripherals is inside soc_axi → becomes the parent for children
                apb = MiniRouter('soc_peripherals', base=0x1A10_0000, size=0x0100_0000, label='SOC')
                with Config.set_current_parent(apb):
                    # base 0x0 is outside soc_peripherals (base 0x1A100000)
                    MiniPeripheral('bad_child', base=0x0000_0000, size=0x1000)
        with pytest.raises(ValueError, match='outside parent'):
            generate_memory_map(target, prefix='SOC_AXI')
