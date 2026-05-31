"""Thin CLI entrypoint — DEPRECATED (routes/services/agents/forecast deleted)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    pd.options.mode.string_storage = "python"
except ImportError:
    pass


def cmd_analyze(args):
    """DEPRECATED: routes deleted. No-op stub."""
    raise ImportError("legacy.routes deleted — cmd_analyze unavailable")


def main(argv=None):
    """DEPRECATED: routes deleted. No-op stub."""
    raise ImportError("legacy.routes deleted — CLI unavailable")


if __name__ == "__main__":
    main()
