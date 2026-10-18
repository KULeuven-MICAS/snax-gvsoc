# Builds the GEN3 step 5 program for a generated elementwise accelerator
# (forge/$(DESIGN)/, snax-forge's GVSoC generator) from sw/ (../../common.mk)
# into build/sw/apps/forge-elementwise/$(DESIGN)/. The fixture's include/
# comes before sw/generated/, so its streamer_csr_addr_map.h is the one
# used; no snax-alu library. data.h is snax-alu's datagen.py at MODE (0 add,
# 2 mul) and DATA_LEN (the manifest's symbols.N), NumPy seed 0, as
# snax-shell's Makefile makes it.

APP      = forge-elementwise
DESIGN  ?= vecadd
MODE    ?= 0
FORGE    = $(abspath $(CURDIR)/../../../forge/$(DESIGN))
DATA_LEN := $(shell python3 -c "import json; \
	print(json.load(open('$(FORGE)/manifest.json'))['symbols']['N'])")
ifeq ($(DATA_LEN),)
$(error no symbols.N in $(FORGE)/manifest.json)
endif
BUILDDIR = $(SW_BUILD)/apps/$(APP)/$(DESIGN)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(FORGE)/include
include ../../common.mk

DATA_H = $(BUILDDIR)/data.h
# One stamp per MODE, so a MODE change makes data.h again
MODE_STAMP = $(BUILDDIR)/mode.$(MODE)

$(MODE_STAMP): | $(BUILDDIR)
	rm -f $(BUILDDIR)/mode.*
	touch $@

# The manifest for DATA_LEN, the Makefile for the rest
$(DATA_H): $(APP_DIR)/../snax-alu/data/datagen.py $(FORGE)/manifest.json $(APP_DIR)/Makefile \
		$(MODE_STAMP) | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 -c "import sys, runpy, numpy as np; \
	np.random.seed(0); sys.argv = ['datagen.py', '--mode=$(MODE)', '--length=$(DATA_LEN)']; \
	runpy.run_path('$<', run_name='__main__')" > $@

$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
