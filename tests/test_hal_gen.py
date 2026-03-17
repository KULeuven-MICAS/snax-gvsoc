"""Tests for hal_gen: C HAL register accessor header generation."""

import pytest

from code_block import CodeBlock
from config_tree.register_types import Register, Regfield, Cmd, Cmdfield, Cmdmap
from config_tree.hal_gen import generate_registers, generate_commands, SPDX, GAP_MACROS


# ---------------------------------------------------------------------------
# Helper — build a standalone header string for easy assertion
# ---------------------------------------------------------------------------

def _render(name, *, registers=None, commands=None, sections=None):
    """Build a full header string using generate_registers/generate_commands."""
    cb = CodeBlock()
    cb.write_raw(SPDX)
    cb.write_raw('')
    cb.write_raw('#pragma once')
    cb.write_raw('')
    cb.write_raw('#ifndef LANGUAGE_ASSEMBLY')
    cb.write_raw('')
    for line in GAP_MACROS.split('\n'):
        cb.write_raw(line)
    cb.write_raw('')
    cb.write_raw('#endif')
    if registers:
        generate_registers(cb, name, registers, sections=sections)
    if commands:
        generate_commands(cb, name, commands)
    cb.write_raw('')
    return str(cb)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def timer_registers():
    """Minimal timer-like register set for testing."""
    return [
        Register(
            name='cfg_lo',
            offset=0x0,
            width=32,
            desc='Timer Low Configuration register.',
            fields=[
                Regfield('enable', width=1, bit=0, access='R/W',
                         desc='Timer low enable configuration bitfield: - 1\'b0: disabled - 1\'b1: enabled'),
                Regfield('reset', width=1, bit=1, access='R/W',
                         desc='Timer low counter reset command bitfield.'),
                Regfield('irqen', width=1, bit=2, access='R/W',
                         desc='Timer low compare match interrupt enable.'),
                Regfield('pval', width=8, bit=8, access='R/W',
                         desc='Timer low prescaler value bitfield.'),
                Regfield('casc', width=1, bit=31, access='R/W',
                         desc='Timer low 64bit cascaded mode.'),
            ],
        ),
        Register(
            name='cfg_hi',
            offset=0x4,
            width=32,
            desc='Timer High Configuration register.',
            fields=[
                Regfield('enable', width=1, bit=0, access='R/W',
                         desc='Timer high enable.'),
            ],
        ),
        Register(
            name='cnt_lo',
            offset=0x8,
            width=32,
            desc='Timer Low counter value register.',
            fields=[
                Regfield('cnt_lo', width=32, bit=0, access='R/W',
                         desc='Timer Low counter value bitfield.'),
            ],
        ),
    ]


