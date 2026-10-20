# Builds the program snax-forge generates for a design point:
# forge/$(DESIGN)/main.c, with the fixture's folder (its data.h) and include/
# (streamer_csr_addr_map.h, <instance>_csr.h) before sw/generated/, from sw/
# (../../common.mk) into build/sw/apps/forge/$(DESIGN)/. No datagen: the data is the fixture's
# data.h. The ELF depends on every file of the fixture, so a refreshed
# fixture rebuilds it. FORGE, when set, names another folder of the same
# form (snax-forge's out/gvsoc/<design>/).

APP      = forge
DESIGN  ?= vecadd
FORGE   ?= $(abspath $(CURDIR)/../../../forge/$(DESIGN))
ifeq ($(wildcard $(FORGE)/main.c),)
$(error no main.c in $(FORGE): refresh the fixture from snax-forge (forge/README.md))
endif
BUILDDIR = $(SW_BUILD)/apps/$(APP)/$(DESIGN)
INCDIRS  = $(FORGE)
INCDIRS += $(FORGE)/include
include ../../common.mk

FIXTURE = $(wildcard $(FORGE)/* $(FORGE)/include/*)

$(ELF): $(FORGE)/main.c $(FIXTURE) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
