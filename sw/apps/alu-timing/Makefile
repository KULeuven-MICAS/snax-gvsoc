# Builds the SG4 ALU timing program, with snax-alu's library and headers,
# from sw/ (../../common.mk) into build/sw/apps/alu-timing/.

APP      = alu-timing
INCDIRS  = $(ALU_INCDIR)
LIB_OBJS = $(ALU_LIB)
include ../../common.mk

$(ELF): $(APP_DIR)/src/$(APP).c $(LIB_OBJS) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
