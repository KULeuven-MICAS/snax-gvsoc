# SPDX-License-Identifier: Apache-2.0
#
# PulpOS make flow — shared target/install resolution.
# Included (guarded) by pulpos.mk and pulpos_config.mk; not meant to be
# included directly by application Makefiles.

ifndef PULPOS_RULES_RESOLVED
PULPOS_RULES_RESOLVED := 1

ifndef EL_SDK_HOME
$(error EL_SDK_HOME is not set. Run 'source sourceme.sh' from the SDK root before running make)
endif

# GVSOC_WORKDIR relocates the install tree (mirrors sourceme.sh).
ifneq ($(GVSOC_WORKDIR),)
PULPOS_INSTALL_DIR ?= $(GVSOC_WORKDIR)/install
else
PULPOS_INSTALL_DIR ?= $(EL_SDK_HOME)/install
endif
PULPOS_RULES_ROOT := $(PULPOS_INSTALL_DIR)/pulpos/rules

# Target selection: 'make target=<name>' wins, then the PULPOS_TARGET
# variable (command line or environment — an SDK's sourceme.sh can export a
# default so a plain 'make run' works).
PULPOS_TARGET := $(or $(target),$(PULPOS_TARGET))
ifeq ($(PULPOS_TARGET),)
$(error No target selected. Pass 'target=<name>' (e.g. make target=gap.gap9.evk) or export PULPOS_TARGET. Generated targets: $(notdir $(wildcard $(PULPOS_RULES_ROOT)/*)))
endif

PULPOS_TARGET_RULES_DIR := $(PULPOS_RULES_ROOT)/$(PULPOS_TARGET)
ifeq ($(wildcard $(PULPOS_TARGET_RULES_DIR)/bforge_target.mk),)
$(error No generated PulpOS make rules for target '$(PULPOS_TARGET)' under $(PULPOS_RULES_ROOT). Generated targets: $(notdir $(wildcard $(PULPOS_RULES_ROOT)/*)). Rebuild the SDK with TARGETS=$(PULPOS_TARGET))
endif

include $(PULPOS_TARGET_RULES_DIR)/bforge_target.mk

endif
