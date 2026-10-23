# Builds the shell program, with forge/vecadd/include/'s headers (the
# streamer's and the shell's CSRs), from sw/ (../../common.mk) into
# build/sw/apps/snax-shell/. It runs on snax_hjson with
# forge/vecadd/snax_forge.hjson. data.h is data/datagen.py at DATA_LEN 192,
# seed 0: the data snax_cluster's snax-alu datagen.py gives for an add.

APP      = snax-shell
DATA_LEN = 192
FORGE    = $(abspath $(CURDIR)/../../../forge/vecadd)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(FORGE)/include
include ../../common.mk

DATA_H = $(BUILDDIR)/data.h

# The Makefile too, for DATA_LEN
$(DATA_H): $(APP_DIR)/data/datagen.py $(APP_DIR)/Makefile | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 $< --length=$(DATA_LEN) --seed=0 > $@

$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(wildcard $(FORGE)/include/*) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
