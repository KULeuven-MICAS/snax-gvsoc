# Builds the DMA TCDM program, with forge/vecadd/include/'s headers (the
# streamer's and the shell's CSRs), from sw/ (../../common.mk) into
# build/sw/apps/dma-tcdm/, one ELF per case.

APP      = dma-tcdm
CASES    = dma_vs_reader
ELFS     = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
FORGE    = $(abspath $(CURDIR)/../../../forge/vecadd)
INCDIRS  = $(FORGE)/include
include ../../common.mk

$(BUILDDIR)/$(APP)-%.elf: $(APP_DIR)/src/$(APP).c $(wildcard $(FORGE)/include/*) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@
