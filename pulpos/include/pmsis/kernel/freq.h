// SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
//
// SPDX-License-Identifier: Apache-2.0
//
// Authors: Germain Haugou (germain.haugou@gmail.com)

#pragma once

enum pi_freq_domain;

unsigned int pi_freq_set(enum pi_freq_domain domain, unsigned int freq);

unsigned int pi_freq_get(enum pi_freq_domain domain);

#if defined(CONFIG_FREQ_INC)
#include CONFIG_FREQ_INC
#endif
