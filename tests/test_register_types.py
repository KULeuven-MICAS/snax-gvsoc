"""Tests for config register types, md_parser, and RegisterList/CommandList field types."""

import json
import os
from types import SimpleNamespace
import pytest

from config_tree import Config, cfg_field
from config_tree.register_types import Cmd, Cmdfield, Cmdmap, Register, Regfield
from config_tree.register_field_types import CommandList, RegisterList
from config_tree.md_parser import parse_document, parse_registers, parse_cmdmaps

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'examples')
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), 'snapshots')
XIP_MD = os.path.abspath(os.path.join(EXAMPLES_DIR, 'README.xip.md'))
SPI_MD = os.path.abspath(os.path.join(EXAMPLES_DIR, 'README.spi.md'))


# ---------------------------------------------------------------------------
# Dataclass construction
# ---------------------------------------------------------------------------

class TestDataclasses:

    def test_regfield(self) -> None:
        rf = Regfield(name='TLB_EN', width=1, bit=0, access='R/W')
        assert rf.name == 'TLB_EN'
        assert rf.width == 1
        assert rf.bit == 0
        assert rf.access == 'R/W'
        assert rf.desc is None
        assert rf.reset is None

    def test_register_defaults(self) -> None:
        reg = Register(name='CFG')
        assert reg.offset is None
        assert reg.width is None
        assert reg.do_reset is True
        assert reg.fields == []
        assert reg.get_field_template() == 'CFG'

    def test_register_template(self) -> None:
        reg = Register(name='CFG_VIRT_ADDR0', template='CFG_VIRT_ADDR')
        assert reg.get_field_template() == 'CFG_VIRT_ADDR'

    def test_cmdfield(self) -> None:
        cf = Cmdfield(name='OP', width=4, offset=0, value=None)
        assert cf.name == 'OP'
        assert cf.width == 4

    def test_cmd(self) -> None:
        cmd = Cmd(name='READ', code='0x01', width=32)
        assert cmd.fields == []

    def test_cmdmap(self) -> None:
        cm = Cmdmap(name='SPI')
        assert cm.cmds == []


# ---------------------------------------------------------------------------
# Field reset derivation from register reset word
# ---------------------------------------------------------------------------

class TestFieldResetDerivation:
    """Tests for deriving field reset values from the parent register reset word."""

    MD = """\
# Test

## Registers

| Register Name | Offset | Size | Reset Value | Description |
|---------------|--------|------|-------------|-------------|
| CTRL          | 0x00   | 32   | 0x00050003  | Control     |
| STATUS        | 0x04   | 32   | 0x00000000  | Status      |
| NORESET       | 0x08   | 32   |             | No reset    |

## CTRL

| Field Name | Bit Position | Width | Access Type | Description |
|------------|--------------|-------|-------------|-------------|
| TX_EN      | 0            | 1     | R/W         | TX enable   |
| RX_EN      | 1            | 1     | R/W         | RX enable   |
| DIVISOR    | 16           | 8     | R/W         | Clock div   |

## STATUS

| Field Name | Bit Position | Width | Access Type | Description |
|------------|--------------|-------|-------------|-------------|
| BUSY       | 0            | 1     | R           | Busy flag   |

## NORESET

| Field Name | Bit Position | Width | Access Type | Description |
|------------|--------------|-------|-------------|-------------|
| VAL        | 0            | 8     | R/W         | Value       |
"""

    def _parse(self) -> dict[str, Register]:
        doc = parse_document(self.MD)
        return {r.name: r for r in parse_registers(doc)}

    def test_field_reset_derived_from_register(self) -> None:
        regs = self._parse()
        fields = {f.name: f for f in regs['CTRL'].fields}
        # 0x00050003: bit 0 → 1, bit 1 → 1, bits 16-23 → 0x05
        assert fields['TX_EN'].reset == 1
        assert fields['RX_EN'].reset == 1
        assert fields['DIVISOR'].reset == 0x05

    def test_field_reset_txt_derived(self) -> None:
        regs = self._parse()
        fields = {f.name: f for f in regs['CTRL'].fields}
        assert fields['TX_EN'].reset_txt == '0x1'
        assert fields['DIVISOR'].reset_txt == '0x5'

    def test_field_reset_none_when_register_reset_zero(self) -> None:
        regs = self._parse()
        fields = {f.name: f for f in regs['STATUS'].fields}
        assert fields['BUSY'].reset == 0
        assert fields['BUSY'].reset_txt == '0x0'

    def test_field_reset_none_when_register_has_no_reset(self) -> None:
        regs = self._parse()
        fields = {f.name: f for f in regs['NORESET'].fields}
        assert fields['VAL'].reset is None
        assert fields['VAL'].reset_txt == '--'

    def test_explicit_field_reset_takes_precedence(self) -> None:
        md = """\
# Test

## Registers

| Register Name | Offset | Reset Value | Description |
|---------------|--------|-------------|-------------|
| CFG           | 0x00   | 0xFF        | Config      |

## CFG

| Field Name | Bit Position | Width | Access Type | Default | Description |
|------------|--------------|-------|-------------|---------|-------------|
| VAL        | 0            | 8     | R/W         | 0x42    | Value       |
"""
        doc = parse_document(md)
        regs = {r.name: r for r in parse_registers(doc)}
        fields = {f.name: f for f in regs['CFG'].fields}
        assert fields['VAL'].reset == 0x42  # explicit wins over derived 0xFF
        assert fields['VAL'].reset_txt == '0x42'


