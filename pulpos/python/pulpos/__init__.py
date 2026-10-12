# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

from __future__ import annotations

import os
import sys
import subprocess
import importlib.util
import logging
import collections
from types import ModuleType
from typing import Any, List, Tuple, Protocol

from gvrun.config import Config
try:
    from typing import override  # Python 3.12+
except ImportError:
    from typing_extensions import override  # Python 3.10–3.11
import gvrun.commands
from gvrun.systree import SystemTreeNode
from typing import Any
import dataclasses
import rich.tree
from gvrun.parameter import set_parameters_from_node
from pulpos.toolchain import Toolchain, ToolchainCFlags, ToolchainLdFlags
from gvrun.builder import Builder
from gvrun.systree import Executable, SystemTreeNode
from collections import deque
from gvrun.header_gen import generate_headers

# Make sure we look for sources in every directory specified in PULPOS_MODULES
_modules = os.environ.get('PULPOS_MODULES')
if _modules is not None:
    pulpos_source_paths = _modules.split(':')


def get_home(container: "SourceContainer") -> str:
    """Returns pulpos home folder

    This is taken from PULPOS_HOME envvar. Raises an error if it is not defined.

    Returns
    -------
    str
        Pulpos home folder.
    """
    home = os.environ.get('PULPOS_HOME')
    if home is None:
        raise RuntimeError(f'{container._get_title(True)} PULPOS_HOME is not defined')
    return home


def get_path_from_source(path: str):
    """ Returns the absolute path of the file

    The file specified by its file path is searched into the source code search paths
    and its absolute within one of the search path is returned.
    If the file is not found in the search paths, its path is returned as it is
    Parameters
    ----------
    path : str
        The path of the file relative to one of the source code search path
    """
    global pulpos_source_paths
    if os.path.isabs(path):
        return path

    for source_path in pulpos_source_paths:
        full_path = os.path.join(source_path, path)
        if os.path.exists(full_path):
            return full_path

    return path


class _CompileCommand(gvrun.commands.Command):
    """
    Command for compiling a source file

    Once created, the command is enqueued to the builder in order to be scheduled, and called
    when one the worker wants to execute it.

    Attributes
    ----------
    builder : Builder
        Builder where commands should be enqueued.
    toolchain: Toolchain
        Toolchain used for compiling the source code
    flags: ToolchainCFlags
        List of flags used for compiling the source code
    """
    def __init__(self, builder: Builder, toolchain: Toolchain,
            flags: ToolchainCFlags):
        super().__init__(builder)

        self.flags = flags
        # Remember the current path to execute the compile command from there in case some
        # files are using relative path
        self.path = os.getcwd()

        if toolchain is None:
            raise RuntimeError('Trying to compile without any toolchain attached')

        self.command = toolchain._get_compile_command(flags)

    def run(self):
        """Execute the compilation command.

        Should be called by a builder worker then the command is ready to be executed.
        """
        print (f'CC  {self.flags.source_path}', flush=True)
        self.execute(self.command, self.path)


class _LinkCommand(gvrun.commands.Command):
    """
    Command for linking object files.

    Once created, the command is enqueued to the builder in order to be scheduled, and called
    when one the worker wants to execute it.

    Attributes
    ----------
    builder : Builder
        Builder where commands should be enqueued.
    toolchain: Toolchain
        Toolchain used for linking the object files
    flags: ToolchainLdFlags
        List of flags used for linking the object files
    """
    def __init__(self, builder: Builder, toolchain: Toolchain,
            flags: ToolchainLdFlags):
        super().__init__(builder)

        self.builder = builder
        self.flags = flags
        # Remember the current path to execute the compile command from there in case some
        # files are using relative path
        self.path = os.getcwd()

        if toolchain is None:
            raise RuntimeError('Trying to compile without any toolchain attached')

        self.command = toolchain._get_link_command(flags)

    def run(self):
        """Execute the link command.

        Should be called by a builder worker then the command is ready to be executed.
        """
        print (f'LD  {self.flags.binary}', flush=True)
        self.execute(self.command, self.path)


