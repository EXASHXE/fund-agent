"""CI workflow gate consistency tests."""
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent.parent


def test_ci_yml_uses_test_ci_script():
    content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/test_ci.sh" in content


def test_ci_yml_has_fail_fast_false():
    data = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert data["jobs"]["test"]["strategy"]["fail-fast"] is False


def test_plugin_ci_yml_uses_fast_gate():
    content = (ROOT / ".github" / "workflows" / "plugin-ci.yml").read_text(encoding="utf-8")
    assert "check_plugin_gate_fast.sh" in content


def test_plugin_ci_yml_does_not_use_full_gate():
    content = (ROOT / ".github" / "workflows" / "plugin-ci.yml").read_text(encoding="utf-8")
    # plugin-ci should NOT run the full canonical gate (requires dev extras)
    lines = content.splitlines()
    for line in lines:
        if "check_plugin_gate" in line:
            assert "check_plugin_gate_fast.sh" in line, (
                f"plugin-ci references non-fast gate: {line.strip()}"
            )


def test_release_checklist_includes_canonical_commands():
    content = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    assert "check_plugin_gate.sh" in content


def test_readme_development_commands_match_gate():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "check_plugin_gate.sh" in content