# ---------------------------------------------------------------------------
# RegisterList.cast() / parse_registers
# ---------------------------------------------------------------------------

class TestRegisterListCast:

    def test_parses_without_error(self) -> None:
        regs = RegisterList.cast(XIP_MD, SimpleNamespace(type=RegisterList))
        assert isinstance(regs, list)
        assert len(regs) > 0

    def test_register_count_xip(self) -> None:
        regs = RegisterList.cast(XIP_MD, SimpleNamespace(type=RegisterList))
        assert len(regs) == 66

    def test_register_count_spi(self) -> None:
        regs = RegisterList.cast(SPI_MD, SimpleNamespace(type=RegisterList))
        assert len(regs) == 5

    def test_register_offsets_spi(self) -> None:
        regs = {r.name: r for r in RegisterList.cast(SPI_MD, SimpleNamespace(type=RegisterList))}
        expected = {
            'RX_DEST': 0x00,
            'TX_DEST': 0x04,
            'CMD_DEST': 0x08,
            'STATUS': 0x30,
            'CONFIG': 0x34,
        }
        for name, offset in expected.items():
            assert regs[name].offset == offset, f'{name}: expected {offset:#x}'

    def test_register_widths_spi(self) -> None:
        regs = {r.name: r for r in RegisterList.cast(SPI_MD, SimpleNamespace(type=RegisterList))}
        assert regs['RX_DEST'].width == 8
        assert regs['STATUS'].width == 7
        assert regs['CONFIG'].width == 3

    def test_fields_spi_config(self) -> None:
        regs = {r.name: r for r in RegisterList.cast(SPI_MD, SimpleNamespace(type=RegisterList))}
        fields = {f.name: f for f in regs['CONFIG'].get_fields()}
        assert fields['SPI_SLAVE_MODE'].bit == 0
        assert fields['SPI_SLAVE_MODE'].width == 1
        assert fields['RX_OVRFLW_EN'].bit == 1
        assert fields['TX_UNDRFLW_EN'].bit == 2

    def test_invalid_path_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match='Cannot load registers'):
            RegisterList.cast('/nonexistent/path.md', SimpleNamespace(type=RegisterList))

    def test_passthrough_list(self) -> None:
        existing = [Register(name='R0', offset=0)]
        result = RegisterList.cast(existing, SimpleNamespace(type=RegisterList))
        assert result[0].name == 'R0'


# ---------------------------------------------------------------------------
# RegisterList.validate / format
# ---------------------------------------------------------------------------

class TestRegisterListValidate:

    def test_format(self) -> None:
        rl = RegisterList([Register(name='A'), Register(name='B')])
        assert RegisterList.format(rl) == '[2 registers]'

    def test_validate_ok(self) -> None:
        RegisterList.validate([Register(name='X', offset=0)], SimpleNamespace(type=RegisterList))

    def test_validate_bad_element(self) -> None:
        with pytest.raises(ValueError, match='Expected Register'):
            RegisterList.validate(['not-a-register'], SimpleNamespace(type=RegisterList))

    def test_validate_not_list(self) -> None:
        with pytest.raises(ValueError, match='Cannot load registers'):
            RegisterList.validate('oops', SimpleNamespace(type=RegisterList))

    def test_check_annotation(self) -> None:
        assert RegisterList.check_annotation(RegisterList) is True
        assert RegisterList.check_annotation(list) is False


# ---------------------------------------------------------------------------
# CommandList
# ---------------------------------------------------------------------------

