"""Tests for scripts/verify_install_discovery.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_install_discovery import (
    CANONICAL_SKILLS,
    MARKER_FILENAME,
    PRIMARY_SKILL,
    SUPPORTING_SKILLS,
    _check_manifest_roles,
    _check_native_skills,
    _check_plugin_file,
    _check_windows_path,
    run_verification,
)


def _setup_skills_dir(project: Path, skills: list[str] | None = None) -> None:
    skills_dir = project / ".opencode" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    if skills is None:
        skills = list(CANONICAL_SKILLS)
    for slug in skills:
        (skills_dir / slug).mkdir(parents=True, exist_ok=True)
        (skills_dir / slug / "SKILL.md").write_text(f"# {slug}\n", encoding="utf-8")


def _write_marker(project: Path) -> None:
    skills_dir = project / ".opencode" / "skills"
    marker = {
        "schema_version": "fund-agent.opencode-skills.v1",
        "plugin": "fund-agent",
        "version": "1.2.0",
        "skills": list(CANONICAL_SKILLS),
    }
    (skills_dir / MARKER_FILENAME).write_text(
        json.dumps(marker, indent=2) + "\n", encoding="utf-8"
    )


def test_native_skills_all_present(tmp_path: Path) -> None:
    _setup_skills_dir(tmp_path)
    _write_marker(tmp_path)
    result = _check_native_skills(tmp_path)
    assert result["ok"] is True
    assert not result["missing"]
    assert result["primary_ok"] is True
    assert result["supporting_ok"] is True
    assert result["marker_exists"] is True


def test_native_skills_missing_one(tmp_path: Path) -> None:
    _setup_skills_dir(tmp_path, skills=[s for s in CANONICAL_SKILLS if s != "news-research"])
    result = _check_native_skills(tmp_path)
    assert result["ok"] is False
    assert "news-research" in result["missing"]
    assert result["supporting_ok"] is False


def test_native_skills_missing_primary(tmp_path: Path) -> None:
    _setup_skills_dir(tmp_path, skills=[s for s in CANONICAL_SKILLS if s != PRIMARY_SKILL])
    result = _check_native_skills(tmp_path)
    assert result["ok"] is False
    assert PRIMARY_SKILL in result["missing"]
    assert result["primary_ok"] is False


def test_native_skills_no_marker(tmp_path: Path) -> None:
    _setup_skills_dir(tmp_path)
    result = _check_native_skills(tmp_path)
    assert result["ok"] is True
    assert result["marker_exists"] is False


def test_plugin_file_absent(tmp_path: Path) -> None:
    result = _check_plugin_file(tmp_path)
    assert result["exists"] is False
    assert result["ok"] is True


def test_plugin_file_present_valid(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".opencode" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_path = plugin_dir / "fund-agent.js"
    plugin_path.write_text("// fund-agent plugin for OpenCode\n", encoding="utf-8")
    result = _check_plugin_file(tmp_path)
    assert result["exists"] is True
    assert result["is_valid"] is True


def test_plugin_file_custom_tool_not_verifiable(tmp_path: Path) -> None:
    result = _check_plugin_file(tmp_path)
    assert result["custom_tool_verifiable"] is False
    assert "environment-dependent" in result["note"]


def test_manifest_roles(fund_agent_root: Path) -> None:
    result = _check_manifest_roles(fund_agent_root)
    assert result["ok"] is True
    assert result["primary_skill"] == PRIMARY_SKILL
    assert set(result["supporting_skills"]) == set(SUPPORTING_SKILLS)


def test_manifest_roles_missing_manifest(tmp_path: Path) -> None:
    result = _check_manifest_roles(tmp_path)
    assert result["ok"] is False
    assert "error" in result


def test_windows_path_warning(tmp_path: Path) -> None:
    posix_path = Path("/drives/c/Users/test/project")
    warning = _check_windows_path(posix_path, platform="win32")
    assert warning is not None
    assert "/drives/c" in warning


def test_windows_path_no_warning_normal(tmp_path: Path) -> None:
    warning = _check_windows_path(tmp_path, platform="linux")
    assert warning is None


def test_run_verification_skip_runtime(tmp_path: Path, fund_agent_root: Path) -> None:
    _setup_skills_dir(tmp_path)
    _write_marker(tmp_path)
    result = run_verification(
        project=tmp_path,
        fund_agent_root=fund_agent_root,
        skip_runtime=True,
    )
    assert result["ok"] is True
    assert result["native_skills"]["ok"] is True
    assert result["runtime_bridge"]["skipped"] is True


def test_run_verification_missing_skill(tmp_path: Path, fund_agent_root: Path) -> None:
    _setup_skills_dir(tmp_path, skills=["fund-analysis"])
    result = run_verification(
        project=tmp_path,
        fund_agent_root=fund_agent_root,
        skip_runtime=True,
    )
    assert result["ok"] is False
    assert len(result["errors"]) > 0


def test_run_verification_json_output(tmp_path: Path, fund_agent_root: Path) -> None:
    _setup_skills_dir(tmp_path)
    _write_marker(tmp_path)
    result = run_verification(
        project=tmp_path,
        fund_agent_root=fund_agent_root,
        skip_runtime=True,
    )
    text = json.dumps(result, default=str)
    parsed = json.loads(text)
    assert parsed["ok"] is True
    assert "native_skills" in parsed
    assert "plugin_file" in parsed
    assert "manifest_roles" in parsed
    assert "runtime_bridge" in parsed
    assert "warnings" in parsed
    assert "errors" in parsed


@pytest.fixture()
def fund_agent_root() -> Path:
    return Path(__file__).resolve().parents[2]
