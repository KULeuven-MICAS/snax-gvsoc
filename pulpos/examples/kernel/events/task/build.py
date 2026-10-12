# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from build_tree import *

os = builder.get_os()
builder.get_config('/gap9_build').opt_level = '3'
src = SourceContainer('test')
src.add('test.c')
os.add_executable_from_source(src)
