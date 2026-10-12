# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from __future__ import annotations

import abc
import os.path
import os
from dataclasses import dataclass, field

@dataclass
class ToolchainConfig:
    """
    Toolchain configuration

    This class descrives the overal behavior of the toolchain

    Attributes
    ----------
    use_ccache (bool): Use ccache tool for compiling
    incremental (bool): Use incremental compilation
    path_from_env (str): Specify an environment variable name giving the path to the toolchain
    """
    use_ccache: bool = True
    incremental: bool = True
    path_from_env: str = ''

@dataclass
class ToolchainCFlags:
    """
    Toolchain CFLAGS

    This describes all the information about a source code compilation. The toolchain will
    generates the compile command out of this information.

    Attributes
    ----------
    builddir (str): Build directory
    source_name (str): Source file base name
    source_path (str): Source file path
    cflags (list[str]): C flags
    includes (list[str]): include folders
    defines (list[str]): defines
    """
    builddir: str
    source_name: str
    source_path: str
    cflags: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)

@dataclass
class ToolchainLdFlags:
    """
    Toolchain LDFLAGS

    This describes all the information about object files linking. The toolchain will
    generates the link command out of this information.

    Attributes
    ----------
    builddir (str): Build directory
    binary (str): Binary path
    sources (list[str]): List of object files to be linked
    ldflags (list[str]): LD flags
    includes (list[str]): library include folders
    """
    builddir: str
    binary: str = ''
    sources: list[str] = field(default_factory=list)
    ldflags: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)

class Toolchain:
    """
    Parent toolchain class

    Any toolchain should inherit from this class.
    Some general behavior such as incremental compilation can be specified in the given
    configuration.

    Attributes
    ----------
    config (config: ToolchainConfig): Toolchain configuration where the behavior of the toolchain
        can be specified.
    """
    def __init__(self, config: ToolchainConfig, family: str):
        self.config = config
        self.family = family

    def get_family(self) -> str:
        return self.family

    def get_extra_cflags(self) -> list[str]:
        """Return cflags that should be applied to every compile when this
        toolchain is active. Default is empty; subclasses override for
        toolchain-specific flags."""
        return []

    @abc.abstractmethod
    def _get_compile_command(self, flags: ToolchainCFlags) -> str:
        """Get the compile command.
        The toolchain will determine the compile command from specified flags.
        This method must be overriden by the implementation class
        """
        pass

    @abc.abstractmethod
    def _get_link_command(self, flags: ToolchainLdFlags) -> str:
        """Get the link command.
        The toolchain will determine the link command from specified flags.
        This method must be overriden by the implementation class
        """
        pass

    def _get_toolchain_command(self, command):
        """Get the full toolchain command.
        """
        if self.config.path_from_env is not None:
            path = os.environ.get(self.config.path_from_env)
            if path is None:
                raise RuntimeError(f'{self.config.path_from_env} must be set to the toolchain path')

            return f'{path}/bin/{command}'

        return command

    def _get_compile_command_from_cc(self, cc, flags):
        """Get the compile command from the specified compiler command and flags.
        """
        cflags = flags.cflags.copy()

        if self.config.incremental:
            cflags += ['-MMD', '-MP']

        for define in flags.defines:
            if define.value is None:
                cflags.append(f'-D{define.name}')
            else:
                cflags.append(f'-D{define.name}={define.value}')

        for inc in flags.includes:
            cflags.append(f'-I{inc.name}')

        if flags.source_name.rfind('.S') != -1:
            cflags.append('-DLANGUAGE_ASSEMBLY')


        obj = os.path.join(flags.builddir, flags.source_name.rstrip('.c').rstrip('.S') + '.o')

        cmd = []

        if self.config.use_ccache:
            cmd.append('ccache')

        cmd.append(cc)

        cmd.append(f'-c {flags.source_path} -o {obj} {" ".join(cflags)}')

        # TODO
        os.makedirs(os.path.dirname(obj), exist_ok=True)

        return ' '.join(cmd)

    def _get_link_command_from_ld(self, ld, flags):
        """Get the link command from the specified linker command and flags.
        """
        cmd = []

        if self.config.use_ccache:
            cmd.append('ccache')

        cmd.append(ld)

        for source in flags.sources:
            source_name, source_path = source
            cmd.append(os.path.join(flags.builddir, source_name.rstrip('.c').rstrip('.S') + '.o'))

        for inc in flags.includes:
            cmd.append(f'-L{inc}')

        cmd += flags.ldflags

        cmd.append(f'-o {flags.binary}')

        return ' '.join(cmd)

    def _get_objdump_tool(self) -> str:
        """Return the base name of the objdump-like tool for this toolchain family.
        Must be overriden by the implementation class.
        """
        raise NotImplementedError

    def _get_size_tool(self) -> str:
        """Return the base name of the size tool for this toolchain family.
        Must be overriden by the implementation class.
        """
        raise NotImplementedError

    def _get_nm_tool(self) -> str:
        """Return the base name of the nm tool for this toolchain family.
        Must be overriden by the implementation class.
        """
        raise NotImplementedError

    def _get_disas_command(self, binary: str) -> str:
        """Get the command dumping the disassembly (with interleaved source) of the binary.
        """
        objdump = self._get_toolchain_command(self._get_objdump_tool())

        return f'{objdump} -d -h -S -t -w --show-raw-insn {binary}'

    def _get_size_command(self, binary: str) -> str:
        """Get the command dumping the section size summary of the binary.
        """
        size = self._get_toolchain_command(self._get_size_tool())

        return f'{size} -B -x --common {binary}'

    def _get_nm_command(self, binary: str) -> str:
        """Get the command dumping the symbols (sorted by size) of the binary.
        """
        nm = self._get_toolchain_command(self._get_nm_tool())

        return f'{nm} -a -A -l -S --size-sort --special-syms {binary}'


