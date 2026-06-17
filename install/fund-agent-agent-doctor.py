#!/usr/bin/env python3
"""Thin CLI entry point for ``install.doctor``.

Runnable as:
  python install/fund-agent-agent-doctor.py --target all
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from install.doctor import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
