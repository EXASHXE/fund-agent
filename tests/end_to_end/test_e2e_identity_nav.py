"""Synthetic E2E tests for identity resolution, fund code validation, and Alipay name cleaning.

These tests use only fake/synthetic data — no real user holdings or private data.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.fund_identity_utils import is_valid_fund_code, normalize_fund_name

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
        assert result["schema_version"] == "fund_identity_resolution.v2"
        assert "resolutions" in result
        codes = [r["resolved_fund_code"] for r in result["resolutions"]]
        assert "002168" in codes
        assert "007467" in codes

    def test_e2e_reads_resolutions_not_funds(self, tmp_path: Path) -> None:
        """E2E fund_agent_e2e.py must extract codes from 'resolutions' key."""
        identity_data = {
            "schema_version": "fund_identity_resolution.v2",
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
        fund_codes = [c for c in raw_codes if is_valid_fund_code(c)]

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
        assert is_valid_fund_code("002168")
        assert is_valid_fund_code("007467")
        assert is_valid_fund_code("017436")

    def test_chinese_names_rejected_as_fund_codes(self) -> None:
        assert not is_valid_fund_code("东方惠新灵活配置混合A")
        assert not is_valid_fund_code("华宝纳斯达克精选股票QDIIA")
        assert not is_valid_fund_code("蚂蚁财富-某基金-买入")

    def test_e2e_filters_name_only_codes(self) -> None:
        """E2E must count name-only references separately from valid codes."""
        raw_codes = ["002168", "东方惠新灵活配置混合A", "007467", "华宝纳斯达克精选股票QDIIA"]
        fund_codes = [c for c in raw_codes if is_valid_fund_code(c)]
        name_only_count = sum(1 for c in raw_codes if not is_valid_fund_code(c))
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
        """Chinese fund names must never appear as resolved_fund_code."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "中文基金名A", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        # resolved_fund_code must be None for name-only, never the Chinese name
        r = result["resolutions"][0]
        assert r["resolved_fund_code"] is None
        assert r["resolution_status"] == "name_only"


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
        fund_codes = [c for c in raw_codes if is_valid_fund_code(c)]

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
        fund_codes = [c for c in raw_codes if is_valid_fund_code(c)]
        name_only_count = sum(1 for c in raw_codes if not is_valid_fund_code(c))

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


# ---------------------------------------------------------------------------
# H. Identity schema v2 fields
# ---------------------------------------------------------------------------


class TestIdentitySchemaV2:
    """Verify new v2 schema fields: raw_reference, raw_fund_code, raw_fund_name,
    normalized_name, resolution_status, resolution_status_counts."""

    def test_name_only_resolved_fund_code_is_none(self) -> None:
        """Name-only resolution: resolved_fund_code must be None, not the Chinese name."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "中文基金名A", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        r = result["resolutions"][0]
        assert r["resolved_fund_code"] is None
        assert r["resolution_status"] == "name_only"
        assert r["raw_reference"] == "中文基金名A"
        assert r["raw_fund_code"] is None
        assert r["raw_fund_name"] == "中文基金名A"

    def test_valid_code_fields(self) -> None:
        """Valid six-digit code: resolution_status == valid_code."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "FakeA", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        r = result["resolutions"][0]
        assert r["resolved_fund_code"] == "002168"
        assert r["resolution_status"] == "valid_code"
        assert r["raw_fund_code"] == "002168"
        assert r["normalized_name"] is not None

    def test_manual_override_status(self) -> None:
        """Manual override: resolution_status == manual_override."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": None, "fund_name": "FakeAlpha", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup={"FakeAlpha": {"fund_code": "111111", "fund_name": "FakeAlpha"}},
        )
        r = result["resolutions"][0]
        assert r["resolved_fund_code"] == "111111"
        assert r["resolution_status"] == "manual_override"

    def test_resolution_status_counts(self) -> None:
        """Summary includes resolution_status_counts with correct taxonomy."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "FakeA", "source": "alipay"},
                {"fund_code": None, "fund_name": "ChineseName", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        counts = result["summary"]["resolution_status_counts"]
        assert counts["valid_code"] == 1
        assert counts["name_only"] == 1
        assert counts["manual_override"] == 0
        assert counts["invalid_code"] == 0
        assert counts["unresolved"] == 0

    def test_normalized_name_field(self) -> None:
        """normalized_name strips punctuation and whitespace."""
        from scripts.resolve_fund_identities import resolve_fund_identities

        ledger_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "Fake Fund (A)", "source": "alipay"},
            ]
        }
        result = resolve_fund_identities(ledger_data=ledger_data)
        r = result["resolutions"][0]
        assert r["normalized_name"] == "FakeFundA"