class _DisasCommand(gvrun.commands.Command):
    """
    Command for generating a disassembly (.s) and a size report (.size) of a linked binary.

    Once created, the command is enqueued to the builder in order to be scheduled, and called
    when one of the workers wants to execute it. It is meant to be triggered by the link command
    of the binary so that it only runs once the binary is up to date.

    Attributes
    ----------
    builder : Builder
        Builder where commands should be enqueued.
    toolchain: Toolchain
        Toolchain used for generating the disassembly and size report
    binary: str
        Path of the binary to disassemble
    """
    def __init__(self, builder: Builder, toolchain: Toolchain, binary: str):
        super().__init__(builder)

        self.toolchain = toolchain
        self.binary = binary
        # Remember the current path to execute the commands from there in case some
        # files are using relative path
        self.path = os.getcwd()

    def __dump(self, cmd: str, out_path: str, mode: str = 'w') -> int:
        proc = subprocess.run(cmd.split(), cwd=self.path, text=True, capture_output=True)
        with open(out_path, mode) as out_file:
            _ = out_file.write(proc.stdout)
        if proc.stderr:
            _ = sys.stderr.write(proc.stderr)
        return proc.returncode

    def run(self):
        """Execute the disassembly, size and nm commands.

        Should be called by a builder worker then the command is ready to be executed.
        """
        print (f'DISAS {self.binary}.s', flush=True)
        retval = self.__dump(self.toolchain._get_disas_command(self.binary), f'{self.binary}.s')

        print (f'SIZE  {self.binary}.size', flush=True)
        retval = self.__dump(self.toolchain._get_size_command(self.binary),
            f'{self.binary}.size', mode='w') or retval
        retval = self.__dump(self.toolchain._get_nm_command(self.binary),
            f'{self.binary}.size', mode='a') or retval

        self.retval: int = retval
        self.command_done()
        self.builder.command_done(self)

    @override
    def get_retval(self) -> int:
        return self.retval


@dataclasses.dataclass
class _Define:
    """
    Container for defines

    Attributes
    ----------
    name (str): The name of the define.
    value (str | None): The value of the define. Can be None in case it has no value.
    internal (bool): True if the define should be used when compiling the sources of the container
        of the define.
    external (bool): True if the define should be used when compiling sources of a container using
        the container of the define.
    """
    name: str
    value: str | int | None = None
    internal: bool = False
    external: bool = False


@dataclasses.dataclass
class _Include:
    """
    Container for include folders

    Attributes
    ----------
    name (str): The path of the folder to be included.
    internal (bool): True if the include path should be used when compiling the sources of the
        container of the define.
    external (bool): True if the include path should be used when compiling sources of a container
        using the container of the define.
    """
    name: str
    internal: bool = False
    external: bool = False


@dataclasses.dataclass
class SourceCode:
    """
    A source file with its resolved absolute path.

    Attributes
    ----------
    name (str): The relative source name as provided (used for output object path).
    path (str | None): The eagerly resolved absolute path, or None if not yet resolved.
    """
    name: str
    path: str | None = None


class TemplateFile():
    """
    Container for template files

    A template file is a file which is used as a template to generate build-time files.
    Properties of the form @name@ can be attached to replace with runtime values.

    Attributes
    ----------
    name (str): The name of the template file
    parent (str): The source container owning this template
    path (str): The path of the generated file
    template (str): The path of the template file
    """
    def __init__(self, name: str, parent: "SourceContainer", path: str, template: str):
        self.path = path
        self.parent = parent
        self.template = template
        self.parameters: dict[str, bool | int | str] = {}
        parent._add_template_file(name, self)

    def add_parameter(self, name: str, value: bool | int | str):
        """Add a parameter.

        Any string in the template file of the form @name@ will be replaced by the specified value.

        Parameters
        ----------
        name (str): Name of the property. Any string of the form @name@ in the template will be
            replaced by the value
        value (Any): Value to be put in the generated file instead of the property.
        """
        self.parameters[name] = value

    def get_path(self):
        """Get the path of the generated file.

        Returns
        -------
        str
            The generated path.
        """
        return self.path

    def _gen(self):
        """Generate the output file

        Properties are replaced by their value in the template file and the output file is generated
        """
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        loaded_config = None
        if os.path.exists(self.path):
            with open(self.path, 'r') as file:
                loaded_config = file.read()

        with open(self.parent._get_source_path(self.template), 'r') as file:
            content = file.read()

            for prop_name, prop_value in self.parameters.items():
                content = content.replace(f'@{prop_name}@', str(prop_value))

        if content != loaded_config:
            with open(self.path, 'w') as file:
                file.write(content)

