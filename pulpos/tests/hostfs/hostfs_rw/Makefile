# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

APP       = hostfs_rw
APP_SRCS += test.c

# Match the gvrun flow (Gap9PulposExecutable), which enables the allocator
# and the filesystem for every executable.
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_ALLOC := 1
CONFIG_GAP9_BUILD_PULPOS_SW_KERNEL_SW_FS := 1

# Input served from the host via semi-hosting; output written into the build
# directory so it is writable and isolated per test run.
APP_DEFINES += -DHOSTFS_INPUT_PATH='"/host$(CURDIR)/files/input.txt"'
APP_DEFINES += -DHOSTFS_OUTPUT_PATH='"/host$(abspath $(BUILD_DIR))/hostfs_write.bin"'

include $(PULPOS_HOME)/rules/pulpos.mk
