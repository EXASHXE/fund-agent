"""Real synthetic E2E smoke test — not dry-run only.

Uses synthetic fixtures to run the actual E2E pipeline end-to-end.
Does not use real Alipay data or provider keys.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
E2E_PY = SCRIPTS_DIR / "fund_agent_e2e.py"

# Synthetic Alipay CSV (minimal valid structure)
SYNTHETIC_ALIPAY_CSV = """\
交易号,商户订单号,交易创建时间,付款时间,交易来源地,类型,交易对方,商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注
202606170001,ORDER001,2026-06-17 10:00:00,2026-06-17 10:00:05,其他,即时到账交易,天弘基金管理有限公司,天弘余额宝-20260617,1000.00,支出,交易成功,0.00,0.00,余额宝申购
202606170002,ORDER002,2026-06-17 11:00:00,2026-06-17 11:00:05,其他,即时到账交易,华夏基金管理有限公司,华夏半导体ETF联接A-20260617,500.00,支出,交易成功,0.00,0.00,基金申购
"""

# Synthetic investment plan
SYNTHETIC_INVESTMENT_PLAN_YAML = """\
plans:
  - plan_id: plan_001
    fund_code: "000001"
    fund_name: "华夏成长混合"
    amount: 500
    schedule:
      frequency: monthly
      day_of_month: 15
      start_date: "2026-01-01"
    execution_policy:
      assume_auto_execution: true
      confirmation_rules:
        settlement_days: 1
        require_nav_available: true
        expected_confirmation_date_offset_days: 3
    fee_policy:
      fee_source: unknown
    is_qdii: false
