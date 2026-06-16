"""Tests for portfolio input bridge — deterministic, no network."""

from __future__ import annotations

from src.skills_runtime.workflow.portfolio_input_bridge import bridge_portfolio_input


def _demo_input(**overrides):
    base = {
        "schema_version": "fund_portfolio_input.v1",
        "user_question": "分析一下",
        "analysis_mode": "report_only",
        "as_of_date": "2024-12-31",
        "base_currency": "CNY",
        "holdings": [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "current_value": 50000,
                "units": 32700,
                "cost_basis": 45000,
                "cost_basis_confidence": "exact",
                "holding_days": 365,
                "unrealized_pnl": 5000,
                "unrealized_pnl_pct": 11.1,
            },
        ],
        "cash_allocation": {"cash_available": 5000},
        "provider_data_snapshot_ref": "provider_data_snapshot_demo.json",
        "risk_profile_ref": "risk_profile_template.yaml",
        "constraints_ref": "investment_constraints_template.yaml",
        "user_preferences": {"language": "zh-CN", "report_style": "detailed"},
        "data_quality": {"missing_fields": [], "estimated_fields": []},
        "privacy_mode": "full",
    }
    base.update(overrides)
    return base


class TestBridgePortfolioInput:
    def test_complete_input(self):
        result = bridge_portfolio_input(_demo_input())
        assert "payload" in result
        payload = result["payload"]
        assert payload["portfolio"]["total_value"] == 50000
        assert payload["portfolio"]["cash_available"] == 5000
        assert len(payload["portfolio"]["positions"]) == 1
        assert payload["user_question"] == "分析一下"
        assert payload["analysis_mode"] == "report_only"

    def test_missing_cost_basis(self):
        inp = _demo_input()
        inp["holdings"][0]["cost_basis"] = None
        inp["holdings"][0]["cost_basis_confidence"] = "unknown"
        result = bridge_portfolio_input(inp)
        assert any("MISSING_COST_BASIS" in w for w in result["warnings"])

    def test_missing_provider_snapshot(self):
        inp = _demo_input(provider_data_snapshot_ref="")
        result = bridge_portfolio_input(inp)
        assert any("NO_PROVIDER_SNAPSHOT" in w for w in result["warnings"])

    def test_report_only_mode(self):
        result = bridge_portfolio_input(_demo_input(analysis_mode="report_only"))
        assert result["payload"]["analysis_mode"] == "report_only"

    def test_formal_trade_decision_mode(self):
        result = bridge_portfolio_input(_demo_input(analysis_mode="formal_trade_decision"))
        assert any("FORMAL_DECISION_REQUESTED" in w for w in result["warnings"])

    def test_empty_holdings(self):
        result = bridge_portfolio_input(_demo_input(holdings=[]))
        assert any("EMPTY_HOLDINGS" in w for w in result["warnings"])

    def test_privacy_mode(self):
        result = bridge_portfolio_input(_demo_input(privacy_mode="anonymous"))
        assert result["payload"]["privacy_mode"] == "anonymous"

    def test_no_broker_execution_fields(self):
        result = bridge_portfolio_input(_demo_input())
        payload_str = str(result["payload"])
        assert "broker" not in payload_str.lower()
        assert "order" not in payload_str.lower()
        assert "execution" not in payload_str.lower()

    def test_invalid_input(self):
        result = bridge_portfolio_input("not a dict")
        assert any("INVALID_INPUT" in w for w in result["warnings"])

    def test_data_quality_missing_fields(self):
        inp = _demo_input(data_quality={"missing_fields": ["003003.cost_basis"], "estimated_fields": []})
        result = bridge_portfolio_input(inp)
        assert any("DATA_QUALITY_MISSING" in w for w in result["warnings"])


class TestCostBasisHandling:
    def test_missing_cost_basis_does_not_produce_zero(self):
        inp = _demo_input()
        inp["holdings"][0]["cost_basis"] = None
        inp["holdings"][0]["cost_basis_confidence"] = "unknown"
        result = bridge_portfolio_input(inp)
        pos = result["payload"]["portfolio"]["positions"][0]
        assert "total_cost" not in pos, "total_cost must not be set when cost_basis is missing"
        assert pos.get("total_cost", "SENTINEL") != 0, "total_cost must not be 0 when cost_basis is unknown"

    def test_missing_cost_basis_sets_explicit_marker(self):
        inp = _demo_input()
        inp["holdings"][0]["cost_basis"] = None
        result = bridge_portfolio_input(inp)
        pos = result["payload"]["portfolio"]["positions"][0]
        assert pos.get("cost_basis_missing") is True
        assert pos.get("cost_basis_confidence") == "unknown"

    def test_known_cost_basis_maps_correctly(self):
        result = bridge_portfolio_input(_demo_input())
        pos = result["payload"]["portfolio"]["positions"][0]
        assert pos["total_cost"] == 45000
        assert "cost_basis_missing" not in pos

    def test_missing_cost_basis_without_confidence_field(self):
        inp = _demo_input()
        del inp["holdings"][0]["cost_basis"]
        if "cost_basis_confidence" in inp["holdings"][0]:
            del inp["holdings"][0]["cost_basis_confidence"]
        result = bridge_portfolio_input(inp)
        pos = result["payload"]["portfolio"]["positions"][0]
        assert "total_cost" not in pos
        assert pos.get("cost_basis_missing") is True
        assert any("MISSING_COST_BASIS" in w for w in result["warnings"])

    def test_mixed_cost_basis_holdings(self):
        inp = _demo_input()
        inp["holdings"].append(
            {
                "fund_code": "003003",
                "fund_name": "华夏现金增利货币",
                "current_value": 20000,
                "cost_basis": None,
                "cost_basis_confidence": "unknown",
            }
        )
        result = bridge_portfolio_input(inp)
        positions = result["payload"]["portfolio"]["positions"]
        assert positions[0]["total_cost"] == 45000
        assert "total_cost" not in positions[1]
        assert positions[1].get("cost_basis_missing") is True
        assert any("MISSING_COST_BASIS" in w and "003003" in w for w in result["warnings"])

    def test_no_broker_order_execution_fields(self):
        inp = _demo_input()
        inp["holdings"][0]["cost_basis"] = None
        result = bridge_portfolio_input(inp)
        payload_str = str(result["payload"])
        assert "broker" not in payload_str.lower()
        assert "order" not in payload_str.lower()
        assert "execution" not in payload_str.lower()


