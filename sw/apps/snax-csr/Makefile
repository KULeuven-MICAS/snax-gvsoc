# Builds snax-csr, with forge/vecadd_v1/include/'s headers (the streamer's and the
# shell's CSRs), from sw/ (../../common.mk) into build/sw/apps/snax-csr/.

APP     = snax-csr
FORGE   = $(abspath $(CURDIR)/../../../forge/vecadd_v1)
INCDIRS = $(FORGE)/include
include ../../common.mk

$(ELF): $(APP_DIR)/src/$(APP).c $(wildcard $(FORGE)/include/*) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
