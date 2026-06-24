"""Tests for Alipay CSV importer with real-shaped padded-header fixtures.

Covers:
- Padded header normalization
- 商家订单号/商户订单号 support
- Fund transactions kept even without fund_code
- Classification accuracy (buy/sell/dividend/conversion/refund/pending)
- No raw account/order/trade IDs in output
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.import_alipay_transactions import import_alipay_csv

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "alipay"
PADDED_CSV = FIXTURES_DIR / "alipay_real_shape_padded.csv"


@pytest.fixture
def output_path(tmp_path: Path) -> Path:
    return tmp_path / "normalized.json"


class TestPaddedHeaderImport:
    """Test that padded-header real-shaped Alipay CSV is parsed correctly."""

    def test_total_transactions_positive(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["total_transactions"] > 0, (
            "Padded-header CSV should produce transactions"
        )

    def test_fund_transactions_positive(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["fund_transactions"] > 0, (
            "Padded-header CSV should produce fund transactions"
        )

    def test_buy_count(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["classification_counts"]["buy"] >= 1, (
            "Should detect at least 1 buy (买入)"
        )

    def test_sell_count(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["classification_counts"]["sell"] >= 1, (
            "Should detect at least 1 sell (卖出至余额宝)"
        )

    def test_dividend_count(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["classification_counts"]["dividend"] >= 1, (
            "Should detect at least 1 dividend (现金分红至余额宝)"
        )

    def test_conversion_count(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["classification_counts"]["conversion"] >= 1, (
            "Should detect at least 1 conversion (转换)"
        )

    def test_refund_count(self, output_path: Path):
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["classification_counts"]["refund"] >= 1, (
            "Should detect at least 1 refund (买入退款)"
        )

    def test_pending_status_preserved(self, output_path: Path):
        """份额确认中 should be flagged as pending."""
        import_alipay_csv(PADDED_CSV, output_path)
        data = json.loads(output_path.read_text(encoding="utf-8"))
        pending = [t for t in data["transactions"] if t.get("pending")]
        assert len(pending) >= 1, (
            "Should detect at least 1 pending transaction (份额确认中)"
        )

    def test_fund_name_without_fund_code(self, output_path: Path):
        """Transactions with fund_name but no fund_code should be kept."""
        import_alipay_csv(PADDED_CSV, output_path)
        data = json.loads(output_path.read_text(encoding="utf-8"))
        no_code = [t for t in data["transactions"] if not t.get("fund_code")]
        assert len(no_code) >= 1, (
            "Should keep transactions identified by fund_name even without fund_code"
        )

    def test_no_raw_ids_in_output(self, output_path: Path):
        """Output must not contain raw trade/order/account IDs."""
        import_alipay_csv(PADDED_CSV, output_path)
        text = output_path.read_text(encoding="utf-8")
        # Raw IDs from fixture should not appear verbatim
        assert "SYNTH-001" not in text
        assert "SYNTH-ORD-001" not in text
        assert "[REDACTED]" not in text

    def test_merchant_order_no_support(self, output_path: Path):
        """商家订单号 (not just 商户订单号) should be used for source_ref."""
        import_alipay_csv(PADDED_CSV, output_path)
        data = json.loads(output_path.read_text(encoding="utf-8"))
        # All transactions should have a source_ref (redacted)
        for txn in data["transactions"]:
            assert txn.get("source_ref") is not None or txn.get("transaction_id") is not None

    def test_six_transactions_total(self, output_path: Path):
        """The fixture has 6 fund-related rows; all should be parsed."""
        result = import_alipay_csv(PADDED_CSV, output_path)
        assert result["total_transactions"] == 6, (
            f"Expected 6 transactions from fixture, got {result['total_transactions']}"
        )


class TestHeaderNormalization:
    """Unit tests for header normalization edge cases."""

    def test_arbitrary_whitespace_stripped(self, tmp_path: Path):
        """Headers with multiple spaces/tabs should be normalized."""
        csv_content = (
            "商品名称                ,金额（元）   ,收/支     ,交易状态    \n"
            "蚂蚁财富-测试基金-买入,100.00,支出,交易成功\n"
        )
        csv_path = tmp_path / "padded.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        output_path = tmp_path / "out.json"
        result = import_alipay_csv(csv_path, output_path)
        assert result["total_transactions"] == 1

    def test_merchant_order_no_variant(self, tmp_path: Path):
        """商家订单号 (not just 商户订单号) should be recognized."""
        csv_content = (
            "交易号,商家订单号,交易创建时间,商品名称,金额（元）,收/支,交易状态\n"
            "T001,O001,2026-06-15 10:00:00,蚂蚁财富-测试基金-买入,500.00,支出,交易成功\n"
        )
        csv_path = tmp_path / "merchant.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        output_path = tmp_path / "out.json"
        result = import_alipay_csv(csv_path, output_path)
        assert result["total_transactions"] == 1
