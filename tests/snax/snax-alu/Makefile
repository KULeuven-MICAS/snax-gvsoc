# Builds snax_cluster's snax-alu app from the copy in this folder, against the
# runtime of the snax_cluster checkout beside this repo. That runtime must be
# built first for the same cluster:
#   make -C $(SNAX_CLUSTER)/target/snitch_cluster sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson
# Flags, include paths, linker script and libraries are those of snax_cluster's
# sw/apps/common.mk and sw/snax/snax-alu/Makefile at the pinned commit.

MK_DIR       := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
SNAX_CLUSTER ?= $(abspath $(MK_DIR)/../../../../snax_cluster)

APP      = snax-alu

# DATA_LEN unset: the checked-in data/data.h (100 elements) into build/.
# DATA_LEN=N: data.h made with datagen.py (NumPy seed 0, mode 0, N elements)
# into build/N/, and the ELF there (SG5). N must be a multiple of 4.
ifeq ($(DATA_LEN),)
BUILDDIR = $(MK_DIR)build
DATA_DIR = $(MK_DIR)data
else
BUILDDIR = $(MK_DIR)build/$(DATA_LEN)
DATA_DIR = $(BUILDDIR)
endif
DATA_H   = $(DATA_DIR)/data.h
LIB_OBJ  = $(BUILDDIR)/snax-alu-lib.o

# The library object goes first, as snax_cluster's app Makefile adds it before
# including the toolchain flags.
RISCV_LDFLAGS += $(LIB_OBJ)

SW_DIR      := $(SNAX_CLUSTER)/target/snitch_cluster/sw
include $(SW_DIR)/toolchain.mk

SNRT_DIR    := $(SNAX_CLUSTER)/sw/snRuntime
RUNTIME_DIR := $(SW_DIR)/runtime/rtl-generic
MATH_DIR    := $(SW_DIR)/math

INCDIRS += $(DATA_DIR)
INCDIRS += $(MK_DIR)include
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

$(LIB_OBJ): $(MK_DIR)lib/snax-alu-lib.c $(wildcard $(MK_DIR)include/*.h) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -c $< -o $@

ifneq ($(DATA_LEN),)
$(DATA_H): $(MK_DIR)data/datagen.py | $(BUILDDIR)
	PYTHONPATH=$(SNAX_CLUSTER)/util/sim python3 -c "import sys, runpy, numpy as np; \
	np.random.seed(0); sys.argv = ['datagen.py', '--mode=0', '--length=$(DATA_LEN)']; \
	runpy.run_path('$<', run_name='__main__')" > $@
endif

$(ELF): $(MK_DIR)src/$(APP).c $(DATA_H) $(LIB_OBJ) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $(MK_DIR)src/$(APP).c -o $@

$(DUMP): $(ELF)
	$(RISCV_OBJDUMP) -D $< > $@

clean:
	rm -rf $(BUILDDIR)