class TargetGenModule(Protocol):
    """Protocol for modules that can generate target-specific files.

    This protocol defines the interface for modules that implement target generation.
    Modules implementing this protocol should provide a target_gen method that is called
    during the build process to generate any target-specific configuration or source files.
    """

    def target_gen(self, container: "SourceContainer") -> None: ...
    """Generate target-specific files for the given source container.
    """

    def declare(self, target: SystemTreeNode, container: "SourceContainer") -> None: ...
    """Declare all the content to the source container.
    """

class _ModuleImportNode:
    """
    Container for imported module

    This class is used to build a tree of all the imported modules of the build process.
    This can then be used to go through them, for example for target_gen command.

    Attributes
    ----------
    module (_ModuleImportNode | None): Path of the imported module
    """
    def __init__(self, module: TargetGenModule | None=None):
        self.module:TargetGenModule | None = module
        self.subdirs: dict[str, "_ModuleImportNode"] = {}

    def add_node(self, path: str, module: "_ModuleImportNode"):
        """Add a child node

        This should be called by a new config file is imported from the current module.

        Parameters
        ----------
        path (str): Path of the imported module
        module (_ModuleImportNode): Node representing the imported module
        """
        self.subdirs[path] = module

    def target_gen(self, container: "SourceContainer", builddir: str):
        """Generate target-specific files for this module and all subdirectories.

        This method recursively traverses the module import tree and calls the target_gen
        method on each imported module that implements it. This allows each module in the
        build hierarchy to generate any target-specific configuration or source files needed
        for the build process.

        Parameters
        ----------
        container : SourceContainer
            The source container for which to generate target-specific files.
        builddir : str
            The build directory path where generated files should be placed.
        """
        if self.module is not None and hasattr(self.module, 'target_gen'):
            self.module.target_gen(container)

        for subdir in self.subdirs.values():
            subdir.target_gen(container, builddir)

