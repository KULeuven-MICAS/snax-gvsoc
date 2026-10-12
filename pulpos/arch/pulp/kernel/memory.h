// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

#ifndef PI_MEMORY_TINY
#define PI_MEMORY_TINY  __attribute__((section(".data_tiny"))) __attribute__((tiny))
#endif
