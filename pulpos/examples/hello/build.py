# SPDX-FileCopyrightText: 2026 ETH Zurich, University of Bologna and EssilorLuxottica SAS
#
# SPDX-License-Identifier: Apache-2.0

from build_tree import SourceContainer
from build_tree.script_typing import *

os = builder.get_os()
src = SourceContainer('test')
src.add('test.c')
os.add_executable_from_source(src)
