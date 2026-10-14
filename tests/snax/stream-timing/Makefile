# Builds the SG3 streamer timing program against the runtime of the
# snax_cluster checkout beside this repo, one ELF per case. That runtime must
# be built first for the same cluster:
#   make -C $(SNAX_CLUSTER)/target/snitch_cluster sw CFG_OVERRIDE=cfg/snax_alu_cluster_old.hjson
# Flags, include paths, linker script and libraries are those of snax_cluster's
# sw/apps/common.mk at the pinned commit, as in ../snax-alu/Makefile.

MK_DIR       := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
SNAX_CLUSTER ?= $(abspath $(MK_DIR)/../../../../snax_cluster)

APP      = stream-timing
BUILDDIR = $(MK_DIR)build
CASES    = zero_bound a_alone ab_other_banks ab_same_banks a_stride0

SW_DIR      := $(SNAX_CLUSTER)/target/snitch_cluster/sw
include $(SW_DIR)/toolchain.mk

SNRT_DIR    := $(SNAX_CLUSTER)/sw/snRuntime
RUNTIME_DIR := $(SW_DIR)/runtime/rtl-generic
MATH_DIR    := $(SW_DIR)/math

# The streamer's CSR map, as snax-alu uses it
INCDIRS += $(MK_DIR)../snax-alu/include
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

ELFS  = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
DUMPS = $(ELFS:.elf=.dump)

.PHONY: all clean
all: $(ELFS) $(DUMPS)

$(BUILDDIR):
	mkdir -p $@

$(BUILDDIR)/$(APP)-%.elf: $(MK_DIR)src/$(APP).c $(MK_DIR)../snax-alu/include/streamer_csr_addr_map.h $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@

$(BUILDDIR)/%.dump: $(BUILDDIR)/%.elf
	$(RISCV_OBJDUMP) -D $< > $@

clean:
	rm -rf $(BUILDDIR)
