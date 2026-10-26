# Builds the program snax-forge generates for a design point:
# forge/$(DESIGN)/main.c, with the fixture's folder (its data.h) and include/
# (streamer_csr_addr_map.h, <instance>_csr.h, snitch_cluster_cfg.h,
# snitch_cluster_addrmap.h) before sw/generated/, from sw/ (../../common.mk)
# into build/sw/apps/forge/$(DESIGN)/, and links the design's own runtime:
# libsnRuntime.a built there against the fixture's two cluster headers
# (`make -C sw runtime`), so its stacks sit at the end of the design's L1,
# not the shared snax_forge runtime. No datagen: the data is the fixture's
# data.h. The ELF depends on every file of the fixture, so a refreshed
# fixture rebuilds it, and the runtime on the two headers. FORGE, when set, names another folder of the same
# form (snax-forge's out/gvsoc/<design>/), and FORGE_BUILD the ELF's folder
# for it, so its ELF never shares a path with a fixture's.

APP      = forge
DESIGN  ?= vecadd
FORGE   ?= $(abspath $(CURDIR)/../../../forge/$(DESIGN))
ifeq ($(wildcard $(FORGE)/main.c),)
$(error no main.c in $(FORGE): refresh the fixture from snax-forge (forge/README.md))
endif
CLUSTER_HEADERS = $(addprefix $(FORGE)/include/,snitch_cluster_cfg.h snitch_cluster_addrmap.h)
ifneq ($(words $(wildcard $(CLUSTER_HEADERS))),2)
$(error no include/snitch_cluster_cfg.h and include/snitch_cluster_addrmap.h in $(FORGE): \
refresh the fixture from snax-forge (forge/README.md))
endif
FORGE_BUILD ?= $(SW_BUILD)/apps/$(APP)/$(DESIGN)
BUILDDIR = $(FORGE_BUILD)
INCDIRS  = $(FORGE)
INCDIRS += $(FORGE)/include
include ../../common.mk

# The design's runtime in place of common.mk's shared one; RISCV_LDFLAGS
# reads LIBS when a recipe runs, so -L and -l follow
RUNTIME = $(FORGE_BUILD)/libsnRuntime.a
LIBS   := $(SW_BUILD)/libmath.a $(RUNTIME)

# sw/Makefile decides whether it is up to date (its objects depend on the
# two headers)
$(RUNTIME): FORCE
	$(MAKE) -s --no-print-directory -C $(SW) runtime RUNTIME_INC=$(FORGE)/include \
		RUNTIME_BUILD=$(FORGE_BUILD)

FIXTURE = $(wildcard $(FORGE)/* $(FORGE)/include/*)

$(ELF): $(FORGE)/main.c $(FIXTURE) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
