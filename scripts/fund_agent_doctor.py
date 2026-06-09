#!/usr/bin/env python3
"""Thin wrapper around ``src.skillpack.doctor``.

The actual implementation lives in :mod:`src.skillpack.doctor`.
This wrapper exists so the doctor is runnable as a plain script
without manipulating ``sys.path`` or remembering the module name.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skillpack.doctor import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