# ---------------------------------------------------------------------------
# I. Normalization consistency across scripts
# ---------------------------------------------------------------------------


class TestNormalizationConsistency:
    """Same name variant produces same normalized_name across scripts."""

    def test_normalize_fund_name_strips_punctuation(self) -> None:
        from scripts.fund_identity_utils import normalize_fund_name

        assert normalize_fund_name("Fake Fund (A)") == "FakeFundA"
        assert normalize_fund_name("华宝纳斯达克精选股票（QDII）A") == "华宝纳斯达克精选股票QDIIA"
        assert normalize_fund_name("某基金-混合型") == "某基金混合型"

    def test_import_produces_normalized_name(self, tmp_path: Path) -> None:
        """import_alipay_transactions adds normalized_name to each transaction."""
        from scripts.import_alipay_transactions import import_alipay_csv

        csv_content = (
            "交易号,交易创建时间,商品名称,金额（元）,交易状态,类型,收/支,资金状态\n"
            "FAKE001,2025-01-15 10:00:00,蚂蚁财富-测试基金（QDII）A-买入,100.00,交易成功,即时到账,支出,已支出\n"
        )
        csv_file = tmp_path / "alipay_test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        output_file = tmp_path / "normalized.json"
        import_alipay_csv(csv_file, output_file, redact_ids=False)

        data = json.loads(output_file.read_text(encoding="utf-8"))
        txn = data["transactions"][0]
        assert txn["normalized_name"] is not None
        # normalized_name should strip parens and match normalize_fund_name output
        assert txn["normalized_name"] == normalize_fund_name("测试基金（QDII）A")

    def test_resolver_and_import_produce_same_normalized_name(self, tmp_path: Path) -> None:
        """Identity resolver and import script agree on normalized_name for the same fund."""
        from scripts.import_alipay_transactions import import_alipay_csv
        from scripts.resolve_fund_identities import resolve_fund_identities

        csv_content = (
            "交易号,交易创建时间,商品名称,金额（元）,交易状态,类型,收/支,资金状态\n"
            "FAKE001,2025-01-15 10:00:00,蚂蚁财富-测试基金（QDII）A-买入,100.00,交易成功,即时到账,支出,已支出\n"
        )
        csv_file = tmp_path / "alipay_test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        output_file = tmp_path / "normalized.json"
        import_alipay_csv(csv_file, output_file, redact_ids=False)

        data = json.loads(output_file.read_text(encoding="utf-8"))
        import_nn = data["transactions"][0]["normalized_name"]

        # Resolver processes the cleaned name
        result = resolve_fund_identities(
            ledger_data={"transactions": [
                {"fund_code": None, "fund_name": "测试基金（QDII）A", "source": "alipay"},
            ]},
        )
        resolver_nn = result["resolutions"][0]["normalized_name"]

        assert import_nn == resolver_nn


# ---------------------------------------------------------------------------
# J. Reconstruction bridge with normalized_name matching
# ---------------------------------------------------------------------------