class TestBridgePortfolioInputSnapshots:
    """Tests for optional host-layer snapshot injection."""

    def test_no_snapshots_by_default(self):
        result = bridge_portfolio_input(_demo_input())
        payload = result["payload"]
        assert payload.get("provider_snapshot_present") is False
        assert payload.get("news_snapshot_present") is False
        assert payload.get("factor_snapshot_present") is False
        assert payload.get("kg_context_snapshot_present") is False

    def test_nonexistent_snapshot_path_warns(self, tmp_path):
        result = bridge_portfolio_input(
            _demo_input(),
            provider_snapshot_path=str(tmp_path / "nonexistent.json"),
            news_snapshot_path=str(tmp_path / "nonexistent_news.json"),
            factor_snapshot_path=str(tmp_path / "nonexistent_factor.json"),
            kg_context_path=str(tmp_path / "nonexistent_kg.json"),
        )
        assert any("PROVIDER_SNAPSHOT_LOAD_FAILED" in w for w in result["warnings"])
        assert any("NEWS_SNAPSHOT_LOAD_FAILED" in w for w in result["warnings"])
        assert any("FACTOR_SNAPSHOT_LOAD_FAILED" in w for w in result["warnings"])
        assert any("KG_CONTEXT_LOAD_FAILED" in w for w in result["warnings"])

    def test_valid_provider_snapshot_injected(self, tmp_path):
        snapshot = {"snapshot_type": "provider_data_snapshot", "nav_data": {"000001": 1.5}}
        snap_path = tmp_path / "provider_snapshot.private.json"
        snap_path.write_text(__import__("json").dumps(snapshot), encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            provider_snapshot_path=str(snap_path),
        )
        payload = result["payload"]
        assert payload.get("provider_snapshot_present") is True
        assert payload.get("provider_data_snapshot") == snapshot

    def test_valid_news_snapshot_injected(self, tmp_path):
        snapshot = {"snapshot_type": "news_snapshot", "items": []}
        snap_path = tmp_path / "news_snapshot.private.json"
        snap_path.write_text(__import__("json").dumps(snapshot), encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            news_snapshot_path=str(snap_path),
        )
        payload = result["payload"]
        assert payload.get("news_snapshot_present") is True
        assert payload.get("news_snapshot") == snapshot

    def test_valid_factor_snapshot_injected(self, tmp_path):
        snapshot = {"snapshot_type": "factor_snapshot", "portfolio_factors": {}}
        snap_path = tmp_path / "factor_snapshot.private.json"
        snap_path.write_text(__import__("json").dumps(snapshot), encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            factor_snapshot_path=str(snap_path),
        )
        payload = result["payload"]
        assert payload.get("factor_snapshot_present") is True
        assert payload.get("factor_snapshot") == snapshot

    def test_valid_kg_context_injected(self, tmp_path):
        snapshot = {"snapshot_type": "knowledge_graph_context", "entities": []}
        snap_path = tmp_path / "kg_context.private.json"
        snap_path.write_text(__import__("json").dumps(snapshot), encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            kg_context_path=str(snap_path),
        )
        payload = result["payload"]
        assert payload.get("kg_context_snapshot_present") is True
        assert payload.get("kg_context_snapshot") == snapshot

    def test_all_snapshots_injected_together(self, tmp_path):
        for name, data in [
            ("provider.private.json", {"snapshot_type": "provider_data_snapshot"}),
            ("news.private.json", {"snapshot_type": "news_snapshot"}),
            ("factor.private.json", {"snapshot_type": "factor_snapshot"}),
            ("kg.private.json", {"snapshot_type": "knowledge_graph_context"}),
        ]:
            (tmp_path / name).write_text(__import__("json").dumps(data), encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            provider_snapshot_path=str(tmp_path / "provider.private.json"),
            news_snapshot_path=str(tmp_path / "news.private.json"),
            factor_snapshot_path=str(tmp_path / "factor.private.json"),
            kg_context_path=str(tmp_path / "kg.private.json"),
        )
        payload = result["payload"]
        assert payload.get("provider_snapshot_present") is True
        assert payload.get("news_snapshot_present") is True
        assert payload.get("factor_snapshot_present") is True
        assert payload.get("kg_context_snapshot_present") is True

    def test_invalid_json_snapshot_warns(self, tmp_path):
        snap_path = tmp_path / "bad.json"
        snap_path.write_text("not valid json {{{", encoding="utf-8")

        result = bridge_portfolio_input(
            _demo_input(),
            provider_snapshot_path=str(snap_path),
        )
        assert any("PROVIDER_SNAPSHOT_LOAD_FAILED" in w for w in result["warnings"])
        assert result["payload"].get("provider_snapshot_present") is False

    def test_backward_compatible_no_snapshot_args(self):
        """Calling bridge_portfolio_input without snapshot args still works."""
        result = bridge_portfolio_input(_demo_input())
        assert "payload" in result
        assert "warnings" in result
        assert result["payload"]["portfolio"]["total_value"] == 50000
