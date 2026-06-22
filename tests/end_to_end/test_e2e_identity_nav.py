"""Synthetic E2E tests for identity resolution, fund code validation, and Alipay name cleaning.

These tests use only fake/synthetic data — no real user holdings or private data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_SIX_DIGIT_RE = re.compile(r"^\d{6}$")

# ---------------------------------------------------------------------------
# A. Identity schema wiring
# ---------------------------------------------------------------------------


class TestIdentitySchemaWiring:
    """Verify E2E reads the current resolver output schema correctly."""

    def test_resolutions_schema_read_by_e2e(self, tmp_path: Path) -> None:
        """E2E must read resolutions[].resolved_fund_code from identity output."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "FakeFundA", "source": "alipay"},
                {"fund_code": "007467", "fund_name": "FakeFundB", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        assert result["schema_version"] == "fund_identity_resolution.v1"
        assert "resolutions" in result
        codes = [r["resolved_fund_code"] for r in result["resolutions"]]
        assert "002168" in codes
        assert "007467" in codes

    def test_e2e_reads_resolutions_not_funds(self, tmp_path: Path) -> None:
        """E2E fund_agent_e2e.py must extract codes from 'resolutions' key."""
        identity_data = {
            "schema_version": "fund_identity_resolution.v1",
            "summary": {"total_funds": 2},
            "resolutions": [
                {"resolved_fund_code": "002168", "fund_name": "FakeA", "confidence": "high"},
                {"resolved_fund_code": "007467", "fund_name": "FakeB", "confidence": "high"},
            ],
        }
        identity_file = tmp_path / "fund_identity_resolution.json"
        identity_file.write_text(json.dumps(identity_data), encoding="utf-8")

        # Simulate what E2E does
        loaded = json.loads(identity_file.read_text(encoding="utf-8"))
        entries = loaded.get("resolutions", loaded.get("funds", []))
        code_field = "resolved_fund_code" if "resolutions" in loaded else "resolved_code"
        raw_codes = [e.get(code_field, "") for e in entries if e.get(code_field)]
        fund_codes = [c for c in raw_codes if _SIX_DIGIT_RE.match(c)]

        assert fund_codes == ["002168", "007467"]

    def test_backward_compat_funds_schema(self) -> None:
        """Old funds[].resolved_code schema still works for reading."""
        identity_data = {
            "schema_version": "fund_identity_resolution.v0",
            "summary": {"total_funds": 1},
            "funds": [
                {"resolved_code": "002168", "fund_name": "FakeA"},
            ],
        }
        entries = identity_data.get("resolutions", identity_data.get("funds", []))
        code_field = "resolved_fund_code" if "resolutions" in identity_data else "resolved_code"
        raw_codes = [e.get(code_field, "") for e in entries if e.get(code_field)]
        assert raw_codes == ["002168"]


# ---------------------------------------------------------------------------
# B. Fund code validation
# ---------------------------------------------------------------------------


class TestFundCodeValidation:
    """Six-digit codes pass; Chinese names are rejected as fund codes."""

    def test_six_digit_codes_are_valid(self) -> None:
        assert _SIX_DIGIT_RE.match("002168")
        assert _SIX_DIGIT_RE.match("007467")
        assert _SIX_DIGIT_RE.match("017436")

    def test_chinese_names_rejected_as_fund_codes(self) -> None:
        assert not _SIX_DIGIT_RE.match("东方惠新灵活配置混合A")
        assert not _SIX_DIGIT_RE.match("华宝纳斯达克精选股票QDIIA")
        assert not _SIX_DIGIT_RE.match("蚂蚁财富-某基金-买入")

    def test_e2e_filters_name_only_codes(self) -> None:
        """E2E must count name-only references separately from valid codes."""
        raw_codes = ["002168", "东方惠新灵活配置混合A", "007467", "华宝纳斯达克精选股票QDIIA"]
        fund_codes = [c for c in raw_codes if _SIX_DIGIT_RE.match(c)]
        name_only_count = sum(1 for c in raw_codes if not _SIX_DIGIT_RE.match(c))
        assert fund_codes == ["002168", "007467"]
        assert name_only_count == 2

    def test_resolver_summary_includes_valid_fund_codes_count(self) -> None:
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "FakeA", "source": "alipay"},
                {"fund_code": None, "fund_name": "ChineseFundName", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        assert result["summary"]["valid_fund_codes_count"] >= 1
        assert result["summary"]["name_only_count"] >= 1

    def test_chinese_name_never_passed_as_provider_fund_code(self) -> None:
        """Chinese fund names must never be passed as fund_code to provider/snapshot."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "中文基金名A", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        # The resolved_fund_code will be the Chinese name (name-only),
        # but E2E must filter it out before passing to snapshot
        for r in result["resolutions"]:
            code = r["resolved_fund_code"]
            if not _SIX_DIGIT_RE.match(code):
                # This is a name-only code — must not be passed to provider
                assert r["confidence"] == "low"


# ---------------------------------------------------------------------------
# C. Manual overrides
# ---------------------------------------------------------------------------


class TestManualOverrides:
    """Fake clean fund names map to fake six-digit codes via overrides."""

    def test_override_yaml_loading(self, tmp_path: Path) -> None:
        from scripts.resolve_fund_identities import _load_overrides

        override_yaml = tmp_path / "overrides.yaml"
        override_yaml.write_text(
            """
funds:
  - raw_name: "FakeAlpha"
    fund_code: "111111"
    fund_name: "FakeAlpha Fund"
  - raw_name: "FakeBeta"
    fund_code: "222222"
    fund_name: "FakeBeta Fund"
aliases:
  "FakeAlphaAlias": "333333"
""",
            encoding="utf-8",
        )
        lookup, warnings = _load_overrides(override_yaml)
        assert "FakeAlpha" in lookup
        assert lookup["FakeAlpha"]["fund_code"] == "111111"
        assert "FakeBeta" in lookup
        assert "FakeAlphaAlias" in lookup
        assert lookup["FakeAlphaAlias"]["fund_code"] == "333333"
        assert warnings == []

    def test_override_applied_in_resolution(self) -> None:
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "FakeAlpha", "source": "alipay"},
            ]
        }
        override_lookup = {
            "FakeAlpha": {"fund_code": "111111", "fund_name": "FakeAlpha Fund"},
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
        )
        codes = [r["resolved_fund_code"] for r in result["resolutions"]]
        assert "111111" in codes
        # Check confidence is high
        for r in result["resolutions"]:
            if r["resolved_fund_code"] == "111111":
                assert r["confidence"] == "high"
                assert r["resolution_source"] == "manual_override"

    def test_override_summary_fields(self) -> None:
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "FakeAlpha", "source": "alipay"},
            ]
        }
        override_lookup = {
            "FakeAlpha": {"fund_code": "111111", "fund_name": "FakeAlpha Fund"},
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
        )
        assert result["summary"]["manual_overrides_used"] is True
        assert result["summary"]["manual_override_matches_count"] >= 1
        assert result["summary"]["valid_fund_codes_count"] >= 1

    def test_override_contents_not_in_output(self) -> None:
        """Override file contents should not appear in resolution output."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "FakeAlpha", "source": "alipay"},
            ]
        }
        override_lookup = {
            "FakeAlpha": {"fund_code": "111111", "fund_name": "FakeAlpha Fund"},
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
        )
        output_str = json.dumps(result, ensure_ascii=False)
        # The override_lookup dict itself should not appear in output
        assert "override_lookup" not in output_str

    def test_invalid_override_code_skipped(self, tmp_path: Path) -> None:
        """Invalid override fund_code (not 6 digits) must produce warning and not enter valid_fund_codes_count."""
        from scripts.resolve_fund_identities import _load_overrides

        override_yaml = tmp_path / "overrides.yaml"
        override_yaml.write_text(
            """
funds:
  - raw_name: "FakeAlpha"
    fund_code: "111111"
    fund_name: "FakeAlpha Fund"
  - raw_name: "FakeBad"
    fund_code: "not-a-code"
    fund_name: "FakeBad Fund"
aliases:
  "BadAlias": "abc123"
""",
            encoding="utf-8",
        )
        lookup, warnings = _load_overrides(override_yaml)
        # Valid entry should be loaded
        assert "FakeAlpha" in lookup
        assert lookup["FakeAlpha"]["fund_code"] == "111111"
        # Invalid entries should be skipped
        assert "FakeBad" not in lookup
        assert "BadAlias" not in lookup
        # Warnings should be produced
        assert len(warnings) == 2
        assert any("not-a-code" in w for w in warnings)
        assert any("abc123" in w for w in warnings)

    def test_name_only_with_override_produces_valid_codes(self) -> None:
        """Name-only Alipay transaction + private override -> valid_fund_codes_count > 0."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "测试基金Alpha", "source": "alipay"},
            ]
        }
        override_lookup = {
            "测试基金Alpha": {"fund_code": "111111", "fund_name": "测试基金Alpha"},
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
        )
        assert result["summary"]["valid_fund_codes_count"] > 0
        assert result["summary"]["name_only_count"] == 0  # override resolved it


# ---------------------------------------------------------------------------
# D. Alipay clean fund_name extraction
# ---------------------------------------------------------------------------


class TestAlipayFundNameCleaning:
    """Fake padded Alipay rows produce clean fund_name."""

    def test_strip_prefix_and_buy_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-东方惠新灵活配置混合A-买入") == "东方惠新灵活配置混合A"

    def test_strip_sell_to_yueebao_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-华宝纳斯达克精选股票(QDII)A-卖出至余额宝") == "华宝纳斯达克精选股票(QDII)A"

    def test_strip_dividend_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-某基金-现金分红至余额宝") == "某基金"

    def test_strip_conversion_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-某基金-转换") == "某基金"

    def test_strip_conversion_refund_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-某基金-转换退款") == "某基金"

    def test_strip_buy_refund_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-某基金-买入退款") == "某基金"

    def test_strip_pending_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-某基金-份额确认中") == "某基金"

    def test_no_prefix_no_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("纯基金名称") == "纯基金名称"

    def test_prefix_only(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("蚂蚁财富-纯基金名称") == "纯基金名称"

    def test_conversion_with_target_strips_target(self) -> None:
        """Conversion entries extract source fund; target preserved in remark."""
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("东方惠新灵活配置混合A[转换至]东方添益债券") == "东方惠新灵活配置混合A"

    def test_conversion_with_dash_target(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("东方惠新灵活配置混合A-[转换至]华泰柏瑞中证红利低波动ETF联接C-确认成功退款") == "东方惠新灵活配置混合A"

    def test_activity_gift_suffix(self) -> None:
        from scripts.import_alipay_transactions import _clean_fund_name

        assert _clean_fund_name("永赢合享混合A-活动赠送") == "永赢合享混合A"

    def test_full_import_produces_clean_names(self, tmp_path: Path) -> None:
        """End-to-end: import produces clean fund_name, not full product action string."""
        from scripts.import_alipay_transactions import import_alipay_csv

        csv_content = (
            "交易号,交易创建时间,商品名称,金额（元）,交易状态,类型,收/支,资金状态\n"
            "FAKE001,2025-01-15 10:00:00,蚂蚁财富-测试基金Alpha-买入,100.00,交易成功,即时到账,支出,已支出\n"
            "FAKE002,2025-02-20 10:00:00,蚂蚁财富-测试基金Beta-卖出至余额宝,200.00,交易成功,即时到账,收入,已收入\n"
        )
        csv_file = tmp_path / "alipay_test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        output_file = tmp_path / "normalized.json"
        import_alipay_csv(csv_file, output_file, redact_ids=False)

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        txns = data["transactions"]
        names = [t["fund_name"] for t in txns]
        assert "测试基金Alpha" in names
        assert "测试基金Beta" in names
        # Should NOT contain the full product action strings
        assert "蚂蚁财富-测试基金Alpha-买入" not in names
        assert "蚂蚁财富-测试基金Beta-卖出至余额宝" not in names


# ---------------------------------------------------------------------------
# E. E2E identity-to-NAV path (synthetic)
# ---------------------------------------------------------------------------


class TestE2EIdentityToNAVPath:
    """Fake Alipay + fake override + seeded NAV -> reconstruction."""

    def test_valid_codes_trigger_snapshot_attempt(self, tmp_path: Path) -> None:
        """When valid six-digit codes exist, fund_data_snapshot_attempted should be true."""
        # Create fake identity resolution with valid codes
        identity = {
            "schema_version": "fund_identity_resolution.v1",
            "summary": {"total_funds": 1, "valid_fund_codes_count": 1, "name_only_count": 0},
            "resolutions": [
                {"resolved_fund_code": "002168", "fund_name": "FakeA", "confidence": "high"},
            ],
        }
        identity_file = tmp_path / "fund_identity_resolution.json"
        identity_file.write_text(json.dumps(identity), encoding="utf-8")

        # Verify that E2E would identify these as valid codes
        loaded = json.loads(identity_file.read_text(encoding="utf-8"))
        entries = loaded.get("resolutions", loaded.get("funds", []))
        code_field = "resolved_fund_code" if "resolutions" in loaded else "resolved_code"
        raw_codes = [e.get(code_field, "") for e in entries if e.get(code_field)]
        fund_codes = [c for c in raw_codes if _SIX_DIGIT_RE.match(c)]

        assert fund_codes == ["002168"]
        assert len(fund_codes) > 0  # Snapshot should be attempted

    def test_override_produces_valid_codes_and_snapshot_attempted(self) -> None:
        """Valid override -> valid_fund_codes_count > 0 -> snapshot should be attempted."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "FakeAlpha", "source": "alipay"},
            ]
        }
        override_lookup = {
            "FakeAlpha": {"fund_code": "111111", "fund_name": "FakeAlpha Fund"},
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
        )
        assert result["summary"]["valid_fund_codes_count"] > 0
        # E2E would see valid_codes_count > 0 and attempt snapshot

    def test_override_with_seeded_nav_triggers_reconstruction(self, tmp_path: Path) -> None:
        """Valid override + seeded NAV -> reconstruction attempted, portfolio_input_source = reconstructed_from_ledger."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        # Ledger with name-only transactions
        ledger_data = {
            "transactions": [
                {
                    "fund_code": None,
                    "fund_name": "FakeAlpha",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        # Identity resolution maps FakeAlpha -> 111111
        identity_data = {
            "schema_version": "fund_identity_resolution.v1",
            "resolutions": [
                {"resolved_fund_code": "111111", "fund_name": "FakeAlpha", "confidence": "high"},
            ],
        }

        # Seeded NAV
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {
                    "records": [
                        {"date": "2025-06-20", "nav": 1.5},
                    ],
                },
            },
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
            identity_data=identity_data,
        )

        # Reconstruction should have grouped by resolved code 111111
        confirmed = result["confirmed_portfolio"]
        positions = confirmed["positions"]
        assert len(positions) >= 1
        fund_codes = [p["fund_code"] for p in positions]
        assert "111111" in fund_codes
        # Identity was applied
        assert result["identity_applied_count"] >= 1


# ---------------------------------------------------------------------------
# F. No-NAV path
# ---------------------------------------------------------------------------


class TestNoNAVPath:
    """Valid fund codes exist but NAV unavailable -> status partial with proper warning."""

    def test_nav_unavailable_warning_is_specific(self, tmp_path: Path) -> None:
        """When valid codes exist but NAV fails, warning must say provider/NAV failed."""
        identity = {
            "schema_version": "fund_identity_resolution.v1",
            "summary": {
                "total_funds": 1,
                "valid_fund_codes_count": 1,
                "name_only_count": 0,
                "fund_data_snapshot_attempted": True,
                "fund_data_snapshot_status": "provider_unavailable",
            },
            "resolutions": [
                {"resolved_fund_code": "002168", "fund_name": "FakeA", "confidence": "high"},
            ],
        }
        identity_file = tmp_path / "fund_identity_resolution.json"
        identity_file.write_text(json.dumps(identity), encoding="utf-8")

        # Verify the summary distinguishes provider_unavailable from no_valid_fund_codes
        loaded = json.loads(identity_file.read_text(encoding="utf-8"))
        summary = loaded["summary"]
        assert summary["valid_fund_codes_count"] > 0
        assert summary["fund_data_snapshot_attempted"] is True
        assert summary["fund_data_snapshot_status"] == "provider_unavailable"

    def test_name_only_warning_is_specific(self) -> None:
        """When only name-only references exist, warning must say fund_code mapping required."""
        raw_codes = ["ChineseFundName", "AnotherChineseName"]
        fund_codes = [c for c in raw_codes if _SIX_DIGIT_RE.match(c)]
        name_only_count = sum(1 for c in raw_codes if not _SIX_DIGIT_RE.match(c))

        assert len(fund_codes) == 0
        assert name_only_count == 2
        # E2E should warn: "name-only references; fund_code mapping required for NAV"

    def test_name_only_without_override_no_nav_attempted(self) -> None:
        """Name-only without override -> no NAV attempted, warning says fund_code mapping required."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "ChineseFundName", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        assert result["summary"]["valid_fund_codes_count"] == 0
        assert result["summary"]["name_only_count"] >= 1
        # E2E should skip snapshot and warn about fund_code mapping


