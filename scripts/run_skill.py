#!/usr/bin/env python3
"""Thin wrapper around ``src.skillpack.run_skill``.

The actual implementation lives in :mod:`src.skillpack.run_skill`.
This wrapper exists so the bridge is runnable as a plain script
without manipulating ``sys.path`` or remembering the module name.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.skillpack.run_skill import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
