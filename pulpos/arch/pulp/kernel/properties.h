// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once


/*
 * CHIP
 */

// Tell if the chip has a cluster
#define CHIP_HAS_CLUSTER              1
// Number of clusters
#define CHIP_NB_CLUSTER   1

// Tell if the chip has an L2 memory
#define CHIP_HAS_L2                   (1)
// Tell if the L2 memory has a multi-bank architecture
#define CHIP_HAS_L2_MULTI             (1)
// Tell if the chip has an alias to the L2 memory starting at 0
#define CHIP_HAS_ALIAS                1


/*
 * Fabric controller
 */

#define FC_CORE_ID     0

#define FC_IRQ_TIMER0_LO_EVT               (10)
#define FC_IRQ_TIMER0_HI_EVT               (11)
#define FC_IRQ_TIMER1_LO_EVT               (12)
#define FC_IRQ_TIMER1_HI_EVT               (13)