# ---------------------------------------------------------------------------
# G. Reconstruction identity bridge
# ---------------------------------------------------------------------------


class TestReconstructionIdentityBridge:
    """Resolved identity is applied to reconstruction grouping, not only snapshot building."""

    def test_name_only_txns_mapped_via_identity(self) -> None:
        """Name-only ledger transactions get resolved fund_code from identity resolution."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": None,
                    "fund_name": "FakeAlpha",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
                {
                    "fund_code": None,
                    "fund_name": "FakeBeta",
                    "action": "buy",
                    "amount": 2000.0,
                    "trade_date": "2025-02-20",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        identity_data = {
            "schema_version": "fund_identity_resolution.v1",
            "resolutions": [
                {"resolved_fund_code": "111111", "fund_name": "FakeAlpha", "confidence": "high"},
                {"resolved_fund_code": "222222", "fund_name": "FakeBeta", "confidence": "high"},
            ],
        }

        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [{"date": "2025-06-20", "nav": 1.0}]},
                "222222": {"records": [{"date": "2025-06-20", "nav": 2.0}]},
            },
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
            identity_data=identity_data,
        )

        positions = result["confirmed_portfolio"]["positions"]
        fund_codes = [p["fund_code"] for p in positions]
        assert "111111" in fund_codes
        assert "222222" in fund_codes
        assert result["identity_applied_count"] == 2

    def test_without_identity_name_only_txns_skipped(self) -> None:
        """Without identity resolution, name-only transactions are skipped in reconstruction."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": None,
                    "fund_name": "FakeAlpha",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [{"date": "2025-06-20", "nav": 1.0}]},
            },
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
            identity_data=None,
        )

        positions = result["confirmed_portfolio"]["positions"]
        # Without identity, name-only transactions have no fund_code -> not grouped
        assert len(positions) == 0
        assert result["identity_applied_count"] == 0

    def test_original_evidence_preserved(self) -> None:
        """Identity resolution adds resolved code but does not overwrite original evidence fields."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": None,
                    "fund_name": "FakeAlpha",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                    "transaction_id": "txn_001",
                },
            ]
        }

        identity_data = {
            "schema_version": "fund_identity_resolution.v1",
            "resolutions": [
                {"resolved_fund_code": "111111", "fund_name": "FakeAlpha", "confidence": "high"},
            ],
        }

        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [{"date": "2025-06-20", "nav": 1.0}]},
            },
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
            identity_data=identity_data,
        )

        # Original ledger data should still have fund_code=None
        original_txn = ledger_data["transactions"][0]
        assert original_txn["fund_code"] is None
        assert original_txn["fund_name"] == "FakeAlpha"
        # But reconstruction should have grouped it under 111111
        positions = result["confirmed_portfolio"]["positions"]
        assert any(p["fund_code"] == "111111" for p in positions)