class TestCommandListCast:

    def test_no_commands_section_returns_empty(self) -> None:
        # XIP and SPI markdowns have no Commands section
        result = CommandList.cast(SPI_MD, SimpleNamespace(type=CommandList))
        assert isinstance(result, list)
        assert len(result) == 0

    def test_check_annotation(self) -> None:
        assert CommandList.check_annotation(CommandList) is True
        assert CommandList.check_annotation(list) is False

    def test_format(self) -> None:
        cl = CommandList([Cmdmap(name='A'), Cmdmap(name='B')])
        assert CommandList.format(cl) == '[2 command maps]'

    def test_validate_bad_element(self) -> None:
        with pytest.raises(ValueError, match='Expected Cmdmap'):
            CommandList.validate(['not-a-cmdmap'], SimpleNamespace(type=CommandList))


# ---------------------------------------------------------------------------
# Use as cfg_field on a Config subclass
# ---------------------------------------------------------------------------

class TestRegisterFieldOnConfig:

    def test_config_with_register_list_field(self) -> None:
        class RegConfig(Config):
            registers: RegisterList = cfg_field(
                default_factory=RegisterList,
                desc='Register map',
            )

        cfg = RegConfig('regcfg')
        assert isinstance(cfg.registers, list)
        assert len(cfg.registers) == 0

    def test_override_loads_from_path(self) -> None:
        class RegConfig2(Config):
            registers: RegisterList = cfg_field(
                default_factory=RegisterList,
                desc='Register map',
                write=True,
            )

        Config.override_fields([f'regcfg2/registers={SPI_MD}'])
        cfg = RegConfig2('regcfg2')
        assert len(cfg.registers) == 5
        assert cfg.registers[0].name == 'RX_DEST'

    def test_file_path_factory(self) -> None:
        class RegConfig2(Config):
            registers: RegisterList = cfg_field(
                default=EXAMPLES_DIR,
                desc='Register map',
                write=True,
            )

        cfg = RegConfig2('regcfg2')
        assert len(cfg.registers) == 76
        assert cfg.registers[0].name == 'RX_DEST'

    def test_file_url_factory(self) -> None:
        class RegConfig2(Config):
            registers: RegisterList = cfg_field(
                default=f'{EXAMPLES_DIR}/README.indirect.md',
                desc='Register map',
                write=True,
            )

        cfg = RegConfig2('regcfg2')
        assert len(cfg.registers) == 5
        assert cfg.registers[0].name == 'RX_DEST'

# ---------------------------------------------------------------------------
# Parity test: new parser vs frozen snapshots (generated from original regmap)
# ---------------------------------------------------------------------------

class TestParityWithSnapshot:

    def _load_snapshot(self, name: str) -> dict:
        path = os.path.join(SNAPSHOTS_DIR, f'registers_{name}.json')
        with open(path) as fh:
            return json.load(fh)

    def _test_registers_match(self, md_path: str, snapshot_name: str) -> None:
        snap = self._load_snapshot(snapshot_name)
        new_regs = {r.name: r for r in RegisterList.cast(md_path, SimpleNamespace(type=RegisterList))}

        assert set(new_regs.keys()) == set(snap.keys()), (
            f'Register name mismatch: {set(new_regs.keys()) ^ set(snap.keys())}'
        )

        for name, snap_r in snap.items():
            new_r = new_regs[name]
            assert new_r.offset == snap_r['offset'], f'{name}: offset mismatch'
            assert new_r.width  == snap_r['width'],  f'{name}: width mismatch'
            assert new_r.reset  == snap_r['reset'],  f'{name}: reset mismatch'

            snap_fields = snap_r['fields']
            new_fields = {f.name: f for f in new_r.get_fields()}
            assert set(new_fields.keys()) == set(snap_fields.keys()), (
                f'{name}: field name mismatch'
            )
            for fname, sf in snap_fields.items():
                nf = new_fields[fname]
                assert nf.bit    == sf['bit'],    f'{name}.{fname}: bit mismatch'
                assert nf.width  == sf['width'],  f'{name}.{fname}: width mismatch'
                assert nf.access == sf['access'], f'{name}.{fname}: access mismatch'
                assert nf.reset  == sf['reset'],  f'{name}.{fname}: reset mismatch'

    def test_parity_xip(self) -> None:
        self._test_registers_match(XIP_MD, 'xip')

    def test_parity_spi(self) -> None:
        self._test_registers_match(SPI_MD, 'spi')
