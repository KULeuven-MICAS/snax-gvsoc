# SPDX-FileCopyrightText: 2026 ETH Zurich and University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0
#
# Authors: Germain Haugou (germain.haugou@gmail.com)
#          Martin Croome (croomem@essilor.fr)

"""
Mapping mixin types for the configuration system.

This module previously contained AddressMapping and InterruptMapping mixin
types.  Those have been removed in favour of the :class:`MemoryMapped` mixin
defined in :mod:`config_tree.config`.  Memory maps are now produced by
iterating over ``MemoryMapped`` instances in the config tree.
"""
