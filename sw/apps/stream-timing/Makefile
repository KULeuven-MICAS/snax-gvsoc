# Builds the SG3 streamer timing program from sw/ (../../common.mk) into
# build/sw/apps/stream-timing/, one ELF per case. The streamer's CSR map
# comes from the cluster's generated headers.

APP   = stream-timing
CASES = zero_bound a_alone ab_other_banks ab_same_banks a_stride0
ELFS  = $(foreach c,$(CASES),$(BUILDDIR)/$(APP)-$(c).elf)
include ../../common.mk

$(BUILDDIR)/$(APP)-%.elf: $(APP_DIR)/src/$(APP).c $(SW)/generated/$(CLUSTER)/streamer_csr_addr_map.h $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) -DCASE_$* $(RISCV_LDFLAGS) $< -o $@
