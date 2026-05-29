"""DEPRECATED CLI compat shim — delegates to legacy CLI.

This file exists only for backward compatibility. All CLI logic lives in legacy/cli.py.
Use the new Research OS path: from src.core.research_os import run_research_task
"""
import warnings

warnings.warn(
    "src.cli is deprecated — CLI moved to legacy/cli.py. Use src.core.research_os.",
    DeprecationWarning,
    stacklevel=2,
)

from legacy.cli import main  # noqa: E402, F401

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
