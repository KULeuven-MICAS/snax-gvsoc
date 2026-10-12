#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)

import os
from gvrun.parameter import BuildParameter


def declare(target, container):
    declare_folders(target, container)

    declare_flags(target, container)

    declare_log(target, container)

    for subdir in ['kernel', 'lib']:
        container.add_subdirectory(subdir, target)


def declare_folders(target, container):
    home = os.environ.get('PULPOS_HOME', '')

    container.add_includes([
        os.path.join(home, 'include'),
        home
    ])

    container.add_source_path(os.environ.get('PULPOS_HOME'))


def declare_log(target, container):
    BuildParameter(container, 'log', [], 'Logs to be enabled')
    BuildParameter(container, 'log.all', False, 'Enable all logs')
    BuildParameter(container, 'log.level', 'error', 'Log level')

    for log in container.get_parameter('log'):
        container.add_define(f'CONFIG_LOG_{log.upper()}', 1)

    if container.get_parameter('log.all'):
        container.add_define('CONFIG_LOG_ALL', 1)

    if container.get_parameter('log.level'):
        container.add_define('CONFIG_LOG_LEVEL', f'PI_LOG_{container.get_parameter("log.level").upper()}')


def declare_flags(target, container):
    platform = container.get_parameter('/platform')

    container.add_define(f'__PLATFORM_{platform.upper()}__', '1')

    if platform == 'gvsoc':
        container.add_includes(f'{os.environ.get("GVSOC_HOME")}/include/target')
        # GUI thread visualization. This is a pulpos/runtime concern, so the parameter is declared
        # here rather than in gvrun. config.py declare() runs for every gvrun command, so declaring
        # it on the top target makes it available both here at compile time (to enable the kernel's
        # gv_vcd thread hooks) and to the GVSoC model's gen_gui at run time (to emit the flame-chart
        # signals). The declaration is guarded so it is done only once even with several executables.
        if target.get_parameter('/gui-threads') is None:
            BuildParameter(target, 'gui-threads', False,
                'Enable GUI thread visualization: builds the kernel with the gv_vcd thread hooks '
                '(__GVSOC_GUI__) and makes the GVSoC GUI show one group per thread with its flame '
                'chart. Off by default to avoid any runtime overhead.')
        # Off by default to avoid runtime overhead; build with gui-threads=true to enable.
        if container.get_parameter('/gui-threads'):
            container.add_define('__GVSOC_GUI__', '1')

        # Stack checker: the kernel declares each stack it runs on (boot stack,
        # thread stacks, cluster-core stacks) to the simulator through
        # semihosting (gv_stack_set). The ISS then traps any SP write leaving
        # the declared range and dumps the stack usage as a trace event, which
        # the GUI shows as an analog signal. Same declaration scheme as
        # gui-threads above. Off by default to avoid the semihosting overhead
        # at boot and on each context switch / cluster fork.
        if target.get_parameter('/stack-check') is None:
            BuildParameter(target, 'stack-check', False,
                'Enable the gvsoc stack checker: the kernel declares each stack (boot, '
                'threads, cluster cores) to the simulator, which traps SP leaving the '
                'declared range and dumps stack usage as a trace event.')
        if container.get_parameter('/stack-check'):
            container.add_define('CONFIG_STACK_CHECK', '1')

    container.add_cflags([
        '-fdata-sections', '-ffunction-sections', '-fno-jump-tables'
    ])

    container.add_ldflags([
       '-Wl,--gc-sections', '-fno-eliminate-unused-debug-symbols', '-nostdlib'
    ])

    if container._get_toolchain().get_family() not in ['llvm']:
        container.add_ldflags([
            '-lgcc', '-nostartfiles'
        ])
    else:
        container.add_ldflags([
            '-mno-relax'
        ])
