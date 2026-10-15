# Builds snax-csr from sw/ (../../common.mk) into build/sw/apps/snax-csr/.

APP = snax-csr
include ../../common.mk

$(ELF): $(APP_DIR)/src/$(APP).c $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
