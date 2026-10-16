# Builds the SG7 DMA TCDM program, with snax-alu's library and headers, from
# sw/ (../../common.mk) into build/sw/apps/dma-tcdm/, one ELF per case.

APP      = dma-tcdm
CASES    = dma_vs_reader
ELFS     = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
INCDIRS  = $(ALU_INCDIR)
LIB_OBJS = $(ALU_LIB)
include ../../common.mk

$(BUILDDIR)/$(APP)-%.elf: $(APP_DIR)/src/$(APP).c $(LIB_OBJS) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@
