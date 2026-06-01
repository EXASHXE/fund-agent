"""Deterministic dates tests — verify no date.today() / datetime.now() usage in pure tools."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from datetime import datetime

from src.tools.portfolio.analysis import calculate_short_term_budget_usage
from src.tools.portfolio.transaction import detect_trading_discipline_flags
from src.schemas.transaction import FundTransaction


def test_no_date_today_in_pure_tools():
    """Verify that pure tool files do not call date.today() or datetime.now()."""
    tool_files = [
        Path("src/tools/portfolio/analysis.py"),
        Path("src/tools/portfolio/transaction.py"),
    ]
    for path in tool_files:
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                code = ast.unparse(node) if hasattr(ast, "unparse") else ast.dump(node)
                # Allow _parse_date which uses datetime.strptime, not .now/.today
                assert "date.today()" not in code, f"date.today() found in {path}: {code}"
                assert "datetime.today()" not in code, f"datetime.today() found in {path}: {code}"
                assert "datetime.now()" not in code, f"datetime.now() found in {path}: {code}"


def test_calculate_short_term_budget_none_as_of_date_returns_warning():
    positions = [
        {
            "fund_code": "F001",
            "fund_name": "Fund One",
            "current_value": 50000.0,
            "total_cost": 48000.0,
        }
    ]
    transactions = [
        {"action": "BUY", "amount": 5000.0, "date": "2026-05-15"},
        {"action": "SELL", "amount": 2000.0, "date": "2026-05-20"},
    ]
    risk_profile = {"risk_level": "moderate", "short_term_trade_budget_pct": 0.1}

    result = calculate_short_term_budget_usage(
        positions=positions,
        transactions=transactions,
        risk_profile=risk_profile,
        as_of_date=None,
    )
    assert result["used"] == 0.0
    assert result["exceeded"] is False
    assert "warning" in result
    assert "as_of_date" in result["warning"]


def test_calculate_short_term_budget_same_input_same_output():
    positions = [
        {"fund_code": "F001", "fund_name": "Fund One", "current_value": 50000.0, "total_cost": 48000.0}
    ]
    transactions = [
        {"action": "BUY", "amount": 5000.0, "date": "2026-05-15"},
        {"action": "SELL", "amount": 2000.0, "date": "2026-05-20"},
    ]
    risk_profile = {"risk_level": "moderate", "short_term_trade_budget_pct": 0.1}

    r1 = calculate_short_term_budget_usage(
        positions=positions, transactions=transactions,
        risk_profile=risk_profile, as_of_date="2026-06-01",
    )
    r2 = calculate_short_term_budget_usage(
        positions=positions, transactions=transactions,
        risk_profile=risk_profile, as_of_date="2026-06-01",
    )
    assert r1 == r2
    assert r1["used"] > 0


def test_detect_trading_discipline_flags_no_as_of_date_skips_dca():
    txn = FundTransaction(
        transaction_id="tx-1",
        fund_code="F001",
        fund_name="Fund One",
        action="BUY",
        date="2026-04-01",
        amount=1000.0,
        shares=100.0,
    )
    risk_profile = {"short_term_trade_budget_pct": 0.1}
    portfolio = {
        "total_value": 100000.0,
        "dca_funds": {"F001": {"interval_days": 30}},
    }
    flags = detect_trading_discipline_flags(
        transactions=[txn],
        risk_profile=risk_profile,
        portfolio=portfolio,
        as_of_date="",
    )
    flag_types = {f["type"] for f in flags}
    assert "dca_interruption" not in flag_types
    assert any(
        "as_of_date" in f.get("message", "").lower() or "dca_interruption_skipped" in f.get("type", "")
        for f in flags
    )


def test_detect_trading_discipline_flags_same_input_same_output():
    txn = FundTransaction(
        transaction_id="tx-1",
        fund_code="F001",
        fund_name="Fund One",
        action="BUY",
        date="2026-04-01",
        amount=1000.0,
        shares=100.0,
    )
    risk_profile = {"short_term_trade_budget_pct": 0.1}
    portfolio = {
        "total_value": 100000.0,
        "dca_funds": {"F001": {"interval_days": 30}},
    }

    r1 = detect_trading_discipline_flags(
        transactions=[txn],
        risk_profile=risk_profile,
        portfolio=portfolio,
        as_of_date="2026-06-01",
    )
    r2 = detect_trading_discipline_flags(
        transactions=[txn],
        risk_profile=risk_profile,
        portfolio=portfolio,
        as_of_date="2026-06-01",
    )
    assert r1 == r2


def test_decision_support_deterministic_same_input_same_output():
    """When deterministic=true, same inputs produce identical decision IDs and created_at."""
    from src.schemas.evidence import EvidenceItem
    from src.schemas.evidence_graph import EvidenceGraph
    from src.schemas.skill import SkillInput
    from src.skills_runtime.decision_support import DecisionSupportSkill

    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id="ev-positive",
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="positive signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "quant_tool"},
        )
    )

    def run():
        return DecisionSupportSkill().run(SkillInput(
            task_id="det-test",
            step_id="deterministic-1",
            skill_name="decision_support",
            payload={
                "evidence_graph": graph.to_dict(),
                "objective": "review fund",
                "time_horizon": "1 year",
                "portfolio_context": {"as_of_date": "2026-01-01T00:00:00"},
                "deterministic": True,
            },
        ))

    o1 = run()
    o2 = run()

    assert o1.status == "OK"
    assert o2.status == "OK"
    d1 = o1.artifacts["decision"]
    d2 = o2.artifacts["decision"]
    assert d1["decision_id"] == d2["decision_id"]
    assert d1["created_at"] == d2["created_at"]
    assert d1["created_at"] == "2026-01-01T00:00:00"
    assert d1["decision_id"] == d2["decision_id"]


def test_decision_support_deterministic_audit_no_datetime_now():
    """Deterministic audit trail must not contain live timestamps."""
    from src.schemas.evidence import EvidenceItem
    from src.schemas.evidence_graph import EvidenceGraph
    from src.schemas.skill import SkillInput
    from src.skills_runtime.decision_support import DecisionSupportSkill

    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id="ev-positive",
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="positive signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "quant_tool"},
        )
    )

    output = DecisionSupportSkill().run(SkillInput(
        task_id="det-audit",
        step_id="deterministic-2",
        skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review fund",
            "time_horizon": "1 year",
            "portfolio_context": {"as_of_date": "2026-01-01T00:00:00"},
            "deterministic": True,
        },
    ))

    audit_trail = output.artifacts.get("audit_trail", [])
    # In deterministic mode, generated_at line should use the deterministic timestamp
    for entry in audit_trail:
        if entry.startswith("Generated at:"):
            assert entry == "Generated at: 2026-01-01T00:00:00"
