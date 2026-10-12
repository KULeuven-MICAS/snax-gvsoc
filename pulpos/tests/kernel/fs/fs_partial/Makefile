# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

APP       = fs_partial
APP_SRCS += test.c

# Match the gvrun flow (Gap9PulposExecutable), which enables the allocator
# and the filesystem for every executable.
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_ALLOC := 1
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_FS := 1

# Bundle the test files into the readfs partition of the on-chip MRAM
# (the gvrun flow declares them in config.py).
APP_RUN_OPTIONS += --flash-property $(CURDIR)/files/lorem.txt@mram:readfs:files

include $(PULPOS_HOME)/rules/pulpos.mk