class SourceContainer(SystemTreeNode):
    """
    Container for sources

    Any kind of source container must inherit from this class. This can be executable, module,
    library and so on.

    Attributes
    ----------
    name (str): Name of the container. This name will contribute to the path of the container within
        the system tree.
    target (SystemTreeNode | None): Target this container is attached to. The target can be
        used to query information about the target.
    parent (SystemTreeNode | None): Parent of this container within the system tree. The
        parent can be either another source container or an architectural component.
    """

    def __init__(self, name: str, target: SystemTreeNode | None=None,
            parent: SystemTreeNode | None=None,
            parameters:list[tuple[str,Any]] | None=None):
        super().__init__(name, parent=parent)

        # Nodes parameters must be registered with global path so that any parameter declared
        # with same global name has it value overwritten by the node parameter
        if parameters is not None:
            node_parameters = []
            for parameter in parameters:
                node_parameters.append((self.get_path(parameter[0]), parameter[1]))
            set_parameters_from_node(node_parameters)

        self.__sources = []
        self.__source_paths = []
        self.__cflags = []
        self.__ldflags = []
        self.__lib_includes = []
        self.__defines = []
        self.__includes = []
        self.__template_files = {}
        self.__build_steps = []
        # Stack of included config path, used to determine absolute path of the config files
        self.__path_stack: deque[str] = collections.deque()
        self.__toolchain = None
        self.__optim_level = None
        self.__current_dir = os.getcwd()
        self.__subdirs_tree_stack: deque[_ModuleImportNode] = collections.deque()
        self.__subdirs_top = _ModuleImportNode()
        self.__subdirs_tree_stack.append(self.__subdirs_top)
        self.__config: Config | None = None

    def set_config(self, config: Config):
        """Set the target configuration for this source container.

        During compilation, the configuration is used to generate C headers (under a ``config/``
        subdirectory of the build directory) containing target-specific preprocessor definitions.
        These headers are automatically added to the include path so that all sources in this
        container can access target characteristics at compile time.

        Parameters
        ----------
        config : Config
            The target configuration object whose ``generate_headers`` method will be called
            at build time to emit the headers.
        """
        self.__config = config

    def add_build_step(self, callback):
        """Register a build-time generation step.

        The callback is invoked during the compile phase (``gvrun compile`` / ``build``),
        before this container's sources are gathered and compiled. Use it to generate
        sources (or other build artifacts) that must exist before compilation, e.g. by
        running an external code generator. Unlike work done in ``config.py``'s
        ``declare()`` (which runs for every gvrun command), a build step runs only when
        the target is actually built.

        The callback receives the build directory as its only argument.

        Parameters
        ----------
        callback (Callable[[str], None]): The build step. Called once per compile with
            the build directory path.
        """
        self.__build_steps.append(callback)

    def _run_build_steps(self, builddir: str):
        """Run the registered build steps. Reserved for internal usage."""
        for callback in self.__build_steps:
            callback(builddir)

    def set_toolchain(self, toolchain: Toolchain):
        """Set the toolchain.

        The specified toolchain will be used to compile and link all the sources contained
        by this source container.

        Parameters
        ----------
        toolchain (Toolchain): Toolchain to be used.
        """
        self.__toolchain = toolchain

    def new_template_file(self, name: str, path: str, template: str) -> TemplateFile:
        """Declare a new template file.

        This will generate in the build folder a new file out of the specified template file
        where each attached property is used to replace any string of the form @name@ by the
        property value.

        Parameters
        ----------
        name (str): Name of the template file. This name is just used to reference the template
            file within its container
        path (str): Relative path of the generated file. This will be prefixed by the build folder
        template (str): Path of the template file
        """
        builddir = self.get_parameter('/builddir')
        if builddir is None:
            builddir = os.getcwd()
        propfile = TemplateFile(name, self, os.path.join(builddir, path),
            template)
        return propfile

    def add_define(self, name: str, value: str | int, internal: bool=True, external: bool=True):
        """Add a define.

        The define is attached to the container.
        If internal is True, it is defined when compiling sources inside the container.
        If external is True, it is defined when compiling sources depending on this container.

        Parameters
        ----------
        name (str): The name of the define.
        value (str | int | None): The value of the define. Can be None in case it has no value.
        internal (bool): True if the define should be used when compiling the sources of the
            container of the define.
        external (bool): True if the define should be used when compiling sources of a container
            using the container of the define.
        """
        self.__defines.append(_Define(name, value, internal, external))

    def add_includes(self, includes: list[str] | str, internal: bool=True, external:bool=True):
        """Add an include folder.

        This can be either a single include folder or a list of folders.
        The folders are attached to the container.
        If internal is True, they are included when compiling sources inside the container.
        If external is True, they are included when compiling sources depending on this container.

        Parameters
        ----------
        includes (list[str] | str): The set of include folders.
        internal (bool): True if the include paths should be used when compiling the sources of the
            container of the define.
        external (bool): True if the include paths should be used when compiling sources of a
            container using the container of the define.
        """
        if isinstance(includes, list):
            for include in includes:
                self.__includes.append(_Include(include, internal, external))
        else:
            self.__includes.append(_Include(includes, internal, external))

    def set_optimization_level(self, level: str):
        """Set optimization level.

        The optimization level will be applied for this container and any child container which
        does not have any optimization level

        Parameters
        ----------
        level (str): The optimization level, e.g. -O3. It will be passed as it is to the compiler.
        """
        self.__optim_level = level

    def add_cflags(self, cflags: list[str] | str):
        """Add CFLAGS.

        The CFLAGS are for now applied to all sources included in the executable.
        CFLAGS can be a single string or a list of strings.

        Parameters
        ----------
        cflags (list[str] | str): The set of CFLAGS.
        """
        if isinstance(cflags, list):
            self.__cflags += cflags
        else:
            self.__cflags.append(cflags)

    def add_ldflags(self, ldflags: list[str] | str):
        """Add LDFLAGS.

        The LDFLAGS are for now applied to all sources included in the executable.
        LDFLAGS can be a single string or a list of strings.

        Parameters
        ----------
        ldflags (list[str] | str): The set of LDFLAGS.
        """
        if isinstance(ldflags, list):
            self.__ldflags += ldflags
        else:
            self.__ldflags.append(ldflags)

    def add_lib_includes(self, includes: list[str] | str):
        """Add library include paths.

        The library include paths are added to the link command to specify folders where to
        look for libraries.
        The includes can be a single folder or a list of folders.

        Parameters
        ----------
        includes (list[str] | str): The set of include folders.
        """
        if isinstance(includes, list):
            self.__lib_includes += includes
        else:
            self.__lib_includes.append(includes)

    def add_source_path(self, paths: list[str] | str):
        """Add a source path.

        Source paths are the folders where the builder will look for to get absolute paths
        of source codes.
        Paths can be a single folder or a list of folders

        Parameters
        ----------
        paths (list[str] | str): The set of source folders.
        """
        if isinstance(paths, list):
            self.__source_paths += paths
        else:
            self.__source_paths.append(paths)

    def add_sources(self, sources: list[str] | str):
        """Add sources to be compiled.

        Sources are attached to this container are are for now compiled withing the executable
        compilation.
        Sources can be a single file or a list of files.
        When called from within an imported subdirectory, sources can be specified relative to that
        subdirectory and will be eagerly resolved to absolute paths.

        Parameters
        ----------
        sources (list[str] | str): The set of sources.
        """
        if not isinstance(sources, list):
            sources = [sources]
        for source in sources:
            path = None
            if len(self.__path_stack) > 0:
                candidate = os.path.join(self.__path_stack[-1], source)
                if os.path.exists(candidate):
                    path = candidate
            self.__sources.append(SourceCode(source, path))

    def add_subdirectory(self, path: str, target: SystemTreeNode):
        """Add a subdirectory.

        The config file from the specified subdirectory is imported and its declare method
        is called.
        This can be used to organize the whole compilation as a hierarchy of folders.

        Parameters
        ----------
        path (str): The path of the folder containing the config file to be imported.
        target (SystemTreeNode): The target to be passed to the imported config.
        """
        logging.debug(f'{self._get_title(True)} Importing config (name: {path})')

        # If not already absolute, convert it to absolute
        if not os.path.isabs(path):
            # Either we already included a file and we take his path as base or it means
            # we are in the current folder
            if len(self.__path_stack) > 0:
                path = os.path.join(self.__path_stack[-1], path)
            else:
                path = os.path.join(os.getcwd(), path)

        file = os.path.join(path, 'config.py')

        module: TargetGenModule

        try:
            spec = importlib.util.spec_from_file_location(file, file)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Unable to load spec for {file}")
            module = importlib.util.module_from_spec(spec)
            sys.modules["module.name"] = module
            spec.loader.exec_module(module)

        except FileNotFoundError as _exc:
            raise RuntimeError(f'Unable to open test configuration file: {file}') from _exc

        self.__path_stack.append(path)

        # Register the imported module in the tree to be able to go through the modules later
        new_node = _ModuleImportNode(module)
        self.__subdirs_tree_stack[-1].add_node(path, new_node)
        self.__subdirs_tree_stack.append(new_node)
        self.__current_dir = path

        module.declare(target, self)

        _ = self.__subdirs_tree_stack.pop()

        _ = self.__path_stack.pop()

    @override
    def target_gen(self, builddir:str):
        """ Overrides the systree target_gen to propagate to imported modules
        """
        self.__subdirs_top.target_gen(self, builddir)

    def _get_title_from_type(self, type_name: str, full_path=False) -> str:
        """ Returns title for logging for specified type

        Returns a string containing the kind of node, class name and path which can be used to see
        where we are in the hierarchy when dumping logs.
        """
        if full_path:
            path = self.get_path()
        else:
            path = self.get_name()
        title = f'{type_name}({self.__class__.__name__})'
        if path is not None:
            title = f'{path}: ' + title
        return title

    def _get_title(self, full_path=False) -> str:
        """ Returns title for logging

        Returns a string containing the kind of node, class name and path which can be used to see
        where we are in the hierarchy when dumping logs.
        """
        return self._get_title_from_type('Container', full_path)

    def _add_template_file(self, name: str, file: TemplateFile):
        """Attach a template file to this container

        When this container is generated, all the attached template files will be generated.

        Parameters
        ----------
        name (str): Name of the template file
        file (TemplateFile): Template file to be added
        """
        self.__template_files[name] = file

    def _get_toolchain(self) -> Toolchain | None:
        """Returns the toolchain associated to this container
        """
        # Return the toolchain of this source container if it has one otherwise try
        # to get it from the parent
        if self.__toolchain is not None:
            return self.__toolchain

        parent = self._get_parent()
        if parent is not None and isinstance(parent, SourceContainer):
            return parent._get_toolchain()

        return None

    def _get_lib_includes(self) -> list[str]:
        """Return the list of library include folders
        """
        return self.__lib_includes

    def _get_ldflags(self) -> list[str]:
        """Return the list of LDFLAGS

        This go through all childs to find the whole set.
        """
        ldflags = []
        for child in self._get_childs():
            ldflags += child._get_ldflags()
        ldflags += self.__ldflags

        return ldflags

    def _get_cflags(self) -> list[str]:
        """Return the list of CFLAGS

        This go through all childs to find the whole set.
        """
        cflags = []
        for child in self._get_childs():
            cflags += child._get_cflags()
        cflags += self.__cflags

        return cflags

    def _get_optimization_level(self) -> str | None:
        """Return the optimization level for this container

        If this container does not have any optimization level, it will return the one from the
        parent.
        """
        if self.__optim_level is not None:
            return self.__optim_level

        parent: SystemTreeNode | None = self._get_parent()
        if parent is not None and isinstance(parent, SourceContainer):
            return parent._get_optimization_level()

        return None


    def _get_source_paths(self) -> list[str]:
        """Return the list of source include paths

        This go through all childs to find the whole set.
        """
        paths = []

        parent = self._get_parent()
        if parent is not None and isinstance(parent, SourceContainer):
            paths += parent._get_source_paths()

        paths += self.__source_paths

        return paths

    def _get_source_path(self, source: str) -> str:
        """Return the absolute path of a source file

        The specified file is searche into the source paths and the absolute path within the
        source path is returned.
        If the file is nto found in the source paths, its path is returned as it is.
        """
        source_paths = self._get_source_paths()

        for source_path in source_paths:
            path = os.path.join(source_path, source)
            if os.path.exists(path):
                return path

        return source

    def _get_sources(self) -> list[str]:
        """Returns the sources to be compiled

        This go through all childs to find the whole set.
        """
        sources = []
        for source in self.__sources:
            resolved = source.path if source.path is not None \
                else self._get_source_path(source.name)
            sources.append([source.name, resolved])

        for child in self._get_childs():
            sources += child._get_sources()

        return sources

    def _get_defines(self, internal: bool=False, external: bool=False) -> list[str]:
        """Returns the defines to be used for compiling

        This go through all childs to find the whole set.
        """
        defines = []
        for child in self._get_childs():
            defines += child._get_defines(internal=False, external=True)

        for define in self.__defines:
            if define.internal and internal or define.external and external:
                defines.append(define)

        return defines

    def _get_includes(self, internal: bool=False, external: bool=False) -> list[str]:
        """Returns the includes to be used for compiling

        This go through all childs to find the whole set.
        """
        includes = []
        for child in self._get_childs():
            includes += child._get_includes(internal=False, external=True)

        for include in self.__includes:
            if include.internal and internal or include.external and external:
                includes.append(include)

        return includes

    def _get_compile_commands(self, builder: Builder, builddir: str) \
            -> list[_CompileCommand]:
        """Returns the compile commands

        This go through all childs to find the whole set.
        """
        toolchain = self._get_toolchain()

        if toolchain is None:
            raise RuntimeError(
                f'{self._get_title(True)} Trying to compile without any toolchain attached')

        commands = []
        for source in self.__sources:
            deps = []
            source_path = source.path if source.path is not None \
                else self._get_source_path(source.name)
            path = os.path.join(builddir, source.name.rstrip('.c').rstrip('.S') + '.o')

            dep_file = os.path.join(builddir, source.name.rstrip('.c').rstrip('.S') + '.d')
            if os.path.exists(dep_file):
                with open(dep_file, 'r') as file:
                    content = file.read().replace("\\\n", " ")

                    for line in content.splitlines():
                        if ":" not in line:
                            continue

                        target, deps_str = line.split(":", 1)

                        deps += deps_str.split()
            else:
                deps.append(source_path)

            obj_timestamp = -1
            if os.path.exists(path):
                obj_timestamp = os.path.getmtime(path)

            # Recompile the source if it is missing or if any of its
            # dependencies is newer than the object. A source must be compiled
            # at most once per build: enqueuing one command per out-of-date
            # dependency would schedule several identical compilations writing
            # the same object file in parallel, racing each other (and ccache).
            needs_compile = False
            for dep in deps:
                if not os.path.exists(dep):
                    needs_compile = True
                    break

                if os.path.getmtime(dep) >= obj_timestamp:
                    needs_compile = True
                    break

            if needs_compile:
                cflags = self._get_cflags()

                optim_level = self._get_optimization_level()
                if optim_level is not None:
                    cflags.append(optim_level)

                cflags += toolchain.get_extra_cflags()

                flags = ToolchainCFlags(
                    builddir=builddir,
                    source_name=source.name,
                    source_path=source_path,
                    cflags=cflags,
                    includes=self._get_includes(internal=True),
                    defines=self._get_defines(internal=True)
                )

                commands.append(
                    _CompileCommand(builder, toolchain, flags)
                )

        return commands

    def _compile(self, builder: Builder, builddir: str):
        """Compile step for this container

        Generates associated template files
        """
        self._run_build_steps(builddir)

        if self.__config is not None:
            path = os.path.join(builddir, 'config')
            generate_headers(self.__config, path)
            self.add_includes(builddir)

        for propfile in self.__template_files.values():
            propfile._gen()


