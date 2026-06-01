"""CI workflow gate consistency tests."""
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).parent.parent.parent

def test_ci_yml_references_canonical_gate():
    content = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "check_plugin_gate.sh" in content

def test_plugin_ci_yml_references_canonical_gate():
    content = (ROOT / ".github" / "workflows" / "plugin-ci.yml").read_text()
    assert "check_plugin_gate.sh" in content

def test_release_checklist_includes_canonical_commands():
    content = (ROOT / "docs" / "release-checklist.md").read_text()
    assert "check_plugin_gate.sh" in content

def test_readme_development_commands_match_gate():
    content = (ROOT / "README.md").read_text()
    assert "check_plugin_gate.sh" in content
