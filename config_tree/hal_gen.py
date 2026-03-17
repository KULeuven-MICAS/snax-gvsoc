# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Martin Croome (croomem@essilor.fr)

"""Generate C HAL register accessor headers from config_tree register data.

Produces output matching the format of the existing ``timer.h`` golden
reference:  OFFSET defines, bit-field defines, typedef unions, a global
struct, register-level accessor functions, and field-extraction macros.

The two public entry points are :func:`generate_registers` and
:func:`generate_commands`.  Both accept an external :class:`CodeBlock` so
that the caller (e.g. ``CHeaderContainer.render``) controls the header
preamble and footer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from code_block import CodeBlock

from .register_types import Register, Regfield, Cmd, Cmdfield, Cmdmap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c_desc(name: str) -> str:
    """Sanitise a description string for C comments."""
    return name.replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')


def _c_name(name: str) -> str:
    """Convert a name to a C-safe identifier."""
    return (name
            .replace('/', '_')
            .replace('.', '_')
            .replace(' ', '_')
            .encode('ascii', 'ignore')
            .decode('ascii'))


def _c_name_no_digit_first(name: str) -> str:
    result = _c_name(name)
    if result and result[0].isdigit():
        result = '_' + result
    return result


# ---------------------------------------------------------------------------
# Header preamble / footer constants
# ---------------------------------------------------------------------------

SPDX = f"""\
/* THIS FILE HAS BEEN GENERATED, DO NOT MODIFY IT.
 */

// SPDX-FileCopyrightText: {datetime.now().year} ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//"""


GAP_MACROS = """\
#define GAP_WRITE_VOL(base, offset, value) __builtin_pulp_write_base_off_v((value), (base), (offset))
#define GAP_WRITE(base, offset, value)     \\
({ __asm__ __volatile__ ("" : : : "memory"); \\
    *(volatile uint32_t *)((base) + (offset)) = value; \\
    __asm__ __volatile__ ("" : : : "memory"); \\
})
#define GAP_READ(base, offset)             \\
({ __asm__ __volatile__ ("" : : : "memory"); \\
    uint32_t result = *(volatile uint32_t *)((base) + (offset)); \\
    __asm__ __volatile__ ("" : : : "memory"); \\
    result; \\
})
#define GAP_WRITE_PTR(base, offset, value) __builtin_pulp_OffsetedWritePtr((int *)(value), (int *)(base), (offset))"""


# All available register sections, in canonical order
REG_SECTIONS = ('regs', 'regfields', 'structs', 'regmap', 'accessors', 'macros')

# All available command sections
CMD_SECTIONS = ('commands',)


# ---------------------------------------------------------------------------
# Core generator (internal — writes into a caller-supplied CodeBlock)
# ---------------------------------------------------------------------------