class PulposModule(SourceContainer):
    """
    Container for Pulpos module

    Any target should define a class which inherits from this one to customize it
    with target-dependent features and provide a fully featured Pulpos module to the application.

    Attributes
    ----------
    target (gvrun.target.Target): Target this container is attached to. The target can be
        used to query information about the target.
    parent (SourceContainer): Parent of this container within the system tree. The
        parent must be another source container.
    """

    def __init__(self, target: SystemTreeNode, parent: SourceContainer):
        super().__init__('pulpos', target, parent=parent)


    def _dump_tree(self, tree: rich.tree.Tree, inc_arch: bool, inc_build: bool, inc_target: bool,
            inc_attr: bool, inc_prop: bool):
        """Dump the tree of parameters, attributes and properties
        """
        if self._has_tree_content():
            new_tree = tree.add(
                self._dump_parameter_title(self.get_name(), 'Module', self.__class__.__name__))
            self._dump_node_parameters(new_tree, inc_arch, inc_build, inc_target, inc_attr,
                inc_prop)
            for child in self._get_childs():
                child._dump_tree(new_tree, inc_arch, inc_build, inc_target, inc_attr, inc_prop)

    def _get_title(self, full_path: bool=False):
        """Returns a title for this node suitable for logging
        """
        return self._get_title_from_type('Module', full_path)


