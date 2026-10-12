// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#if defined(CONFIG_BOARD_INC)

#define  __BOARD_INC(x) #x
#define  _BOARD_INC(x) __BOARD_INC(x)
#define  BOARD_INC(x) _BOARD_INC(x)

#include BOARD_INC(CONFIG_BOARD_INC)

#endif
