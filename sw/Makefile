# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Builds snax_cluster's software from the copy in sw/ (CI1, README.md) into
# build/sw/: libmath.a; per cluster, <cluster>/libsnRuntime.a (and for
# snax_alu_cluster_old snax-alu-lib.o); every plain test in tests/ (the 17
# of COPIED in sync.py) for snitch_cluster into tests/. Flags from
# toolchain.mk; include order and link flags as snax_cluster's
# sw/math/Makefile, runtime/common/common.mk, snax/snax-alu/Makefile and
# tests/Makefile at the pin. Each cluster's generated headers
# (generated/<cluster>/) come before the other include dirs. The apps are
# built by apps/<name>/Makefile (common.mk).

MK_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
SW     := $(abspath $(MK_DIR))
BUILD  := $(abspath $(SW)/../build/sw)

include $(SW)/toolchain.mk

.PHONY: all libs clean
all: libs tests

SNRT_DIR    = $(SW)/snRuntime
RUNTIME_DIR = $(SW)/runtime/rtl-generic
MATH_DIR    = $(SW)/math
CLUSTERS    = snitch_cluster snax_alu_cluster_old

# The math headers, in the order of every upstream Makefile that uses them
MATH_INCDIRS  = $(MATH_DIR)/arch/riscv64/
MATH_INCDIRS += $(MATH_DIR)/arch/generic
MATH_INCDIRS += $(MATH_DIR)/src/include
MATH_INCDIRS += $(MATH_DIR)/src/internal
MATH_INCDIRS += $(MATH_DIR)/include/bits
MATH_INCDIRS += $(MATH_DIR)/include

# Every rule below sets INCDIRS for its own targets; toolchain.mk turns them
# into -I flags in RISCV_CFLAGS when the recipe runs.
DEPFLAGS = -MMD -MP

###########
# libmath #
###########

MATH_SRCS = $(abspath $(wildcard $(MATH_DIR)/src/math/*.c))
MATH_OBJS = $(addprefix $(BUILD)/math/,$(addsuffix .o,$(basename $(notdir $(MATH_SRCS)))))
LIBMATH   = $(BUILD)/libmath.a

$(BUILD)/math/%.o: INCDIRS = $(MATH_INCDIRS)
$(BUILD)/math/%.o: $(MATH_DIR)/src/math/%.c
	@mkdir -p $(@D)
	$(RISCV_CC) $(RISCV_CFLAGS) $(DEPFLAGS) -c $< -o $@

$(LIBMATH): $(MATH_OBJS)
	$(RISCV_AR) $(RISCV_ARFLAGS) $@ $^

#########################################
# Runtime and snax-alu's lib, per cluster #
#########################################

# common.mk's include dirs; vendor/riscv-opcodes does not exist, as upstream
RUNTIME_INCDIRS  = $(SNRT_DIR)/src
RUNTIME_INCDIRS += $(SNRT_DIR)/api
RUNTIME_INCDIRS += $(SNRT_DIR)/src/omp
RUNTIME_INCDIRS += $(SNRT_DIR)/api/omp
RUNTIME_INCDIRS += $(SNRT_DIR)/vendor/riscv-opcodes
RUNTIME_INCDIRS += $(SW)/runtime/common
RUNTIME_INCDIRS += $(MATH_INCDIRS)

RUNTIME_OBJS = snitch_cluster_start.o snrt.o
RUNTIMES     = $(foreach c,$(CLUSTERS),$(BUILD)/$(c)/libsnRuntime.a)

# snax/snax-alu/Makefile's include dirs: common.mk's between its own and the
# runtime's (rtl-generic/include does not exist, as upstream)
ALU_LIB = $(BUILD)/snax_alu_cluster_old/snax-alu-lib.o
ALU_LIB_INCDIRS  = $(SW)/snax/snax-alu/include
ALU_LIB_INCDIRS += $(RUNTIME_INCDIRS)
ALU_LIB_INCDIRS += $(RUNTIME_DIR)/src
ALU_LIB_INCDIRS += $(RUNTIME_DIR)/include

define cluster_rules
$(BUILD)/$(1)/%.o: INCDIRS = $(SW)/generated/$(1) $(RUNTIME_INCDIRS)
$(BUILD)/$(1)/%.o: $(RUNTIME_DIR)/src/%.S
	@mkdir -p $$(@D)
	$$(RISCV_CC) $$(RISCV_CFLAGS) $$(DEPFLAGS) -c $$< -o $$@
$(BUILD)/$(1)/%.o: $(RUNTIME_DIR)/src/%.c
	@mkdir -p $$(@D)
	$$(RISCV_CC) $$(RISCV_CFLAGS) $$(DEPFLAGS) -c $$< -o $$@
$(BUILD)/$(1)/libsnRuntime.a: $(addprefix $(BUILD)/$(1)/,$(RUNTIME_OBJS))
	$$(RISCV_AR) $$(RISCV_ARFLAGS) $$@ $$^
endef
$(foreach c,$(CLUSTERS),$(eval $(call cluster_rules,$(c))))

$(ALU_LIB): INCDIRS = $(SW)/generated/snax_alu_cluster_old $(ALU_LIB_INCDIRS)
$(ALU_LIB): $(SW)/snax/snax-alu/src/snax-alu-lib.c
	@mkdir -p $(@D)
	$(RISCV_CC) $(RISCV_CFLAGS) $(DEPFLAGS) -c $< -o $@

###############
# Plain tests #
###############

# Every test in tests/ (sync.py's COPIED holds the list: those of
# runtime.yaml and standard-fp.yaml), for snitch_cluster, with
# tests/Makefile's include dirs and link flags
TESTS = $(basename $(notdir $(wildcard $(SW)/tests/*.c)))
TEST_ELFS = $(addprefix $(BUILD)/tests/,$(addsuffix .elf,$(TESTS)))
TEST_RUNTIME = $(BUILD)/snitch_cluster/libsnRuntime.a

TEST_INCDIRS  = $(SW)/generated/snitch_cluster
TEST_INCDIRS += $(RUNTIME_DIR)/src
TEST_INCDIRS += $(RUNTIME_DIR)/../common
TEST_INCDIRS += $(SNRT_DIR)/api
TEST_INCDIRS += $(SNRT_DIR)/api/omp
TEST_INCDIRS += $(SNRT_DIR)/src
TEST_INCDIRS += $(SNRT_DIR)/src/omp
TEST_INCDIRS += $(SNRT_DIR)/vendor/riscv-opcodes
TEST_INCDIRS += $(MATH_INCDIRS)

TEST_LDFLAGS  = -L$(RUNTIME_DIR)
TEST_LDFLAGS += -T$(SNRT_DIR)/base.ld
TEST_LDFLAGS += -L$(dir $(TEST_RUNTIME))
TEST_LDFLAGS += -lsnRuntime

$(BUILD)/tests/%.elf: INCDIRS = $(TEST_INCDIRS)
$(BUILD)/tests/%.elf: $(SW)/tests/%.c $(TEST_RUNTIME)
	@mkdir -p $(@D)
	$(RISCV_CC) $(RISCV_CFLAGS) $(DEPFLAGS) $(RISCV_LDFLAGS) $(TEST_LDFLAGS) $< -o $@

#########
# Rules #
#########

.PHONY: tests
tests: $(TEST_ELFS)

libs: $(LIBMATH) $(RUNTIMES) $(ALU_LIB)

clean:
	rm -rf $(BUILD)

-include $(wildcard $(BUILD)/*/*.d)
