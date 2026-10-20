# Builds the core TCDM program from sw/ (../../common.mk) into
# build/sw/apps/core-tcdm/, one ELF per case.

APP   = core-tcdm
CASES = subword core_vs_reader after_stores
ELFS  = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
include ../../common.mk

$(BUILDDIR)/$(APP)-%.elf: $(APP_DIR)/src/$(APP).c $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@
