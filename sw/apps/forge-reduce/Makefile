# Builds the GEN3 step 6b program for a generated one-lane reduction
# (forge/$(DESIGN)/, snax-forge's GVSoC generator) from sw/ (../../common.mk)
# into build/sw/apps/forge-reduce/$(DESIGN)/. The fixture's include/ comes
# before sw/generated/, so its streamer_csr_addr_map.h is the one used; no
# snax-alu library. From the manifest: N (symbols.N), BEATS (tasks[0].beats,
# the accelerator task's trip count, N for one lane) and RATE
# (tasks[0].csrs.len, inputs per sum), passed to the program as -DBEATS and
# -DRATE. data.h is data/datagen.py at N and RATE, seed 0.

APP      = forge-reduce
DESIGN  ?= vsum
FORGE    = $(abspath $(CURDIR)/../../../forge/$(DESIGN))
MANIFEST = $(FORGE)/manifest.json
N        := $(shell python3 -c "import json; \
	print(json.load(open('$(MANIFEST)'))['symbols']['N'])")
BEATS    := $(shell python3 -c "import json; \
	print(json.load(open('$(MANIFEST)'))['tasks'][0]['beats'])")
RATE     := $(shell python3 -c "import json; \
	print(json.load(open('$(MANIFEST)'))['tasks'][0]['csrs']['len'])")
ifeq ($(N),)
$(error no symbols.N in $(MANIFEST))
endif
ifeq ($(BEATS),)
$(error no tasks[0].beats in $(MANIFEST))
endif
ifeq ($(RATE),)
$(error no tasks[0].csrs.len in $(MANIFEST))
endif
ifneq ($(N),$(BEATS))
$(error N $(N) is not the $(BEATS) beats in $(MANIFEST): forge-reduce runs one lane)
endif
ifneq ($(shell expr $(BEATS) % $(RATE)),0)
$(error the $(BEATS) beats are not a multiple of rate $(RATE) in $(MANIFEST))
endif
BUILDDIR = $(SW_BUILD)/apps/$(APP)/$(DESIGN)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(FORGE)/include
include ../../common.mk

RISCV_CFLAGS += -DBEATS=$(BEATS) -DRATE=$(RATE)

DATA_H = $(BUILDDIR)/data.h

# The manifest for N and RATE, the Makefile for the seed
$(DATA_H): $(APP_DIR)/data/datagen.py $(MANIFEST) $(APP_DIR)/Makefile | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 $< --length=$(N) --rate=$(RATE) --seed=0 > $@

# The manifest too, for -DBEATS and -DRATE
$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(MANIFEST) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