"""

# Synthetic NAV overrides
SYNTHETIC_NAV_OVERRIDES = {
    "000001": {
        "2026-06-15": 1.2345,
        "2026-06-16": 1.2350,
        "2026-06-17": 1.2360,
    }
}

# Synthetic profile overrides
SYNTHETIC_PROFILE_OVERRIDES = {
    "000001": {
        "fund_name": "华夏成长混合",
        "fund_type": "混合型",
        "manager": "张三",
        "benchmark": "沪深300指数",
        "tracking_index": "沪深300",
        "inception_date": "2020-01-01",
        "size_category": "中盘",
        "tags": ["混合", "成长"],
        "holdings": [
            {"name": "贵州茅台", "code": "600519", "industry": "白酒", "weight": 8.5},
            {"name": "宁德时代", "code": "300750", "industry": "新能源", "weight": 6.2},
        ],
        "benchmark_symbol": "000300.SS",
        "benchmark_name": "沪深300",
        "benchmark_provider": "sse",
        "asset_class": "equity",
    }
}

# Synthetic fee overrides
SYNTHETIC_FEE_OVERRIDES = {
    "000001": {
        "purchase_fee": 0.0015,
        "redemption_fee_tiers": [
            {"holding_days_max": 7, "fee_rate": 0.015},
            {"holding_days_max": 30, "fee_rate": 0.0075},
            {"holding_days_max": 365, "fee_rate": 0.005},
        ],
    }
}


def _setup_synthetic_workspace(tmp_dir: Path) -> Path:
    """Create synthetic private_data directory with all fixtures."""
    private_data = tmp_dir / "private_data"
    private_data.mkdir(parents=True, exist_ok=True)

    # Write Alipay CSV
    (private_data / "alipay_record_20260617_1200_1.csv").write_text(
        SYNTHETIC_ALIPAY_CSV, encoding="utf-8"
    )

    # Write investment plan
    (private_data / "investment_plan.private.yaml").write_text(
        SYNTHETIC_INVESTMENT_PLAN_YAML, encoding="utf-8"
    )

    # Write NAV/profile/fee overrides for build_fund_data_snapshot
    overrides_dir = tmp_dir / "overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / "nav_overrides.json").write_text(
        json.dumps(SYNTHETIC_NAV_OVERRIDES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (overrides_dir / "profile_overrides.json").write_text(
        json.dumps(SYNTHETIC_PROFILE_OVERRIDES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (overrides_dir / "fee_overrides.json").write_text(
        json.dumps(SYNTHETIC_FEE_OVERRIDES, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return private_data


@pytest.mark.slow
class TestE2ERunnerRealSmoke:
    """Real synthetic E2E smoke test — runs actual pipeline steps."""

    def test_python_e2e_with_synthetic_data(self, tmp_path):
        """Run the Python E2E orchestrator with synthetic data."""
        private_data = _setup_synthetic_workspace(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "real_portfolio_report.md"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)

        result = subprocess.run(
            [
                sys.executable, str(E2E_PY),
                "--as-of", "2026-06-17",
                "--skip-news",
                "--skip-akshare",
                "--private-data-dir", str(private_data),
                "--output-dir", str(output_dir),
                "--output-report", str(report_path),
                "--run-id", "test-smoke-001",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(REPO_ROOT),
        )

        # Should not crash
        assert result.returncode == 0, (
            f"E2E runner failed (exit={result.returncode}):\n"
            f"stdout: {result.stdout[:2000]}\n"
            f"stderr: {result.stderr[:2000]}"
        )

        # e2e_summary.json should exist
        summary_path = output_dir / "e2e_summary.json"
        assert summary_path.exists(), f"e2e_summary.json not found at {summary_path}"

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["run_id"] == "test-smoke-001"
        assert "steps_completed" in summary

        # Output should not contain raw private row content or API keys
        combined = result.stdout + result.stderr
        assert "api_key=" not in combined.lower() or "***REDACTED***" in combined
        assert "token=" not in combined.lower() or "***REDACTED***" in combined

    def test_normalized_transactions_output(self, tmp_path):
        """Verify normalized_transactions output exists when CSV is present."""
        private_data = _setup_synthetic_workspace(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)

        result = subprocess.run(
            [
                sys.executable, str(E2E_PY),
                "--as-of", "2026-06-17",
                "--skip-news",
                "--skip-akshare",
                "--private-data-dir", str(private_data),
                "--output-dir", str(output_dir),
                "--run-id", "test-norm-001",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(REPO_ROOT),
        )

        normalized_path = output_dir / "normalized_transactions.json"
        assert normalized_path.exists(), (
            f"normalized_transactions.json not found.\n"
            f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:1000]}"
        )

    def test_transaction_ledger_output(self, tmp_path):
        """Verify transaction_ledger output exists."""
        private_data = _setup_synthetic_workspace(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)

        result = subprocess.run(
            [
                sys.executable, str(E2E_PY),
                "--as-of", "2026-06-17",
                "--skip-news",
                "--skip-akshare",
                "--private-data-dir", str(private_data),
                "--output-dir", str(output_dir),
                "--run-id", "test-ledger-001",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(REPO_ROOT),
        )

        ledger_path = output_dir / "transaction_ledger.json"
        assert ledger_path.exists(), (
            f"transaction_ledger.json not found.\n"
            f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:1000]}"
        )

    def test_no_stale_round3_in_output(self, tmp_path):
        """Verify output does not reference stale round3 envelope paths."""
        private_data = _setup_synthetic_workspace(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)

        result = subprocess.run(
            [
                sys.executable, str(E2E_PY),
                "--as-of", "2026-06-17",
                "--skip-news",
                "--skip-akshare",
                "--private-data-dir", str(private_data),
                "--output-dir", str(output_dir),
                "--run-id", "test-staleref-001",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(REPO_ROOT),
        )

        # Check for stale references in actual pipeline output files, not temp paths
        combined = result.stdout + result.stderr
        # Remove temp paths that may coincidentally contain "round3" in directory names
        lines = combined.splitlines()
        non_path_lines = [
            line for line in lines
            if not any(p in line for p in [str(tmp_path), str(output_dir)])
        ]
        filtered = "\n".join(non_path_lines)
        assert "round3_" not in filtered
        assert "fund_analysis_input_envelope" not in filtered

    def test_python_e2e_help(self):
        """Verify --help works."""
        result = subprocess.run(
            [sys.executable, str(E2E_PY), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "--as-of" in result.stdout
        assert "--skip-news" in result.stdout
        assert "--private-data-dir" in result.stdout

    def test_python_e2e_dry_run(self, tmp_path):
        """Verify --dry-run works with custom dirs."""
        private_data = _setup_synthetic_workspace(tmp_path)
        output_dir = tmp_path / "output"

        result = subprocess.run(
            [
                sys.executable, str(E2E_PY),
                "--dry-run",
                "--as-of", "2026-06-17",
                "--private-data-dir", str(private_data),
                "--output-dir", str(output_dir),
            ],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "dry-run" in result.stdout.lower() or "would run" in result.stdout.lower()
