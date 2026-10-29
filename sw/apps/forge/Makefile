# Builds the program snax-forge generates for a design point:
# forge/$(DESIGN)/main.c, with the fixture's folder (its data.h) and include/
# (streamer_csr_addr_map.h, <instance>_csr.h, snitch_cluster_cfg.h,
# snitch_cluster_addrmap.h) before sw/generated/, from sw/ (../../common.mk)
# into build/sw/apps/forge/$(DESIGN)/, and links a runtime built against the
# fixture's two cluster headers (`make -C sw runtime`), so its stacks sit at
# the end of the design's L1, not the shared snax_forge runtime. The headers
# differ between fixtures only in their comment lines, so the runtime is
# built once per distinct pair: in build/sw/apps/forge/runtime/<key>/, the
# key a hash of their lines but the comment ones, from a copy of the first
# pair with that key. No datagen: the data is the fixture's data.h. The ELF
# depends on every file of the fixture, so a refreshed fixture rebuilds it,
# and the runtime on the two headers. FORGE, when set, names another folder of the same
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
RUNTIME_KEY  := $(shell grep -hv '^[[:space:]]*//' $(CLUSTER_HEADERS) | sha256sum | cut -c1-16)
RUNTIME_KEYED := $(SW_BUILD)/apps/$(APP)/runtime/$(RUNTIME_KEY)
RUNTIME = $(RUNTIME_KEYED)/libsnRuntime.a
LIBS   := $(SW_BUILD)/libmath.a $(RUNTIME)

# The key's copy of the headers is never overwritten, so its objects stay up
# to date across fixtures; sw/Makefile decides whether they are (they depend
# on the two headers)
$(RUNTIME): FORCE
	@mkdir -p $(RUNTIME_KEYED)/include
	@cp -n $(CLUSTER_HEADERS) $(RUNTIME_KEYED)/include/
	$(MAKE) -s --no-print-directory -C $(SW) runtime RUNTIME_INC=$(RUNTIME_KEYED)/include \
		RUNTIME_BUILD=$(RUNTIME_KEYED)

FIXTURE = $(wildcard $(FORGE)/* $(FORGE)/include/*)

$(ELF): $(FORGE)/main.c $(FIXTURE) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
