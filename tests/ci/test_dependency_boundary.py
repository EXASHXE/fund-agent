"""Dependency boundary tests.

These tests guard the host-agnostic dependency policy:

- ``requirements.txt`` must be minimal (no provider SDKs).
- Provider SDKs may appear only in ``requirements-legacy.txt`` or
  in docs / tests as explicitly forbidden examples.
- ``package.json`` has zero runtime dependencies.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PROVIDER_SDKS = (
    "akshare",
    "finnhub",
    "tavily",
    "langchain",
    "langgraph",
    "openai",
    "anthropic",
    "firecrawl",
    "reddit",
    "streamlit",
)

MINIMAL_DEPS = (
    "pyyaml",
    "pytest",
)


def _read_lines(path: Path) -> list[str]:
    """Read non-blank, non-comment lines from a requirements-style file."""
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped.lower())
    return lines


# ---------------------------------------------------------------------------
# requirements.txt is minimal
# ---------------------------------------------------------------------------


def test_requirements_txt_exists():
    assert (ROOT / "requirements.txt").exists(), "requirements.txt is missing"


def test_requirements_txt_has_no_provider_sdks():
    """Default requirements.txt must not bundle any provider SDKs."""
    lines = _read_lines(ROOT / "requirements.txt")
    for line in lines:
        for sdk in PROVIDER_SDKS:
            assert sdk not in line, (
                f"requirements.txt must not include {sdk!r}; "
                f"provider SDKs belong in requirements-legacy.txt"
            )


# ---------------------------------------------------------------------------
# requirements-legacy.txt exists and houses provider SDKs
# ---------------------------------------------------------------------------


def test_requirements_legacy_txt_exists():
    assert (ROOT / "requirements-legacy.txt").exists(), (
        "requirements-legacy.txt is missing"
    )


def test_requirements_legacy_txt_is_marked_historical():
    """requirements-legacy.txt must warn that it is historical / reference-only."""
    text = (ROOT / "requirements-legacy.txt").read_text(encoding="utf-8").lower()
    markers = (
        "historical",
        "reference-only",
        "legacy",
        "not the default",
    )
    assert any(m in text for m in markers), (
        "requirements-legacy.txt must clearly mark itself as "
        "historical / reference-only"
    )


# ---------------------------------------------------------------------------
# Provider SDKs only in legacy or as forbidden examples
# ---------------------------------------------------------------------------


def test_provider_sdks_only_in_legacy_or_docs():
    """Provider SDK names must not appear in active src/ or skills_runtime/
    code as imports or dependencies. They may appear in requirements-legacy.txt
    and in doc comments / test assertions as forbidden examples."""
    active_dirs = [
        ROOT / "src" / "skills_runtime",
        ROOT / "src" / "skillpack",
        ROOT / "src" / "tools",
        ROOT / "src" / "schemas",
        ROOT / "src" / "graph",
    ]
    for active_dir in active_dirs:
        if not active_dir.exists():
            continue
        for py_file in active_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8").lower()
            # Strip docstrings and comments to check imports only
            for sdk in PROVIDER_SDKS:
                # Allow references in string literals / comments /
                # docstrings only (they're docs/test mentions, not
                # actual imports).
                if f"import {sdk}" in text or f"from {sdk}" in text:
                    # Check if it's a real import or just in a docstring
                    lines = text.splitlines()
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                            continue
                        if f"import {sdk}" in stripped or f"from {sdk}" in stripped:
                            if not stripped.startswith("#"):
                                assert False, (
                                    f"{py_file.relative_to(ROOT)}: "
                                    f"active runtime code imports {sdk!r} — "
                                    f"provider SDKs belong to host implementations"
                                )


# ---------------------------------------------------------------------------
# package.json has zero runtime dependencies
# ---------------------------------------------------------------------------


def test_package_json_has_zero_runtime_dependencies():
    """The npm package must not declare any runtime dependencies."""
    import json
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    deps = pkg.get("dependencies", {})
    assert not deps, (
        f"package.json must have zero runtime dependencies, got: {deps}"
    )
    # peerDependencies with optional true is acceptable
    peer = pkg.get("peerDependencies", {})
    if peer:
        meta = pkg.get("peerDependenciesMeta", {})
        for dep_name in peer:
            assert meta.get(dep_name, {}).get("optional") is True, (
                f"package.json peerDependency {dep_name!r} must be marked optional"
            )
