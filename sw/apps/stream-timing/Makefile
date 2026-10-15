# Builds the SG3 streamer timing program from sw/ (../../common.mk) into
# build/sw/apps/stream-timing/, one ELF per case.

APP   = stream-timing
CASES = zero_bound a_alone ab_other_banks ab_same_banks a_stride0 prio_queued idle_restart
ELFS  = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
include ../../common.mk

$(BUILDDIR)/$(APP)-%.elf: $(APP_DIR)/src/$(APP).c $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@