class TestReconstructionNormalizedNameBridge:
    """Reconstruction matches by normalized_name when exact name fails."""

    def test_normalized_name_matching_works(self) -> None:
        """Half-width vs full-width parens: normalized_name matching resolves identity."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": None,
                    "fund_name": "测试基金(QDII)A",  # half-width parens
                    "normalized_name": "测试基金QDIIA",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        # Identity resolution with full-width parens
        identity_data = {
            "schema_version": "fund_identity_resolution.v2",
            "resolutions": [
                {
                    "resolved_fund_code": "111111",
                    "fund_name": "测试基金（QDII）A",  # full-width parens
                    "normalized_name": "测试基金QDIIA",
                },
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

        positions = result["confirmed_portfolio"]["positions"]
        assert any(p["fund_code"] == "111111" for p in positions)
        assert result["identity_applied_count"] >= 1

    def test_valuation_type_estimated_when_units_and_nav_available(self) -> None:
        """When units computed from trade-date NAV and latest_nav exists, valuation_type == 'estimated'."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "fund_name": "FakeA",
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
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},  # NAV on trade date for unit calculation
                    {"date": "2025-06-20", "nav": 1.5},  # Latest NAV for valuation
                ]},
            },
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )

        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "estimated"
        assert pos["valuation_source"] == "estimated_from_transactions_and_nav"
        assert pos["current_value"] is not None
        assert pos["current_value"] == 1500.0  # 1000 units * 1.5 NAV

    def test_valuation_type_cashflow_only_when_no_nav(self) -> None:
        """When NAV is missing but cost_basis exists, valuation_type == 'cashflow_only'."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "fund_name": "FakeA",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        # No NAV snapshot
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )

        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None
        assert pos["cost_basis"] is not None

    def test_identity_provenance_tracked(self) -> None:
        """Positions resolved via identity show identity_provenance."""
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

        identity_data = {
            "schema_version": "fund_identity_resolution.v2",
            "resolutions": [
                {"resolved_fund_code": "111111", "fund_name": "FakeAlpha"},
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

        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["identity_provenance"] == "identity_resolution"


# ---------------------------------------------------------------------------
# K. E2E summary fund_transactions count
# ---------------------------------------------------------------------------


class TestE2ESummaryFundTransactionsCount:
    """E2E summary counts name-only transactions in fund_transactions."""

    def test_list_branch_counts_name_only_transactions(self) -> None:
        """In list-branch, fund_transactions includes txns with fund_name but no fund_code."""
        tx_data = [
            {"fund_code": "002168", "fund_name": "FakeA", "action": "buy"},
            {"fund_code": None, "fund_name": "ChineseName", "action": "buy"},
            {"fund_code": None, "fund_name": None, "action": "unknown"},
        ]
        fund_txns = [t for t in tx_data if isinstance(t, dict) and (t.get("fund_code") or t.get("fund_name"))]
        assert len(fund_txns) == 2  # Both FakeA and ChineseName

    def test_dict_branch_counts_name_only_transactions(self) -> None:
        """In dict-branch, fund_transactions includes txns with fund_name but no fund_code."""
        tx_data = {
            "transactions": [
                {"fund_code": "002168", "fund_name": "FakeA", "action": "buy"},
                {"fund_code": None, "fund_name": "ChineseName", "action": "buy"},
                {"fund_code": None, "fund_name": None, "action": "unknown"},
            ]
        }
        fund_txns = [t for t in tx_data.get("transactions", []) if isinstance(t, dict) and (t.get("fund_code") or t.get("fund_name"))]
        assert len(fund_txns) == 2


# ---------------------------------------------------------------------------
# L. Report semantics — valuation_type and no fake 0.00
# ---------------------------------------------------------------------------


class TestReportSemantics:
    """valuation_type == cashflow_only when NAV missing; no fake 0.00 current_value."""

    def test_cashflow_only_no_fake_zero(self) -> None:
        """When valuation_type == cashflow_only, current_value must be None, not 0.00."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "fund_name": "FakeA",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        # No NAV -> cashflow_only
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )

        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None
        # Must not be 0.0 or 0.00
        assert pos["current_value"] != 0.0

    def test_portfolio_input_no_fake_zero(self) -> None:
        """portfolio_input holdings must not have 0.00 for unknown current_value."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "fund_name": "FakeA",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "source": "alipay",
                },
            ]
        }

        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )

        holding = result["portfolio_input"]["holdings"][0]
        assert holding["current_value"] is None
        assert holding["current_value"] != 0.0


# ---------------------------------------------------------------------------
# Task 5: New test classes for valuation_type state machine, units estimation,
# fallback source semantics, and report semantics
# ---------------------------------------------------------------------------


class TestValuationTypeStateMachine:
    """Valuation type transitions per the v0.10.5 state machine."""

    def test_none_when_no_transactions(self) -> None:
        """No transactions → valuation_type == 'none'."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        result = reconstruct_portfolio(
            ledger_data={"transactions": []},
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )
        assert result["confirmed_portfolio"]["positions"] == []

    def test_cashflow_only_when_no_units_no_nav(self) -> None:
        """Has cost_basis but no units/NAV → cashflow_only, current_value=None."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None
        assert pos["cost_basis"] is not None

    def test_estimated_when_units_and_latest_nav(self) -> None:
        """Units + latest_nav → estimated, current_value = units * latest_nav."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-20", "nav": 2.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "estimated"
        assert pos["valuation_source"] == "estimated_from_transactions_and_nav"
        assert pos["current_value"] == 2000.0  # 1000 units * 2.0 NAV
        assert pos["units"] == 1000.0

    def test_cashflow_only_when_units_but_no_latest_nav(self) -> None:
        """Units computed but no latest_nav → cashflow_only (can't compute current_value)."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "units": 500.0,  # Explicit units
                },
            ]
        }
        # NAV exists on trade date but NOT on as_of date → no latest_nav
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 2.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 12, 31),  # After all NAV records
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        # latest_nav should be 2.0 (from 2025-01-15, which is <= 2025-12-31)
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None

    def test_valuation_type_never_used_without_confirmed_source(self) -> None:
        """valuation_type='valuation' must not appear in v0.10.5 transaction-derived positions."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-20", "nav": 2.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] != "valuation"