class _HalEmitter:
    """Internal emitter that writes register/command C declarations.

    All output goes to the *cb* passed at construction time.
    No header preamble or footer is emitted.
    """

    def __init__(self, cb: CodeBlock, name: str):
        self._cb = cb
        self._prefix = _c_name(name).upper()  # e.g. "TIMER"
        self._lower = _c_name(name).lower()   # e.g. "timer"

    # -- register sections ----------------------------------------------------

    def emit_registers(
        self,
        registers: Sequence[Register],
        sections: set[str] | None = None,
    ) -> None:
        """Emit register declarations into the CodeBlock.

        Args:
            registers: List of ``Register`` objects.
            sections: Subset of :data:`REG_SECTIONS` to include (None = all).
        """
        if sections is None:
            sections = set(REG_SECTIONS)
        if 'regs' in sections:
            self._emit_regs(registers)
        if 'regfields' in sections:
            self._emit_regfields(registers)
        if 'structs' in sections:
            self._emit_structs(registers)
        if 'regmap' in sections:
            self._emit_regmap(registers)
        if 'accessors' in sections:
            self._emit_accessors(registers)
        if 'macros' in sections:
            self._emit_macros(registers)

    # -- command sections ---------------------------------------------------

    def emit_commands(self, commands: Sequence[Cmdmap]) -> None:
        """Emit command declarations into the CodeBlock."""
        self._emit_commands(commands)

    # -- section emitters ---------------------------------------------------

    def _emit_header(self, title: str):
        self._cb.nl(3)
        with self._cb.long_comment() as lc:
            lc.write(title)

    def _emit_regs(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS')

        for reg in registers:
            reg_name = _c_name(reg.name).upper()
            define_name = f'{self._prefix}_{reg_name}_OFFSET'
            desc = _c_desc(reg.desc) if reg.desc else ''
            self._cb.nl()
            if desc:
                self._cb.comment(desc)
            self._cb.write(f'#define {define_name:<40} 0x{reg.offset or 0:x}')

    def _emit_regfields(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS FIELDS')

        for reg in registers:
            reg_name = _c_name(reg.name).upper()
            for fld in reg.fields:
                field_name = f'{self._prefix}_{reg_name}_{_c_name(fld.name).upper()}'
                desc = _c_desc(fld.desc) if fld.desc else ''
                access_str = f' (access: {fld.access})' if fld.access else ''
                bit = fld.bit if fld.bit is not None else 0
                width = fld.width if fld.width is not None else 1
                mask = ((1 << width) - 1) << bit
                self._cb.nl()
                if desc or access_str:
                    self._cb.comment(f'{desc}{access_str}')
                self._cb.write(
                    f'#define {field_name + "_BIT":<60} {bit}',
                    f'#define {field_name + "_WIDTH":<60} {width}',
                    f'#define {field_name + "_MASK":<60} 0x{mask:x}')
                if fld.reset is not None:
                    self._cb.write(f'#define {field_name + "_RESET":<60} 0x{fld.reset:x}')

    def _emit_structs(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS STRUCTS')
        self._cb.write('#ifndef LANGUAGE_ASSEMBLY')

        for reg in registers:
            reg_name = _c_name(reg.name).lower()
            reg_width = reg.width if reg.width else 32
            self._cb.nl().write('typedef union {')
            with self._cb.indented_block() as cb1:
                cb1.write('struct {')
                with cb1.indented_block() as cb2:

                    prev_end = 0
                    padding_idx = 0
                    for fld in sorted(reg.fields, key=lambda f: f.bit if f.bit is not None else 0):
                        bit = fld.bit if fld.bit is not None else 0
                        width = fld.width if fld.width is not None else 1
                        fname = _c_name_no_digit_first(fld.name).lower()
                        desc = _c_desc(fld.desc) if fld.desc else ''

                        # Padding for gap
                        if bit > prev_end:
                            gap = bit - prev_end
                            cb2.write(f'unsigned int padding{padding_idx}:{gap:<2};')
                            padding_idx += 1

                        int_type = 'unsigned int' if width <= 32 else 'unsigned long long int'
                        cb2.write(f'{int_type} {fname:<16}:{width:<2}; // {desc}')
                        prev_end = bit + width

                cb1.write('};')
                if reg_width <= 32:
                    cb1.write('unsigned int raw;')
                else:
                    cb1.write(f'unsigned int raw[{(reg_width + 31) // 32}];')
            self._cb.write(f'}} __attribute__((packed)) {self._lower}_{reg_name}_t;')

        self._cb.nl().write('#endif')

    def _emit_regmap(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS GLOBAL STRUCT')
        self._cb.write('#ifndef LANGUAGE_ASSEMBLY')
        self._cb.write('typedef struct {')
        with self._cb.indented_block() as cb:
            for reg in registers:
                reg_name = _c_name(reg.name).lower()
                desc = _c_desc(reg.desc) if reg.desc else ''
                cb.write(f'  unsigned int {reg_name:<16}; // {desc}')

        self._cb.write(f'}} __attribute__((packed)) {self._lower}_{self._lower}_t;').nl()
        self._cb.write('#endif')

    def _emit_accessors(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS ACCESS FUNCTIONS')
        self._cb.write('#ifndef LANGUAGE_ASSEMBLY')

        for reg in registers:
            reg_name = _c_name(reg.name).lower()
            reg_name_upper = _c_name(reg.name).upper()
            offset_name = f'{self._prefix}_{reg_name_upper}_OFFSET'
            func_prefix = f'{self._lower}_{reg_name}'
            self._cb.nl().write(
                f'static inline uint32_t {func_prefix}_get(uint32_t base)'
                f' {{ return GAP_READ(base, {offset_name}); }}'
            )
            self._cb.write(
                f'static inline void {func_prefix}_set(uint32_t base, uint32_t value)'
                f' {{ GAP_WRITE(base, {offset_name}, value); }}'
            )
        self._cb.nl().write('#endif')

    def _emit_macros(self, registers: Sequence[Register]) -> None:
        self._emit_header('REGISTERS FIELDS MACROS')
        self._cb.write('#ifndef LANGUAGE_ASSEMBLY')

        for reg in registers:
            reg_name = _c_name(reg.name).upper()
            for fld in reg.fields:
                field_name = f'{self._prefix}_{reg_name}_{_c_name(fld.name).upper()}'
                bit = fld.bit if fld.bit is not None else 0
                width = fld.width if fld.width is not None else 1

                self._cb.nl()
                self._cb.write(
                    f'#define {field_name + "_GET(value)":<50} (ARCHI_BEXTRACTU((value),{width},{bit}))',
                    f'#define {field_name + "_GETS(value)":<50} (ARCHI_BEXTRACT((value),{width},{bit}))',
                    f'#define {field_name + "_SET(value,field)":<50} (ARCHI_BINSERT((value),(field),{width},{bit}))',
                    f'#define {field_name + "(val)":<50} ((val) << {bit})')

        self._cb.nl().write('#endif')

    def _emit_commands(self, commands: Sequence[Cmdmap]) -> None:
        self._emit_header('COMMANDS')

        for cmdmap in commands:
            map_name = _c_name(cmdmap.name).upper()
            for cmd in cmdmap.cmds:
                cmd_name = _c_name(cmd.name).upper()
                define_name = f'{self._prefix}_{map_name}_{cmd_name}'
                if cmd.code is not None:
                    self._cb.write(f'#define {define_name:<40} {cmd.code}')
                for fld in cmd.fields:
                    fld_name = _c_name(fld.name).upper()
                    fld_define = f'{define_name}_{fld_name}'
                    if fld.value is not None:
                        self._cb.write(f'#define {fld_define:<40} {fld.value}')



# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def generate_register_macros(
    cb: CodeBlock,
) -> None:
    cb.write('#ifndef LANGUAGE_ASSEMBLY').nl()
    cb.write(*GAP_MACROS.split('\n')).nl()
    cb.write('#endif')

def generate_registers(
    cb: CodeBlock,
    name: str,
    registers: Sequence[Register],
    *,
    sections: set[str] | None = None,
) -> None:
    """Emit register declarations into *cb* (no header/footer).

    Args:
        cb: CodeBlock to write into.
        name: Peripheral name (used for C prefix).
        registers: List of Register objects.
        sections: Subset of :data:`REG_SECTIONS` to emit (None = all).
    """
    _HalEmitter(cb, name).emit_registers(registers, sections=sections)


def generate_commands(
    cb: CodeBlock,
    name: str,
    commands: Sequence[Cmdmap],
) -> None:
    """Emit command declarations into *cb* (no header/footer).

    Args:
        cb: CodeBlock to write into.
        name: Peripheral name (used for C prefix).
        commands: List of Cmdmap objects.
    """
    _HalEmitter(cb, name).emit_commands(commands)
