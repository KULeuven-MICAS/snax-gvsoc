# Builds the SG2 DMA timing program from sw/ (../../common.mk) into
# build/sw/apps/dma-timing/. data/data.h is checked in (README).

APP = dma-timing
INCDIRS = $(APP_DIR)/data
include ../../common.mk

$(ELF): $(APP_DIR)/src/$(APP).c $(APP_DIR)/data/data.h $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
