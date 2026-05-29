"""DEPRECATED CLI shim — re-exports legacy.cli with DeprecationWarning."""
import warnings

warnings.warn(
    "src.cli is deprecated. CLI entry point moved to legacy/cli.py",
    DeprecationWarning,
    stacklevel=2,
)

from legacy import cli as _legacy_cli

# Re-export the main entry point
main = _legacy_cli.main if hasattr(_legacy_cli, "main") else None

# Fallback: if old-style CLI used directly, delegate to legacy
if __name__ == "__main__":
    import sys
    from legacy.routes.cli_router import run_cli
    sys.exit(run_cli(sys.argv[1:]))
