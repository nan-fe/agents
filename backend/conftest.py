"""Pytest bootstrap: ensure `import app` works when cwd / PYTHONPATH differ (e.g. CI)."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
_backend_root = str(_BACKEND_ROOT)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)
