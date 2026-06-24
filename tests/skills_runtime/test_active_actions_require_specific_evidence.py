"""Tests that active actions with only fallback evidence fail the quality gate.

Verifies the active_trade_anchor_gate check in advisory_quality_gate.py
rejects active decisions (BUY, SELL, INCREASE, REDUCE) when the evidence
comes exclusively from fallback queries (theme_fallback, priority 5).
"""

from __future__ import annotations

from src.tools.workflow.advisory_quality_gate import evaluate_advisory_quality_gate


def _make_ds_output(action: str, evidence_anchors: list[dict] | None = None, blocked_by: list | None = None) -> dict:
    """Build a minimal decision_support output dict."""
    decision = {
        "action": action,
        "rationale_anchor": "anchor-1" if evidence_anchors else None,
    }
    if blocked_by is not None:
        decision["blocked_by"] = blocked_by

    anchor_diag: dict = {}
    if evidence_anchors is not None:
        anchor_diag["has_evidence_anchors"] = len(evidence_anchors) > 0
        anchor_diag["anchor_details"] = evidence_anchors
    else:
        anchor_diag["has_evidence_anchors"] = True

    return {
        "artifacts": {
            "decision": decision,
            "execution_ledger": {"ledger_summary": {"total_decisions": 1}},
            "evidence_anchor_diagnostics": anchor_diag,
            "risk_constraint_conflicts": {},
        }
    }


def _make_evidence_graph(items: list[dict] | None = None) -> dict:
    """Build a minimal evidence_graph dict."""
    if items is None:
        items = []
    eg_items: dict[str, dict] = {}
    for item in items:
        eg_items[item.get("evidence_id", f"ev-{len(eg_items)}")] = item
    return {"items": eg_items}


class TestActiveTradeAnchorGateFallbackOnly:
    """Active actions with only fallback evidence should FAIL the quality gate."""

    def test_buy_with_only_fallback_evidence_fails(self):
        """BUY decision backed only by fallback evidence should fail."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "FAIL"

    def test_sell_with_only_fallback_evidence_fails(self):
        """SELL decision backed only by fallback evidence should fail."""
        ds = _make_ds_output(
            "SELL",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
                {"evidence_id": "ev-2", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
                {"evidence_id": "ev-2", "query_type": "theme_fallback", "is_fallback_query": True},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "FAIL"

    def test_increase_with_only_fallback_evidence_fails(self):
        """INCREASE decision backed only by fallback evidence should fail."""
        ds = _make_ds_output(
            "INCREASE",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "FAIL"

    def test_reduce_with_only_fallback_evidence_fails(self):
        """REDUCE decision backed only by fallback evidence should fail."""
        ds = _make_ds_output(
            "REDUCE",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "FAIL"


class TestActiveTradeAnchorGateWithSpecificEvidence:
    """Active actions with at least one specific (non-fallback) evidence should PASS."""

    def test_buy_with_holding_company_evidence_passes(self):
        """BUY with holding_company evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "holding_company", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "holding_company", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_buy_with_benchmark_evidence_passes(self):
        """BUY with benchmark evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "benchmark", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "benchmark", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_buy_with_fund_name_evidence_passes(self):
        """BUY with fund_name evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "fund_name", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "fund_name", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_buy_with_fund_code_evidence_passes(self):
        """BUY with fund_code evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "fund_code", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "fund_code", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_buy_with_fund_manager_evidence_passes(self):
        """BUY with fund_manager evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "fund_manager", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "fund_manager", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_buy_with_mixed_fallback_and_specific_evidence_passes(self):
        """BUY with both fallback and specific evidence should pass."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
                {"evidence_id": "ev-2", "query_type": "holding_company", "is_fallback_query": False},
            ],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
                {"evidence_id": "ev-2", "query_type": "holding_company", "is_fallback_query": False},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"


class TestActiveTradeAnchorGatePassiveActions:
    """Passive actions should not be affected by fallback-only evidence."""

    def test_wait_with_fallback_evidence_passes(self):
        """WAIT with only fallback evidence should pass (not an active action)."""
        ds = _make_ds_output(
            "WAIT",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"

    def test_hold_with_fallback_evidence_passes(self):
        """HOLD with only fallback evidence should pass."""
        ds = _make_ds_output(
            "HOLD",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"


class TestActiveTradeAnchorGateBlockedAction:
    """Blocked active actions should not fail the fallback gate."""

    def test_blocked_buy_with_fallback_evidence_passes(self):
        """A blocked BUY with only fallback evidence should pass (already blocked)."""
        ds = _make_ds_output(
            "BUY",
            evidence_anchors=[
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ],
            blocked_by=["risk_constraint"],
        )
        eg = _make_evidence_graph(
            [
                {"evidence_id": "ev-1", "query_type": "theme_fallback", "is_fallback_query": True},
            ]
        )
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            evidence_graph=eg,
            decision_support_output=ds,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"


class TestActiveTradeAnchorGateNoDecisionSupport:
    """When no decision_support output, the gate should pass (not applicable)."""

    def test_no_decision_support_passes(self):
        result = evaluate_advisory_quality_gate(
            fund_analysis_output={},
            decision_support_output=None,
        )
        gate = _find_check(result, "active_trade_anchor_gate")
        assert gate is not None
        assert gate["status"] == "PASS"


def _find_check(result: dict, check_id: str) -> dict | None:
    for c in result.get("checks", []):
        if c.get("id") == check_id:
            return c
    return None