@pytest.fixture
def timer_commands():
    """Minimal command set for testing."""
    return [
        Cmdmap(name='ctrl', cmds=[
            Cmd(name='start', code='0x1', width=8, desc='Start timer',
                fields=[
                    Cmdfield('mode', width=2, offset=0, value='0x0', desc='Timer mode'),
                ]),
            Cmd(name='stop', code='0x2', width=8, desc='Stop timer'),
        ]),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHalGen:

    def test_regs_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regs'})
        assert '#define TIMER_CFG_LO_OFFSET' in output
        assert '0x0' in output
        assert '#define TIMER_CFG_HI_OFFSET' in output
        assert '0x4' in output
        assert '#define TIMER_CNT_LO_OFFSET' in output
        assert '0x8' in output

    def test_regs_desc_comment(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regs'})
        assert '// Timer Low Configuration register.' in output

    def test_regfields_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regfields'})
        assert '#define TIMER_CFG_LO_ENABLE_BIT' in output
        assert '#define TIMER_CFG_LO_ENABLE_WIDTH' in output
        assert '#define TIMER_CFG_LO_ENABLE_MASK' in output
        # Check values
        lines = output.splitlines()
        bit_line = [l for l in lines if 'TIMER_CFG_LO_ENABLE_BIT' in l][0]
        assert bit_line.strip().endswith('0')
        width_line = [l for l in lines if 'TIMER_CFG_LO_ENABLE_WIDTH' in l][0]
        assert width_line.strip().endswith('1')
        mask_line = [l for l in lines if 'TIMER_CFG_LO_ENABLE_MASK' in l][0]
        assert '0x1' in mask_line

    def test_regfields_access_comment(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regfields'})
        assert '(access: R/W)' in output

    def test_regfields_pval_mask(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regfields'})
        lines = output.splitlines()
        mask_line = [l for l in lines if 'TIMER_CFG_LO_PVAL_MASK' in l][0]
        assert '0xff00' in mask_line

    def test_regfields_casc_mask(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regfields'})
        lines = output.splitlines()
        mask_line = [l for l in lines if 'TIMER_CFG_LO_CASC_MASK' in l][0]
        assert '0x80000000' in mask_line

    def test_structs_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'structs'})
        assert 'typedef union {' in output
        assert 'timer_cfg_lo_t;' in output
        assert 'timer_cfg_hi_t;' in output
        assert 'unsigned int raw;' in output

    def test_structs_bitfields(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'structs'})
        assert 'enable' in output
        assert ':1' in output

    def test_structs_padding(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'structs'})
        # cfg_lo has gap between pval(8+8=16) and casc(31) → padding
        assert 'padding' in output

    def test_regmap_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regmap'})
        assert 'typedef struct {' in output
        assert 'timer_timer_t;' in output
        assert 'unsigned int cfg_lo' in output
        assert 'unsigned int cfg_hi' in output
        assert 'unsigned int cnt_lo' in output

    def test_accessors_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'accessors'})
        assert 'timer_cfg_lo_get' in output
        assert 'timer_cfg_lo_set' in output
        assert 'GAP_READ(base, TIMER_CFG_LO_OFFSET)' in output
        assert 'GAP_WRITE(base, TIMER_CFG_LO_OFFSET, value)' in output

    def test_accessors_single_line(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'accessors'})
        # Each accessor should be on one line (no multi-line)
        for line in output.splitlines():
            if 'static inline' in line:
                assert '{' in line and '}' in line

    def test_macros_section(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'macros'})
        assert 'TIMER_CFG_LO_ENABLE_GET(value)' in output
        assert 'TIMER_CFG_LO_ENABLE_GETS(value)' in output
        assert 'TIMER_CFG_LO_ENABLE_SET(value,field)' in output
        assert 'TIMER_CFG_LO_ENABLE(val)' in output
        assert 'ARCHI_BEXTRACTU' in output
        assert 'ARCHI_BEXTRACT' in output
        assert 'ARCHI_BINSERT' in output

    def test_macros_shift(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'macros'})
        # The shift macro for enable (bit 0) should be ((val) << 0)
        lines = [l for l in output.splitlines() if 'TIMER_CFG_LO_ENABLE(val)' in l]
        assert len(lines) == 1
        assert '((val) << 0)' in lines[0]

    def test_commands_section(self, timer_commands):
        output = _render('TIMER', commands=timer_commands)
        assert '#define TIMER_CTRL_START' in output
        assert '0x1' in output
        assert '#define TIMER_CTRL_STOP' in output
        assert '0x2' in output
        assert 'TIMER_CTRL_START_MODE' in output
        assert '0x0' in output

    def test_full_output(self, timer_registers, timer_commands):
        output = _render('TIMER', registers=timer_registers,
                         commands=timer_commands)
        assert '#pragma once' in output or '#ifndef' in output
        assert 'REGISTERS' in output
        assert 'REGISTERS FIELDS' in output
        assert 'REGISTERS STRUCTS' in output
        assert 'REGISTERS GLOBAL STRUCT' in output
        assert 'REGISTERS ACCESS FUNCTIONS' in output
        assert 'REGISTERS FIELDS MACROS' in output
        assert 'COMMANDS' in output
        assert '#endif' in output

    def test_write_to_file(self, timer_registers, tmp_path):
        """Config.gen_hal writes to file — tested in TestConfigGenHal."""
        pass

    def test_registers_only(self, timer_registers):
        """No commands → commands section omitted."""
        output = _render('TIMER', registers=timer_registers)
        assert 'REGISTERS' in output
        assert 'COMMANDS' not in output

    def test_commands_only(self, timer_commands):
        """No registers → register sections omitted."""
        output = _render('TIMER', commands=timer_commands)
        assert 'COMMANDS' in output
        assert 'REGISTERS FIELDS' not in output

    def test_no_duplicate_defines(self, timer_registers):
        output = _render('TIMER', registers=timer_registers,
                         sections={'regs', 'regfields', 'macros'})
        lines = [l.strip() for l in output.splitlines() if l.strip().startswith('#define')]
        names = [l.split()[1].split('(')[0] for l in lines]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(dupes) == 0, f'Duplicate defines: {set(dupes)}'

    def test_header_guard(self, timer_registers):
        output = _render('TIMER', registers=timer_registers)
        assert '#pragma once' in output

    def test_gap_macros_in_header(self, timer_registers):
        output = _render('TIMER', registers=timer_registers)
        assert 'GAP_WRITE_VOL' in output
        assert 'GAP_WRITE(' in output
        assert 'GAP_READ(' in output

    def test_language_assembly_guard(self, timer_registers):
        output = _render('TIMER', registers=timer_registers)
        assert '#ifndef LANGUAGE_ASSEMBLY' in output


