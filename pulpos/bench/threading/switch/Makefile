# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

APP       = switch
APP_SRCS += test.c

# Match the gvrun flow (Gap9PulposExecutable), which enables the allocator
# and the filesystem for every executable.
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_ALLOC := 1
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_FS := 1

# The OS stays at its -O3 default; the gvrun flow pins its OS to -O3 too
# (config.py) so both flows measure the same kernel against one set of bench
# references.  Note: setting CONFIG_GAP9_BUILD_OS_OPT_LEVEL := s currently
# hangs at boot (tiny-data corruption suspected from -fdata-sections, under
# investigation).

include $(PULPOS_HOME)/rules/pulpos.mk
