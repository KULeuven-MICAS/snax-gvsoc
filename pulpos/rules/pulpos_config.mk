# SPDX-License-Identifier: Apache-2.0
#
# PulpOS make flow — optional user pre-include.
# Include this at the TOP of an application Makefile to get hardware facts
# (HW_*) and config defaults (CONFIG_*) for ifeq/ifneq checks:
#
#     include $(PULPOS_HOME)/rules/pulpos_config.mk
#     ifeq ($(HW_CHIP_NAME),gap9)
#     APP_SRCS += gap9_specific.c
#     endif
#
# Safe to omit: pulpos.mk includes the same properties itself.

include $(dir $(abspath $(lastword $(MAKEFILE_LIST))))pulpos_target.mk
include $(BFORGE_PROPERTIES)
