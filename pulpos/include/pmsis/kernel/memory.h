// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#if defined(CONFIG_MEMORY_INC)
#include CONFIG_MEMORY_INC
#endif

/**
 * @brief Put a variable into the tiny section.
 *
 * This define puts the associated variable into the main processor tiny section. The tiny
 * section is a special section, close to address 0, which allows the compiler to consider the
 * variable as having a small address, and to apply optimizations.
 */
#ifndef PI_MEMORY_TINY
#define PI_MEMORY_TINY
#endif
