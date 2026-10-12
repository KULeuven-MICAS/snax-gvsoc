// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

// Do all the initializations required to have the system ready
void __pi_init_start();

// Stop everything, free resources and leave the platform with specified status
void __attribute((noreturn)) __pi_init_stop(int status);
