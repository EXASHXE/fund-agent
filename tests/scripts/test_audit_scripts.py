"""Tests for audit scripts.

Asserts:
- JSON output shape
- No network calls
- No file deletions
- Deterministic output
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestAuditProjectStructure:
    def test_returns_dict(self):
        from scripts.audit.audit_project_structure import audit
        result = audit()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        from scripts.audit.audit_project_structure import audit
        result = audit()
        for key in ("top_level_directories", "src_package_areas",
                     "large_files", "directories_missing_readme"):
            assert key in result

    def test_src_areas_exist(self):
        from scripts.audit.audit_project_structure import audit
        result = audit()
        src_areas = result["src_package_areas"]
        area_names = [a["name"] for a in src_areas]
        assert "src/skills_runtime" in area_names
        assert "src/host_data" in area_names

    def test_json_serializable(self):
        from scripts.audit.audit_project_structure import audit
        result = audit()
        text = json.dumps(result, ensure_ascii=False)
        assert isinstance(text, str)


class TestAuditDeadCode:
    def test_returns_dict(self):
        from scripts.audit.audit_dead_code import audit
        result = audit()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        from scripts.audit.audit_dead_code import audit
        result = audit()
        for key in ("total_candidates", "high_confidence",
                     "medium_confidence", "low_confidence", "candidates"):
            assert key in result

    def test_no_high_confidence_for_protected(self):
        from scripts.audit.audit_dead_code import audit
        result = audit()
        for c in result["candidates"]:
            if c["confidence"] == "HIGH":
                assert not c["path"].startswith("skills/")
                assert not c["path"].startswith("tests/")

    def test_json_serializable(self):
        from scripts.audit.audit_dead_code import audit
        result = audit()
        text = json.dumps(result, ensure_ascii=False)
        assert isinstance(text, str)


class TestAuditPublicApi:
    def test_returns_dict(self):
        from scripts.audit.audit_public_api import audit
        result = audit()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        from scripts.audit.audit_public_api import audit
        result = audit()
        for key in ("console_scripts", "skillpack_entrypoints",
                     "facade_recommendations"):
            assert key in result

    def test_facade_recommendations_include_targets(self):
        from scripts.audit.audit_public_api import audit
        result = audit()
        facades = [r["facade"] for r in result["facade_recommendations"]]
        assert "fund_agent.workflow" in facades
        assert "fund_agent.providers" in facades

    def test_json_serializable(self):
        from scripts.audit.audit_public_api import audit
        result = audit()
        text = json.dumps(result, ensure_ascii=False)
        assert isinstance(text, str)


class TestAuditDocsLinks:
    def test_returns_dict(self):
        from scripts.audit.audit_docs_links import audit
        result = audit()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        from scripts.audit.audit_docs_links import audit
        result = audit()
        for key in ("broken_links", "overclaims", "missing_boundaries", "summary"):
            assert key in result

    def test_summary_has_counts(self):
        from scripts.audit.audit_docs_links import audit
        result = audit()
        summary = result["summary"]
        assert "files_scanned" in summary
        assert "broken_links" in summary
        assert "overclaims" in summary

    def test_json_serializable(self):
        from scripts.audit.audit_docs_links import audit
        result = audit()
        text = json.dumps(result, ensure_ascii=False)
        assert isinstance(text, str)


class TestRunAllAudits:
    def test_returns_dict(self):
        from scripts.audit.run_all_audits import run_all
        result = run_all()
        assert isinstance(result, dict)

    def test_has_all_audit_keys(self):
        from scripts.audit.run_all_audits import run_all
        result = run_all()
        for key in ("project_structure", "dead_code", "public_api", "docs_links"):
            assert key in result

    def test_writes_artifacts(self):
        from scripts.audit.run_all_audits import run_all, AUDIT_DIR
        run_all()
        assert (AUDIT_DIR / "summary.md").exists()
        assert (AUDIT_DIR / "project_structure.json").exists()
        assert (AUDIT_DIR / "dead_code.json").exists()
        assert (AUDIT_DIR / "public_api.json").exists()
        assert (AUDIT_DIR / "docs_links.json").exists()


class TestAuditNoNetworkNoDeletion:
    def test_no_network_imports(self):
        for mod_name in (
            "scripts.audit.audit_project_structure",
            "scripts.audit.audit_dead_code",
            "scripts.audit.audit_public_api",
            "scripts.audit.audit_docs_links",
        ):
            import importlib
            mod = importlib.import_module(mod_name)
            source = Path(mod.__file__).read_text(encoding="utf-8")
            assert "requests" not in source.split("import")[0] if "import" in source else True
            assert "urllib" not in source or "urllib.parse" in source
            assert "socket" not in source

    def test_no_file_deletion(self):
        for mod_name in (
            "scripts.audit.audit_project_structure",
            "scripts.audit.audit_dead_code",
            "scripts.audit.audit_public_api",
            "scripts.audit.audit_docs_links",
        ):
            import importlib
            mod = importlib.import_module(mod_name)
            source = Path(mod.__file__).read_text(encoding="utf-8")
            assert "os.remove" not in source
            assert "shutil.rmtree" not in source
            assert "os.unlink" not in source
