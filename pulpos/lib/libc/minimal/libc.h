// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

// Early libc initialization to enable printf when the device is simple
void __pi_libc_init();

// Full lib initialization
int __pi_libc_start();

// Full lib deinitialization
void __pi_libc_stop();
