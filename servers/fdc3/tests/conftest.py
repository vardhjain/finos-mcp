from __future__ import annotations

import sys
from pathlib import Path

# `generate_intents.py` lives in scripts/ (not the installed package -- see its
# module docstring) but the drift test needs to import its `generate()` function.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
