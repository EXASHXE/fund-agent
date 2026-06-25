#!/usr/bin/env python3
"""Build transaction ledger from Alipay evidence and planned transactions.

Merges evidence_confirmed Alipay transactions with rule_confirmed/pending/planned
transactions. Evidence overrides plan. Rule_confirmed is below evidence_confirmed.
Pending never becomes evidence_confirmed. Keeps audit trail.

Usage:
    python scripts/build_transaction_ledger.py \
        --alipay private_data/normalized_transactions.private.json \
        --planned private_data/planned_transactions.private.json \
        --output private_data/transaction_ledger.private.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Confirmation type precedence (higher = more authoritative)
_CONFIRMATION_PRECEDENCE = {
    "evidence_confirmed": 5,
    "rule_confirmed": 3,
    "pending_confirmation": 2,
    "projected": 1,
    "manual_review_required": 0,
}


def _parse_date(val) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _merge_key(txn: dict[str, Any]) -> str | None:
    """Create a merge key for matching Alipay evidence with planned transactions.

    Match on (fund_code, date, action) when possible.
    """
    fund_code = txn.get("fund_code")
    d = txn.get("trade_date") or txn.get("scheduled_date")
    action = txn.get("action", "buy")
    amount = txn.get("amount")
    if fund_code and d:
        return f"{fund_code}|{d}|{action}|{amount}"
    return None


def build_transaction_ledger(
    alipay_transactions: list[dict[str, Any]] | None = None,
    planned_transactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge Alipay evidence and planned transactions into a unified ledger.

    Rules:
    - Evidence_confirmed (Alipay) overrides plan entries for the same
      fund_code + date + action.
    - Rule_confirmed is below evidence_confirmed.
    - Pending never becomes evidence_confirmed.
    - Audit trail preserved for every merge decision.
    """
    alipay_txns = alipay_transactions or []
    planned_txns = planned_transactions or []

    # Index Alipay by merge key
    alipay_by_key: dict[str, dict[str, Any]] = {}
    for txn in alipay_txns:
        key = _merge_key(txn)
        if key:
            alipay_by_key[key] = txn

    merged = []
    audit_trail = []

    # Add all Alipay transactions as evidence_confirmed
    for txn in alipay_txns:
        entry = {
            "transaction_id": txn.get("transaction_id", f"alipay_{len(merged):06d}"),
            "source": "alipay",
            "fund_code": txn.get("fund_code"),
            "fund_name": txn.get("fund_name"),
            "trade_date": txn.get("trade_date"),
            "submitted_at": txn.get("submitted_at"),
            "action": txn.get("action", "unknown"),
            "amount": txn.get("amount"),
            "confirmation_type": "evidence_confirmed",
            "confirmation_source": txn.get("confirmation_source", "alipay"),
            "confidence": "evidence_confirmed",
            "source_ref": txn.get("source_ref"),
            "remark": txn.get("remark"),
            "audit": [{"action": "evidence_from_alipay", "source": "alipay_csv"}],
        }
        merged.append(entry)

    # Process planned transactions
    for txn in planned_txns:
        key = _merge_key(txn)
        fund_code = txn.get("fund_code")
        sched_date = txn.get("scheduled_date")
        action = txn.get("action", "buy")
        conf_type = txn.get("confirmation_type", "pending_confirmation")
        plan_id = txn.get("plan_id")

        # Check if Alipay evidence already covers this
        if key and key in alipay_by_key:
            audit_trail.append({
                "decision": "evidence_overrides_plan",
                "plan_transaction_id": txn.get("transaction_id"),
                "evidence_transaction_id": alipay_by_key[key].get("transaction_id"),
                "fund_code": fund_code,
                "date": sched_date,
                "reason": "Alipay evidence_confirmed takes precedence over planned transaction",
            })
            continue

        # Check for Alipay evidence on same fund_code + date (looser match)
        alipay_match = None
        for a_txn in alipay_txns:
            a_fund = a_txn.get("fund_code")
            a_date = a_txn.get("trade_date")
            a_action = a_txn.get("action")
            if a_fund == fund_code and a_date == sched_date and a_action == action:
                alipay_match = a_txn
                break

        if alipay_match:
            audit_trail.append({
                "decision": "evidence_overrides_plan",
                "plan_transaction_id": txn.get("transaction_id"),
                "evidence_transaction_id": alipay_match.get("transaction_id"),
                "fund_code": fund_code,
                "date": sched_date,
                "reason": "Alipay evidence_confirmed takes precedence",
            })
            continue

        # Planned transaction - keep as-is with its confirmation level
        entry = {
            "transaction_id": txn.get("transaction_id", f"plan_{len(merged):06d}"),
            "source": "investment_plan",
            "plan_id": plan_id,
            "fund_code": fund_code,
            "fund_name": txn.get("fund_name"),
            "trade_date": sched_date,
            "action": action,
            "amount": txn.get("amount"),
            "net_amount": txn.get("net_amount"),
            "fee_amount": txn.get("fee_amount"),
            "fee_source": txn.get("fee_source"),
            "confirmation_type": conf_type,
            "confirmation_source": txn.get("confirmation_source"),
            "confidence": txn.get("confidence"),
            "is_qdii": txn.get("is_qdii", False),
            "nav_available": txn.get("nav_available"),
            "audit": [{"action": "from_investment_plan", "plan_id": plan_id}],
        }
        merged.append(entry)

    # Sort by date
    merged.sort(key=lambda t: t.get("trade_date") or "9999-99-99")

    # Summary
    summary = {
        "total_transactions": len(merged),
        "evidence_confirmed": sum(1 for t in merged if t["confirmation_type"] == "evidence_confirmed"),
        "rule_confirmed": sum(1 for t in merged if t["confirmation_type"] == "rule_confirmed"),
        "pending_confirmation": sum(1 for t in merged if t["confirmation_type"] == "pending_confirmation"),
        "projected": sum(1 for t in merged if t["confirmation_type"] == "projected"),
        "manual_review_required": sum(1 for t in merged if t["confirmation_type"] == "manual_review_required"),
        "overridden_by_evidence": len(audit_trail),
    }

    return {
        "schema_version": "transaction_ledger.v1",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "transactions": merged,
        "audit_trail": audit_trail,
    }


def main():
    parser = argparse.ArgumentParser(description="Build transaction ledger")
    parser.add_argument("--alipay", default=None, help="Path to normalized Alipay transactions JSON")
    parser.add_argument("--planned", default=None, help="Path to planned transactions JSON")
    parser.add_argument("--output", required=True, help="Output path for transaction ledger JSON")
    args = parser.parse_args()

    alipay_txns = None
    if args.alipay:
        with open(args.alipay, encoding="utf-8") as f:
            data = json.load(f)
            alipay_txns = data.get("transactions", [])

    planned_txns = None
    if args.planned:
        with open(args.planned, encoding="utf-8") as f:
            data = json.load(f)
            planned_txns = data.get("transactions", [])

    result = build_transaction_ledger(
        alipay_transactions=alipay_txns,
        planned_transactions=planned_txns,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