class TestConfigGenHal:
    """Test the Config.gen_hal() integration method."""

    def test_gen_hal_with_register_list(self, tmp_path):
        from config_tree import Config
        from config_tree.register_field_types import RegisterList

        Config.reset()
        cfg = Config('timer')

        regs = RegisterList([
            Register('cfg_lo', offset=0x0, width=32, desc='Config register.', fields=[
                Regfield('enable', width=1, bit=0, access='R/W', desc='Enable bit'),
            ]),
        ])

        out = tmp_path / 'timer.h'
        result = cfg.gen_hal(str(out), regs)
        assert out.exists()
        content = out.read_text()
        assert '#define TIMER_CFG_LO_OFFSET' in content
        assert 'TIMER_CFG_LO_ENABLE_BIT' in content
        Config.reset()

    def test_gen_hal_with_label(self, tmp_path):
        from config_tree import Config
        from config_tree.register_field_types import RegisterList

        Config.reset()
        cfg = Config('timer0', label='FC_TIMER')

        regs = RegisterList([
            Register('cfg_lo', offset=0x0, width=32, desc='Config.', fields=[]),
        ])

        out = tmp_path / 'timer.h'
        cfg.gen_hal(str(out), regs)
        content = out.read_text()
        assert '#define FC_TIMER_CFG_LO_OFFSET' in content
        Config.reset()

    def test_gen_hal_multiple_register_lists(self, tmp_path):
        from config_tree import Config
        from config_tree.register_field_types import RegisterList

        Config.reset()
        cfg = Config('timer')

        regs1 = RegisterList([
            Register('cfg_lo', offset=0x0, width=32, desc='Config Lo.', fields=[]),
        ])
        regs2 = RegisterList([
            Register('cfg_hi', offset=0x4, width=32, desc='Config Hi.', fields=[]),
        ])

        out = tmp_path / 'timer.h'
        cfg.gen_hal(str(out), regs1, regs2)
        content = out.read_text()
        assert '#define TIMER_CFG_LO_OFFSET' in content
        assert '#define TIMER_CFG_HI_OFFSET' in content
        Config.reset()

    def test_gen_hal_commands_only(self, tmp_path):
        from config_tree import Config
        from config_tree.register_field_types import CommandList

        Config.reset()
        cfg = Config('timer')

        cmds = CommandList([
            Cmdmap(name='ctrl', cmds=[
                Cmd(name='start', code='0x1', width=8, desc='Start'),
            ]),
        ])

        out = tmp_path / 'timer.h'
        cfg.gen_hal(str(out), cmds)
        content = out.read_text()
        assert 'TIMER_CTRL_START' in content
        Config.reset()

    def test_gen_hal_bad_type_raises(self, tmp_path):
        from config_tree import Config

        Config.reset()
        cfg = Config('timer')

        with pytest.raises(TypeError, match='Expected RegisterList or CommandList'):
            cfg.gen_hal(str(tmp_path / 'timer.h'), [1, 2, 3])
        Config.reset()
