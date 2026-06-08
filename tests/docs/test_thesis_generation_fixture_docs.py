"""Tests for thesis_generation fixture documentation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestThesisFixtureDocs:
    def test_readme_has_usage_commands(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "python scripts/run_skill.py --skill thesis_generation" in text
        assert "python scripts/run_skill.py --skill thesis-generation" in text

    def test_all_fixtures_parse_as_json(self):
        import json
        fixture_dir = ROOT / "examples" / "thesis_generation"
        for path in sorted(fixture_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "payload" in data, f"{path.name} missing payload envelope"

    def test_fixtures_use_payload_envelope(self):
        import json
        fixture_dir = ROOT / "examples" / "thesis_generation"
        for path in sorted(fixture_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "payload" in data, f"{path.name} missing payload"
            assert isinstance(data["payload"], dict), f"{path.name} payload is not dict"
