// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

/*
 * MEMORIES
 */

#define CHIP_L2_PRIV0_ADDR  ( 0x1c000000 )
#define CHIP_L2_PRIV0_SIZE  ( 0x00008000 )

#define CHIP_L2_PRIV1_ADDR  ( 0x1c008000 )
#define CHIP_L2_PRIV1_SIZE  ( 0x00008000 )

#define CHIP_L2_SHARED_ADDR  ( 0x1c010000 )
#define CHIP_L2_SHARED_SIZE  ( 0x00180000 )



/*
 * SOC PERIPHERALS
 */

#define SOC_PERIPHERALS_ADDR        ( 0x1A100000 )

#define SOC_FC_ITC_OFFSET           ( 0x00009800 )
#define SOC_FC_TIMER0_OFFSET        ( 0x0000B000 )
#define SOC_FC_TIMER1_OFFSET        ( 0x0000B800 )


#define SOC_FC_ITC_ADDR            ( SOC_PERIPHERALS_ADDR + SOC_FC_ITC_OFFSET )
#define SOC_FC_TIMER0_ADDR         ( SOC_PERIPHERALS_ADDR + SOC_FC_TIMER0_OFFSET )
#define SOC_FC_TIMER1_ADDR         ( SOC_PERIPHERALS_ADDR + SOC_FC_TIMER1_OFFSET )


#define SOC_FC_TIMER_SIZE           0x00000800

/*
 * TIMER
 */

#define SOC_FC_TIMER_SUB_ADDR(id, sub_id) (SOC_FC_TIMER0_ADDR + (id) * SOC_FC_TIMER_SIZE + (sub_id) * 4)