class _LlvmToolchain(Toolchain):
    """
    Parent toolchain class for LLVM toolchains
    """
    def __init__(self, config: ToolchainConfig):
        super().__init__(config, family='llvm')


class _GccToolchain(Toolchain):
    """
    Parent toolchain class for GCC toolchains
    """
    def __init__(self, config: ToolchainConfig):
        super().__init__(config, family='gcc')

    def get_extra_cflags(self) -> list[str]:
        # GCC-only: stop the loop-distribute pass from rewriting
        # hand-rolled byte/word loops as memcpy/memset, which freestanding
        # PulpOS does not link against.
        return ['-fno-tree-loop-distribute-patterns']



class RiscvLlvmToolchain(_LlvmToolchain):
    """
    Toolchain class for Ricv LLVM

    This class must be used to compile with the Riscv LLVM toolchain

    Attributes
    ----------
    config (ToolchainConfig): Flags to configure toolchain behavior
    """
    def __init__(self, config: ToolchainConfig):
        super().__init__(config)

    def _get_compile_command(self, flags:ToolchainCFlags) -> str:

        cc = self._get_toolchain_command('clang')

        return self._get_compile_command_from_cc(cc, flags)


    def _get_link_command(self, flags: ToolchainLdFlags) -> str:

        ld = self._get_toolchain_command('clang')

        return self._get_link_command_from_ld(ld, flags)

    def _get_objdump_tool(self) -> str:
        return 'llvm-objdump'

    def _get_size_tool(self) -> str:
        return 'llvm-size'

    def _get_nm_tool(self) -> str:
        return 'llvm-nm'


class RiscvGccToolchain(_GccToolchain):
    """
    Toolchain class for Ricv GCC

    This class must be used to compile with the Riscv GCC toolchain

    Attributes
    ----------
    config (ToolchainConfig): Flags to configure toolchain behavior
    """

    def __init__(self, config: ToolchainConfig):
        super().__init__(config)

    def _get_compile_command(self, flags:ToolchainCFlags) -> str:
        """Get the compile command.
        The toolchain will determine the compile command from specified flags.
        """
        cc = self._get_toolchain_command('riscv32-unknown-elf-gcc')

        return self._get_compile_command_from_cc(cc, flags)

    def _get_link_command(self, flags: ToolchainLdFlags) -> str:
        """Get the link command.
        The toolchain will determine the link command from specified flags.
        """
        ld = self._get_toolchain_command('riscv32-unknown-elf-gcc')

        return self._get_link_command_from_ld(ld, flags)

    def _get_objdump_tool(self) -> str:
        return 'riscv32-unknown-elf-objdump'

    def _get_size_tool(self) -> str:
        return 'riscv32-unknown-elf-size'

    def _get_nm_tool(self) -> str:
        return 'riscv32-unknown-elf-nm'
