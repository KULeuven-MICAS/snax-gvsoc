# Builds the SG2 DMA timing program against the runtime of the snax_cluster
# checkout beside this repo. That runtime must be built first for the same
# cluster:
#   make -C $(SNAX_CLUSTER)/target/snitch_cluster sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson
# Flags, include paths, linker script and libraries are those of snax_cluster's
# sw/apps/common.mk at the pinned commit, as in ../snax-alu/Makefile.

MK_DIR       := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
SNAX_CLUSTER ?= $(abspath $(MK_DIR)/../../../../snax_cluster)

APP      = dma-timing
BUILDDIR = $(MK_DIR)build
SW_DIR      := $(SNAX_CLUSTER)/target/snitch_cluster/sw
include $(SW_DIR)/toolchain.mk

SNRT_DIR    := $(SNAX_CLUSTER)/sw/snRuntime
RUNTIME_DIR := $(SW_DIR)/runtime/rtl-generic
MATH_DIR    := $(SW_DIR)/math

INCDIRS += $(MK_DIR)data
INCDIRS += $(RUNTIME_DIR)/src
INCDIRS += $(RUNTIME_DIR)/../common
INCDIRS += $(SNRT_DIR)/api
INCDIRS += $(SNRT_DIR)/api/omp
INCDIRS += $(SNRT_DIR)/src
INCDIRS += $(SNRT_DIR)/src/omp
INCDIRS += $(SNAX_CLUSTER)/sw/deps/riscv-opcodes
INCDIRS += $(SNAX_CLUSTER)/sw/math/include

LIBS  = $(MATH_DIR)/build/libmath.a
LIBS += $(RUNTIME_DIR)/build/libsnRuntime.a

RISCV_LDFLAGS += -L$(RUNTIME_DIR)
RISCV_LDFLAGS += -T$(SNRT_DIR)/base.ld
RISCV_LDFLAGS += $(addprefix -L,$(dir $(LIBS)))
RISCV_LDFLAGS += $(addprefix -l,$(patsubst lib%,%,$(notdir $(basename $(LIBS)))))

ELF     = $(BUILDDIR)/$(APP).elf
DUMP    = $(BUILDDIR)/$(APP).dump

.PHONY: all clean
all: $(ELF) $(DUMP)

$(BUILDDIR):
	mkdir -p $@

$(ELF): $(MK_DIR)src/$(APP).c $(MK_DIR)data/data.h $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $(MK_DIR)src/$(APP).c -o $@

$(DUMP): $(ELF)
	$(RISCV_OBJDUMP) -D $< > $@

clean:
	rm -rf $(BUILDDIR)
