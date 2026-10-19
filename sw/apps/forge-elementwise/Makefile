# Builds the GEN3 step 5 program for a generated elementwise accelerator
# (forge/$(DESIGN)/, a design point's hjson and headers from snax-forge) from
# sw/ (../../common.mk) into build/sw/apps/forge-elementwise/$(DESIGN)/. The
# fixture's include/ comes before sw/generated/, so its
# streamer_csr_addr_map.h is the one used; no snax-alu library. From the
# manifest: DATA_LEN (symbols.N) and BEATS (tasks[0].beats, the accelerator
# task's trip count), and LANES = DATA_LEN / BEATS, passed to the program as
# -DBEATS and -DLANES. data.h is snax-alu's datagen.py at MODE (0 add, 2 mul)
# and DATA_LEN, NumPy seed 0, as snax-shell's Makefile makes it.

APP      = forge-elementwise
DESIGN  ?= vecadd
MODE    ?= 0
FORGE    = $(abspath $(CURDIR)/../../../forge/$(DESIGN))
MANIFEST = $(FORGE)/manifest.json
DATA_LEN := $(shell python3 -c "import json; \
	print(json.load(open('$(MANIFEST)'))['symbols']['N'])")
BEATS    := $(shell python3 -c "import json; \
	print(json.load(open('$(MANIFEST)'))['tasks'][0]['beats'])")
ifeq ($(DATA_LEN),)
$(error no symbols.N in $(MANIFEST))
endif
ifeq ($(BEATS),)
$(error no tasks[0].beats in $(MANIFEST))
endif
LANES    := $(shell expr $(DATA_LEN) / $(BEATS))
ifneq ($(shell expr $(DATA_LEN) % $(BEATS)),0)
$(error N $(DATA_LEN) is not a multiple of the $(BEATS) beats in $(MANIFEST))
endif
BUILDDIR = $(SW_BUILD)/apps/$(APP)/$(DESIGN)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(FORGE)/include
include ../../common.mk

RISCV_CFLAGS += -DBEATS=$(BEATS) -DLANES=$(LANES)

DATA_H = $(BUILDDIR)/data.h
# One stamp per MODE, so a MODE change makes data.h again
MODE_STAMP = $(BUILDDIR)/mode.$(MODE)

$(MODE_STAMP): | $(BUILDDIR)
	rm -f $(BUILDDIR)/mode.*
	touch $@

# The manifest for DATA_LEN, the Makefile for the rest
$(DATA_H): $(APP_DIR)/../snax-alu/data/datagen.py $(MANIFEST) $(APP_DIR)/Makefile \
		$(MODE_STAMP) | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 -c "import sys, runpy, numpy as np; \
	np.random.seed(0); sys.argv = ['datagen.py', '--mode=$(MODE)', '--length=$(DATA_LEN)']; \
	runpy.run_path('$<', run_name='__main__')" > $@

# The manifest too, for -DBEATS and -DLANES
$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(MANIFEST) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
