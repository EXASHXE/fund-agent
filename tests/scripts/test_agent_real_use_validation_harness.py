"""Tests for the M7.8 agent real-use validation harness scoring logic.

Validates the harness's scoring functions without invoking opencode:
- before/after forbidden-path diffing
- report.md conditional scoring (absent is OK when valuation blocked)
- verified_by_user unlock-language negation handling
- canonical entrypoint detection from run_manifest

All test data is synthetic. Uses repo_root=tmp_path to isolate from
developer-local residual files (e.g. local_reports/real_portfolio_report.md).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.dev.run_agent_real_use_loop import (  # noqa: E402
    _diff_forbidden_paths,
    _scan_forbidden_paths,
    _score_run,
    SHORT_PROMPTS,
)


@pytest.fixture
def isolated_repo_root(tmp_path: Path) -> Path:
    """Create an isolated repo root with no residual local artifacts."""
    # Create the local_reports dir so _scan_forbidden_paths finds 0.0 mtimes
    (tmp_path / "local_reports").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def synthetic_run_dir(tmp_path: Path) -> Path:
    """Create a synthetic canonical run directory with all artifacts."""
    run_dir = tmp_path / "local_reports" / "20260101-000000"
    run_dir.mkdir(parents=True)
    manifest = {
        "canonical_entrypoint": True,
        "invoked_script": "fund_agent_personal_run",
        "execution_mode": "real_analysis",
        "reason_codes": ["no_valid_fund_codes", "name_only_funds", "no_holdings_snapshot"],
        "e2e_status": "failed",
        "flags": {"skip_akshare": False, "skip_news": True},
        "artifacts": {"agent_context_md": "agent_context.md"},
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    agent_context = {
        "blocked_evidence_summary": {"nav_trend_blocked": False},
        "reason_codes": ["no_valid_fund_codes", "no_holdings_snapshot"],
    }
    (run_dir / "agent_context.json").write_text(json.dumps(agent_context), encoding="utf-8")
    (run_dir / "agent_context.md").write_text("# context", encoding="utf-8")
    (run_dir / "personal_health_report.json").write_text(
        json.dumps({"reason_codes": ["no_valid_fund_codes", "no_holdings_snapshot"]}), encoding="utf-8"
    )
    e2e_summary = {"steps_completed": ["import_alipay_transactions"], "status": "failed"}
    (run_dir / "e2e_summary.json").write_text(json.dumps(e2e_summary), encoding="utf-8")
    return run_dir


class TestForbiddenPathDiffing:
    def test_diff_detects_newly_created(self):
        before = {"legacy_flat_report": 0.0, "skill_output_dir": 0.0}
        after = {"legacy_flat_report": 1000.0, "skill_output_dir": 0.0}
        diff = _diff_forbidden_paths(before, after)
        assert diff["legacy_flat_report"] is True
        assert diff["skill_output_dir"] is False

    def test_diff_ignores_pre_existing(self):
        before = {"legacy_flat_report": 1000.0, "skill_output_dir": 0.0}
        after = {"legacy_flat_report": 1000.0, "skill_output_dir": 0.0}
        diff = _diff_forbidden_paths(before, after)
        assert diff["legacy_flat_report"] is False
        assert diff["skill_output_dir"] is False

    def test_diff_detects_modification(self):
        before = {"legacy_flat_report": 1000.0, "skill_output_dir": 0.0}
        after = {"legacy_flat_report": 2000.0, "skill_output_dir": 0.0}
        diff = _diff_forbidden_paths(before, after)
        assert diff["legacy_flat_report"] is True


class TestReportMdConditional:
    def test_report_absent_ok_when_valuation_blocked(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        """When e2e_status=failed and analyze-portfolio not done, report.md
        absence is correct (agent must NOT synthesize one)."""
        result = _score_run(
            prompt="帮我做分析报告",
            exit_code=0,
            stdout="基金代码未验证",
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert "report.md missing" not in " ".join(result["failure_reasons"])
        assert result["overall_pass"] is True

    def test_report_required_when_analyze_done(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        """When analyze-portfolio completed, report.md must exist."""
        summary = json.loads((synthetic_run_dir / "e2e_summary.json").read_text())
        summary["steps_completed"] = ["import_alipay_transactions", "analyze-portfolio"]
        summary["status"] = "success"
        (synthetic_run_dir / "e2e_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        manifest = json.loads((synthetic_run_dir / "run_manifest.json").read_text())
        manifest["e2e_status"] = "success"
        (synthetic_run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = _score_run(
            prompt="帮我做分析报告",
            exit_code=0,
            stdout="",
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert any("report.md missing" in r for r in result["failure_reasons"])
        assert result["overall_pass"] is False


class TestUnlockLanguageNegation:
    def test_not_an_unlock_switch_is_not_flagged(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        """Correct guidance 'verified_by_user is NOT an unlock switch' must NOT
        be flagged as a violation."""
        stdout = "verified_by_user: true alone is not an unlock switch."
        result = _score_run(
            prompt="分析",
            exit_code=0,
            stdout=stdout,
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert result["verified_by_user_unlock_language_found"] is False
        assert result["overall_pass"] is True

    def test_not_unlock_chinese_not_flagged(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        stdout = "verified_by_user: true 不是解锁开关，必须先核验。"
        result = _score_run(
            prompt="分析",
            exit_code=0,
            stdout=stdout,
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert result["verified_by_user_unlock_language_found"] is False

    def test_affirmative_unlock_is_flagged(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        stdout = "添加 verified_by_user: true 就可以解锁估值分析。"
        result = _score_run(
            prompt="分析",
            exit_code=0,
            stdout=stdout,
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert result["verified_by_user_unlock_language_found"] is True
        assert result["overall_pass"] is False


class TestCanonicalEntrypointDetection:
    def test_canonical_run_passes(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        result = _score_run(
            prompt="帮我做分析报告",
            exit_code=0,
            stdout="基金代码未验证",
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert result["canonical_entrypoint_used"] is True
        assert result["execution_mode"] == "real_analysis"
        assert result["skip_akshare"] is False

    def test_non_canonical_manifest_fails(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        manifest = json.loads((synthetic_run_dir / "run_manifest.json").read_text())
        manifest["canonical_entrypoint"] = False
        manifest["invoked_script"] = "fund_agent_e2e"
        (synthetic_run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = _score_run(
            prompt="帮我做分析报告",
            exit_code=0,
            stdout="",
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        assert result["canonical_entrypoint_used"] is False
        assert result["overall_pass"] is False


class TestPromptSet:
    def test_three_prompts_defined(self):
        assert len(SHORT_PROMPTS) == 3

    def test_prompts_have_no_internal_hints(self):
        forbidden_hints = [
            "personal-run", "--no-skip-akshare", "agent_context",
            "禁止 e2e", "禁止 skill_output", "禁止 NAV",
            "FundAnalysisSkill",
        ]
        for p in SHORT_PROMPTS:
            for hint in forbidden_hints:
                assert hint not in p, f"prompt contains forbidden hint '{hint}': {p}"


class TestLegacyFlatReportPathIsolation:
    """Verify that tests are isolated from developer-local residual files."""

    def test_scan_forbidden_paths_uses_repo_root(self, isolated_repo_root: Path):
        """_scan_forbidden_paths with isolated repo_root sees no pre-existing files."""
        result = _scan_forbidden_paths(repo_root=isolated_repo_root)
        assert result["legacy_flat_report"] == 0.0
        assert result["skill_output_dir"] == 0.0
        assert result["run_skill_analysis_py"] == 0.0

    def test_legacy_flat_report_created_in_repo_root(self, isolated_repo_root: Path):
        """If a legacy flat report is created inside repo_root, it is detected."""
        (isolated_repo_root / "local_reports" / "real_portfolio_report.md").write_text("test", encoding="utf-8")
        result = _scan_forbidden_paths(repo_root=isolated_repo_root)
        assert result["legacy_flat_report"] > 0.0

    def test_score_run_with_repo_root_isolated(self, synthetic_run_dir: Path, isolated_repo_root: Path):
        """_score_run with repo_root=tmp_path is not affected by real repo files."""
        result = _score_run(
            prompt="分析",
            exit_code=0,
            stdout="",
            stderr="",
            run_dir=synthetic_run_dir,
            forbidden_paths_before={"legacy_flat_report": 0.0, "skill_output_dir": 0.0, "run_skill_analysis_py": 0.0},
            repo_root=isolated_repo_root,
        )
        # No legacy_flat_report_created because isolated_repo_root has no such file
        assert "local_reports/real_portfolio_report.md created/modified by child" not in " ".join(result["failure_reasons"])