class PulposExecutable(SourceContainer, Executable):
    """
    Container for Pulpos-based executable

    Any target should define a class which inherits from this one to customize it
    with target-dependent features and provide a fully featured Pulpos executable to the
    application.

    Attributes
    ----------
    name (str): Name of the executable
    target (SystemTreeNode): Target this container is attached to. The target can be
        used to query information about the target.
    parent (SourceContainer): Parent of this container within the system tree. The
        parent must be another source container.
    """

    def __init__(self, name: str, target: SystemTreeNode,
            parameters:list[tuple[str,Any]] | None=None):
        super().__init__(name, target=target, parent=target, parameters=parameters)
        self.__target = target
        builddir = self.get_parameter('/builddir')
        if builddir is None:
            builddir = os.getcwd()
        path = self.get_path()
        if path[0] == '/':
            path = path[1:]
        self.__builddir = os.path.join(builddir, path)
        self.__binary = os.path.join(self.__builddir, name)

        target._add_executable(self)

    def get_binary(self) -> str:
        """Get the executable binary.

        The compilation of the executable will produce a binary whose path can be retrieved by
        calling this function.

        Returns
        -------
        str: The binary path
        """
        return self.__binary

    def _dump_tree(self, tree: rich.tree.Tree, inc_arch: bool, inc_build: bool, inc_target: bool,
            inc_attr: bool, inc_prop: bool):
        """Dump the tree of parameters, attributes and properties
        """
        if self._has_tree_content():
            new_tree = tree.add(
                self._dump_parameter_title(self.get_name(), 'Executable', self.__class__.__name__))
            self._dump_node_parameters(new_tree, inc_arch, inc_build, inc_target, inc_attr,
                inc_prop)
            for child in self._get_childs():
                child._dump_tree(new_tree, inc_arch, inc_build, inc_target, inc_attr, inc_prop)

    def _get_title(self, full_path: bool=False) -> str:
        """Returns a title for this node suitable for logging
        """
        return self._get_title_from_type('Executable', full_path)

    def _compile(self, builder: Builder, builddir: str):
        """Compile the executable
        """

        # Run any registered build-time generators first so that generated sources
        # exist before they are gathered and stat'd below.
        self._run_build_steps(builddir)

        toolchain = self._get_toolchain()

        if toolchain is None:
            raise RuntimeError(
                f'{self._get_title(True)} Trying to link without any toolchain attached')

        commands = self._get_compile_commands(builder, self.__builddir)

        for child in self._get_childs():
            commands += child._get_compile_commands(builder, self.__builddir)

        do_link = len(commands) != 0 or not os.path.exists(self.__binary)

        if do_link:

            ldflags = self._get_ldflags()

            optim_level = self._get_optimization_level()
            if optim_level is not None:
                ldflags.append(optim_level)

            flags = ToolchainLdFlags(
                builddir=self.__builddir,
                binary=self.__binary,
                sources=self._get_sources(),
                ldflags=ldflags,
                includes=self._get_lib_includes()
            )

            link_command = _LinkCommand(builder=builder, toolchain=toolchain, flags=flags)

            if len(commands) != 0:
                for command in commands:
                    command.add_trigger(link_command)
                    builder.push_command(command)
            else:
                builder.push_command(link_command)

    def _dump_asm(self, builder: Builder, builddir: str):
        """Generate a disassembly (.s) and a size report (.size, objdump/size/nm) for
        this executable's binary.

        Meant to be called after the compile step, once the binary is up to date.
        """
        _ = builddir

        toolchain = self._get_toolchain()

        if toolchain is None:
            raise RuntimeError(
                f'{self._get_title(True)} Trying to dump asm without any toolchain attached')

        builder.push_command(_DisasCommand(builder=builder, toolchain=toolchain,
            binary=self.__binary))


def new_executable(name: str, target: SystemTreeNode,
        parameters:List[Tuple[str,Any]] | None=None):
    """Create a new executable

    This will create a new executable for the specified target.

    Parameters
    ----------
    name (str): Name of the executable.
    target (SystemTreeNode): Target for which this executable will be compiled.
    parameters (List[Tuple[str,Any]] | None): List of parameters for this executable. They will
    be applied as command-line parameters, but their name should be relative to this
    executable without the executable name.
    """
    target_name = target.get_target_name()
    if target_name is None:
        raise RuntimeError('Could not load Pulpos target config, the target has no target name')

    try:
        module = importlib.import_module('pulpos.' + target_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f'The target has no pulpos descriptor (target_name: {target_name}, missing module: pulpos.{target_name}.py)') from exc

    return module.new_executable(name, target, parameters=parameters)
