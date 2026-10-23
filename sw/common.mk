# Copyright 2026 KU Leuven.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# What the programs in apps/ share (CI1): built for snax_forge (snax-forge's
# vecadd fixture's cluster) against the runtime and math library of sw/, with the include dirs,
# libraries, linker script and link flags of snax_cluster's sw/apps/common.mk
# at the pin; the cluster's generated headers come first. An app sets APP
# and, before including this file, its own INCDIRS, LIB_OBJS (objects
# linked first, as snax_cluster's app Makefile puts snax-alu-lib.o) and
# ELFS when it makes more than $(ELF); it gets APP_DIR (its folder),
# BUILDDIR (build/sw/apps/$(APP)), LIBS and the rules for them and the
# dumps. The libraries are made by `make -C sw`, so `make -C sw/apps/<name>`
# works on its own.

APP_DIR := $(abspath $(dir $(firstword $(MAKEFILE_LIST))))
SW      := $(abspath $(dir $(realpath $(lastword $(MAKEFILE_LIST)))))
CLUSTER  = snax_forge
SW_BUILD = $(abspath $(SW)/../build/sw)
BUILDDIR ?= $(SW_BUILD)/apps/$(APP)

# snax-alu's library and headers, for the apps that use them
ALU_INCDIR = $(SW)/snax/snax-alu/include
ALU_LIB    = $(SW_BUILD)/$(CLUSTER)/snax-alu-lib.o

RISCV_LDFLAGS += $(LIB_OBJS)

include $(SW)/toolchain.mk

# Each ELF's dependency file, beside it (included at the end), so an edited
# header relinks every program that includes it
RISCV_CFLAGS += -MMD -MP -MT $@ -MF $(@:.elf=.d)

SNRT_DIR    := $(SW)/snRuntime
RUNTIME_DIR := $(SW)/runtime/rtl-generic

INCDIRS += $(SW)/generated/$(CLUSTER)
INCDIRS += $(RUNTIME_DIR)/src
INCDIRS += $(RUNTIME_DIR)/../common
INCDIRS += $(SNRT_DIR)/api
INCDIRS += $(SNRT_DIR)/api/omp
INCDIRS += $(SNRT_DIR)/src
INCDIRS += $(SNRT_DIR)/src/omp
INCDIRS += $(SW)/deps/riscv-opcodes
INCDIRS += $(SW)/math/include

LIBS  = $(SW_BUILD)/libmath.a
LIBS += $(SW_BUILD)/$(CLUSTER)/libsnRuntime.a

RISCV_LDFLAGS += -L$(RUNTIME_DIR)
RISCV_LDFLAGS += -T$(SNRT_DIR)/base.ld
RISCV_LDFLAGS += $(addprefix -L,$(dir $(LIBS)))
RISCV_LDFLAGS += $(addprefix -l,$(patsubst lib%,%,$(notdir $(basename $(LIBS)))))

ELF   = $(BUILDDIR)/$(APP).elf
ELFS ?= $(ELF)

.PHONY: all clean FORCE
all: $(ELFS) $(ELFS:.elf=.dump)

# sw/Makefile decides whether they are up to date; a program relinks only
# when one changed.
$(LIBS) $(ALU_LIB): FORCE
	$(MAKE) -s --no-print-directory -C $(SW) $@

$(BUILDDIR):
	mkdir -p $@

$(BUILDDIR)/%.dump: $(BUILDDIR)/%.elf
	$(RISCV_OBJDUMP) -D $< > $@

clean:
	rm -rf $(BUILDDIR)

-include $(ELFS:.elf=.d)
