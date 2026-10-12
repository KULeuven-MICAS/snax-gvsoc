from __future__ import annotations

import sys
from pathlib import Path

# Make sibling modules in this tests/ dir importable regardless of the
# directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