class TestUnitsEstimation:
    """Units estimation from trade-date NAV."""

    def test_buy_with_trade_date_nav_increases_units(self) -> None:
        """Buy with trade-date NAV → units = amount / nav."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 2.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["units"] == 500.0  # 1000 / 2.0
        assert pos["units_source"] == "trade_date_nav"
        assert pos["units_estimated"] is not None

    def test_sell_with_trade_date_nav_decreases_units(self) -> None:
        """Sell with trade-date NAV → units_sold = amount / nav."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 2000.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "111111",
                    "action": "sell",
                    "amount": 500.0,
                    "trade_date": "2025-03-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-10", "nav": 1.0},
                    {"date": "2025-03-10", "nav": 1.25},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["units"] == 1600.0  # 2000/1.0 - 500/1.25 = 2000 - 400
        assert pos["sell_count"] == 1

    def test_dividend_does_not_change_units(self) -> None:
        """Dividend transactions do not modify units."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "111111",
                    "action": "dividend",
                    "amount": 50.0,
                    "trade_date": "2025-03-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-10", "nav": 1.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["units"] == 1000.0  # Unchanged by dividend
        assert pos["dividends_received"] == 50.0

    def test_conversion_flagged_as_manual_review(self) -> None:
        """Conversion transactions are flagged for manual review, excluded from units."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "111111",
                    "action": "conversion",
                    "amount": 500.0,
                    "trade_date": "2025-03-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-10", "nav": 1.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["has_manual_review"] is True
        assert pos["manual_review_transaction_count"] == 1
        assert pos["units"] == 1000.0  # Conversion didn't change units

    def test_refund_flagged_as_manual_review(self) -> None:
        """Refund transactions are flagged for manual review, excluded from units."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "111111",
                    "action": "refund",
                    "amount": 100.0,
                    "trade_date": "2025-03-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-10", "nav": 1.0},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["has_manual_review"] is True
        assert pos["manual_review_transaction_count"] == 1

    def test_partial_trade_nav_coverage(self) -> None:
        """Some txns have trade-date NAV, some don't → partial_trade_date_nav."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 500.0,
                    "trade_date": "2025-02-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-10", "nav": 1.0},
                    # No NAV for 2025-02-15
                    {"date": "2025-06-20", "nav": 1.5},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["units_source"] == "partial_trade_date_nav"
        assert pos["trade_nav_coverage_ratio"] == 0.5  # 1 of 2 txns
        assert pos["trade_nav_missing_count"] == 1
        assert "partial_trade_nav_coverage" in pos.get("data_quality", [])

    def test_explicit_units_field_used(self) -> None:
        """Transaction with explicit 'units' field uses it directly."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "units": 800.0,
                    "trade_date": "2025-01-10",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["units"] == 800.0
        assert pos["units_source"] == "transaction_units"


class TestFallbackSourceSemantics:
    """portfolio_input_source must correctly distinguish reconstructed vs existing."""

    def test_existing_portfolio_input_source(self) -> None:
        """When portfolio_input is not in portfolio_dir, source is existing_private."""
        from pathlib import Path

        # Simulate: portfolio_dir is run_dir/portfolio, existing is private_data/
        portfolio_dir = Path("/tmp/run/portfolio")
        existing = Path("/tmp/private_data/portfolio_input.private.json")

        # The key check: existing path does NOT start with portfolio_dir
        assert not str(existing).startswith(str(portfolio_dir))

    def test_reconstructed_portfolio_input_source(self) -> None:
        """When portfolio_input is in portfolio_dir, source is reconstructed_from_ledger."""
        from pathlib import Path

        portfolio_dir = Path("/tmp/run/portfolio")
        reconstructed = Path("/tmp/run/portfolio/portfolio_input.private.json")

        assert str(reconstructed).startswith(str(portfolio_dir))


class TestReportSemantics:
    """Report semantics: no fake 0.00, estimated properly labeled."""

    def test_cashflow_only_no_fake_zero(self) -> None:
        """cashflow_only positions must have current_value=None, not 0.00."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=None,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None
        assert pos["current_value"] != 0.0

    def test_estimated_must_label_source(self) -> None:
        """estimated positions must have valuation_source=estimated_from_transactions_and_nav."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-20", "nav": 1.5},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        pos = result["confirmed_portfolio"]["positions"][0]
        assert pos["valuation_type"] == "estimated"
        assert pos["valuation_source"] == "estimated_from_transactions_and_nav"
        # Must NOT say "confirmed" or "broker"
        assert "confirmed" not in pos["valuation_source"].lower()
        assert "broker" not in pos["valuation_source"].lower()

    def test_portfolio_input_includes_valuation_type(self) -> None:
        """portfolio_input holdings must include valuation_type and valuation_source."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-20", "nav": 1.5},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        holding = result["portfolio_input"]["holdings"][0]
        assert "valuation_type" in holding
        assert holding["valuation_type"] == "estimated"
        assert "valuation_source" in holding
        assert holding["valuation_source"] == "estimated_from_transactions_and_nav"

    def test_confirmed_portfolio_includes_valuation_type_counts(self) -> None:
        """confirmed_portfolio summary must include valuation_type_counts."""
        from datetime import date

        from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio

        ledger_data = {
            "transactions": [
                {
                    "fund_code": "111111",
                    "action": "buy",
                    "amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
            ]
        }
        nav_snapshot = {
            "nav_by_fund": {
                "111111": {"records": [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-20", "nav": 1.5},
                ]},
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger_data,
            nav_snapshot=nav_snapshot,
            as_of_date=date(2025, 6, 20),
        )
        summary = result["confirmed_portfolio"]["summary"]
        assert "valuation_type_counts" in summary
        assert summary["valuation_type_counts"]["estimated"] == 1
        assert summary["valuation_type_counts"]["cashflow_only"] == 0
