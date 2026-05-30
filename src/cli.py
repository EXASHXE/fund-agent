"""Deprecated CLI stub.

The plugin core is loaded through skillpack manifests and skills_runtime.
This module is retained only so ``python -m src.cli`` fails with a clear
message instead of importing the legacy archive.
"""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Exit with guidance for host-agnostic plugin usage."""
    raise SystemExit(
        "src.cli is deprecated and is not part of the plugin contract. "
        "Load skillpack/fund-agent.skillpack.yaml and call src.skills_runtime "
        "from an external host."
    )


if __name__ == "__main__":
    main()
