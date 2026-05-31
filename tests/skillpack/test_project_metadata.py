"""Project metadata sanity tests."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


PROJECT_ROOT = Path(__file__).parent.parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
VERSION_PATH = PROJECT_ROOT / "VERSION"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_pyproject_has_project_section():
    data = _pyproject()
    assert "project" in data


def test_project_name_is_fund_agent():
    assert _pyproject()["project"]["name"] == "fund-agent"


def test_project_version_matches_version_file():
    expected = VERSION_PATH.read_text(encoding="utf-8").strip()
    assert _pyproject()["project"]["version"] == expected


def test_requires_python_exists():
    assert "requires-python" in _pyproject()["project"]


def test_description_mentions_skill_pack_or_agent_plugin():
    desc = _pyproject()["project"]["description"].lower()
    assert "skill pack" in desc or "agent plugin" in desc
