"""Centralized resource path resolution for fund-agent.

Provides deterministic path resolution for manifest, contract YAMLs,
skills docs, and other non-Python resources. Works from both repo-root
and non-repo-root current working directories when the source tree is
importable.

Rules:
- No runtime skill imports.
- No provider SDK imports.
- No network calls.
- No importlib.resources (keep it simple and deterministic).
"""

from __future__ import annotations

from pathlib import Path


_PACKAGE_ROOT_CACHE: Path | None = None


def package_root() -> Path:
    """Return the repository/package root containing skillpack/, skills/, docs/, examples/.

    Derived from the location of this file (``src/skillpack/resources.py``).
    The root is two levels up: ``src/skillpack/resources.py`` -> repo root.
    """
    global _PACKAGE_ROOT_CACHE
    if _PACKAGE_ROOT_CACHE is not None:
        return _PACKAGE_ROOT_CACHE
    _PACKAGE_ROOT_CACHE = Path(__file__).resolve().parents[2]
    return _PACKAGE_ROOT_CACHE


def resolve_resource_path(path: str | Path) -> Path:
    """Resolve a relative resource path from cwd first, then from package root.

    - If ``path`` is absolute and exists, return it unchanged.
    - If ``path`` is relative and exists under current working directory, prefer it.
    - Otherwise resolve relative to ``package_root()``.
    - If neither exists, return the package-root-relative path (caller decides
      whether to raise or handle).
    """
    p = Path(path)
    if p.is_absolute():
        return p
    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate
    root_candidate = package_root() / p
    if root_candidate.exists():
        return root_candidate
    return root_candidate


def resolve_manifest_path(path: str | Path | None = None) -> Path:
    """Resolve manifest path, defaulting to skillpack/fund-agent.skillpack.yaml."""
    if path is None:
        path = "skillpack/fund-agent.skillpack.yaml"
    return resolve_resource_path(path)


def resolve_skillpack_file(filename: str) -> Path:
    """Resolve skillpack/<filename>."""
    return resolve_resource_path(Path("skillpack") / filename)


def resource_exists(path: str | Path) -> bool:
    """Check whether a resource path resolves to an existing file."""
    return resolve_resource_path(path).exists()
