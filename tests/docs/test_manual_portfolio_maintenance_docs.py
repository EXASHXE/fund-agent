"""Tests for manual portfolio maintenance documentation (v0.10.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANUAL_MAINT_DOC = ROOT / "docs" / "development" / "manual-portfolio-maintenance.md"
PRIVATE_DATA_HANDLING_DOC = ROOT / "docs" / "development" / "private-data-handling.md"
PRIVATE_DATA_FLOW_DOC = ROOT / "docs" / "agent-integration" / "private-data-flow.md"
TEMPLATES_README = ROOT / "examples" / "user_portfolio_templates" / "README.md"


def _read_doc(path: Path) -> str:
    assert path.exists(), f"Document not found: {path}"
    return path.read_text(encoding="utf-8")


class TestManualPortfolioMaintenanceDoc:
    """Tests for docs/development/manual-portfolio-maintenance.md."""

    def test_doc_exists(self):
        assert MANUAL_MAINT_DOC.exists()

    def test_doc_mentions_raw_alipay_csv_not_committed(self):
        """Docs must explicitly state that raw Alipay CSV should not be committed."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "alipay" in text.lower() or "支付宝" in text
        # Must say not to commit raw Alipay CSV
        assert "never commit" in text.lower() or "不提交" in text or "不得提交" in text

    def test_doc_mentions_no_fund_code_guessing(self):
        """Docs must explicitly state not to guess fund_code."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "fund_code" in text or "基金代码" in text
        # Must say not to guess
        assert "不猜" in text or "不要猜" in text or "do not guess" in text.lower() or "leave" in text.lower() and "empty" in text.lower()

    def test_doc_mentions_no_fabricating_units_nav_cost_basis(self):
        """Docs must explicitly state not to fabricate units/NAV/cost_basis."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "units" in text.lower() or "份额" in text
        assert "cost_basis" in text.lower() or "成本" in text
        assert "nav" in text.lower() or "净值" in text
        # Must say not to fabricate
        assert "fabricat" in text.lower() or "伪造" in text or "不伪造" in text or "leave" in text.lower()

    def test_doc_mentions_snapshot_is_authoritative(self):
        """Docs must state that the current holding snapshot is the authoritative source."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "authoritative" in text.lower() or "权威" in text
        assert "snapshot" in text.lower() or "快照" in text

    def test_doc_mentions_pending_not_confirmed(self):
        """Docs must state that pending_confirmation must not be treated as confirmed holdings."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "pending_confirmation" in text or "pending" in text.lower()
        assert "confirmed" in text.lower() or "已确认" in text

    def test_doc_mentions_private_data_directory(self):
        """Docs must reference private_data/ as the location for private files."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "private_data" in text

    def test_doc_mentions_no_alipay_importer(self):
        """Docs must state there is no Alipay importer."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "importer" in text.lower() or "no alipay" in text.lower() or "no" in text.lower() and "parse" in text.lower()

    def test_doc_mentions_allowed_action_values(self):
        """Docs must list the allowed action values."""
        text = _read_doc(MANUAL_MAINT_DOC)
        for action in ["buy", "sell", "cash_dividend", "conversion", "refund",
                        "fee", "transfer_in", "transfer_out", "manual_adjustment", "unknown"]:
            assert action in text, f"Allowed action '{action}' not documented"

    def test_doc_mentions_allowed_status_values(self):
        """Docs must list the allowed status values."""
        text = _read_doc(MANUAL_MAINT_DOC)
        for status in ["confirmed", "pending_confirmation", "estimated", "cancelled", "unknown"]:
            assert status in text, f"Allowed status '{status}' not documented"

    def test_doc_mentions_bootstrap_flow(self):
        """Docs must show the manual transaction bootstrap flow."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "alipay_record" in text or "manual_transactions" in text
        assert "portfolio_input" in text

    def test_doc_mentions_no_auto_calculation(self):
        """Docs must state no automatic cost/NAV/units calculation."""
        text = _read_doc(MANUAL_MAINT_DOC)
        assert "automatic" in text.lower() or "自动" in text
        # Must say no auto calculation
        assert "no automatic" in text.lower() or "不自动" in text or "不" in text and "计算" in text


class TestPrivateDataHandlingDoc:
    """Tests for updated docs/development/private-data-handling.md."""

    def test_doc_exists(self):
        assert PRIVATE_DATA_HANDLING_DOC.exists()

    def test_doc_mentions_manual_transaction_bootstrap(self):
        """Updated doc must mention manual transaction bootstrap flow."""
        text = _read_doc(PRIVATE_DATA_HANDLING_DOC)
        assert "manual_transactions" in text or "bootstrap" in text.lower()

    def test_doc_mentions_alipay_csv_not_committed(self):
        """Updated doc must state raw Alipay CSV must not be committed."""
        text = _read_doc(PRIVATE_DATA_HANDLING_DOC)
        assert "alipay" in text.lower() or "支付宝" in text
        assert "never commit" in text.lower() or "不提交" in text or "不得提交" in text

    def test_doc_mentions_snapshot_authoritative(self):
        """Updated doc must mention snapshot is authoritative."""
        text = _read_doc(PRIVATE_DATA_HANDLING_DOC)
        assert "authoritative" in text.lower() or "权威" in text or "snapshot" in text.lower()

    def test_doc_mentions_no_fund_code_guessing(self):
        """Updated doc must mention not to guess fund_code."""
        text = _read_doc(PRIVATE_DATA_HANDLING_DOC)
        assert "fund_code" in text or "基金代码" in text
        assert "不猜" in text or "不要猜" in text or "do not guess" in text.lower()

    def test_doc_mentions_manual_transaction_template(self):
        """Updated doc must reference the new manual transaction template."""
        text = _read_doc(PRIVATE_DATA_HANDLING_DOC)
        assert "manual_transaction_entries_template" in text


class TestPrivateDataFlowDoc:
    """Tests for updated docs/agent-integration/private-data-flow.md."""

    def test_doc_exists(self):
        assert PRIVATE_DATA_FLOW_DOC.exists()

    def test_doc_mentions_manual_transaction_bootstrap(self):
        """Updated doc must mention manual transaction bootstrap flow."""
        text = _read_doc(PRIVATE_DATA_FLOW_DOC)
        assert "manual_transactions" in text or "bootstrap" in text.lower()

    def test_doc_mentions_alipay_csv_not_committed(self):
        """Updated doc must state raw Alipay CSV must not be committed."""
        text = _read_doc(PRIVATE_DATA_FLOW_DOC)
        assert "alipay" in text.lower() or "支付宝" in text
        assert "never commit" in text.lower() or "不提交" in text or "不得提交" in text


class TestTemplatesReadme:
    """Tests for updated examples/user_portfolio_templates/README.md."""

    def test_readme_exists(self):
        assert TEMPLATES_README.exists()

    def test_readme_mentions_manual_transaction_template(self):
        """README must list the new manual_transaction_entries_template.csv."""
        text = _read_doc(TEMPLATES_README)
        assert "manual_transaction_entries_template" in text

    def test_readme_mentions_bootstrap(self):
        """README must mention manual transaction bootstrap flow."""
        text = _read_doc(TEMPLATES_README)
        assert "bootstrap" in text.lower() or "manual" in text.lower()
