"""Transaction-derived current holding discovery — M7.20.

Determines which funds from a transaction ledger are likely still held,
based on transaction lifecycle analysis (buys, sells, conversions, dividends,
refunds). Only identity-verified funds can reach current_position_confirmed;
unverified funds are capped at probable or manual_review.

Key rules:
- Only identity-verified funds enter current_position_confirmed.
- Buy-only funds → current_position_probable (no sells/conversions out).
- Full sell/conversion out → closed_position_probable.
- Dividend/refund only → history_only (does not create current holding).
- Holdings snapshot can upgrade probable → confirmed.
- Incomplete transaction chains → manual_review_required.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


# ── Lifecycle status enumeration ─────────────────────────────────────────

HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED = "current_position_confirmed"
HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE = "current_position_probable"
HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE = "closed_position_probable"
HOLDING_LIFECYCLE_HISTORY_ONLY = "history_only"
HOLDING_LIFECYCLE_CONVERSION_ONLY = "conversion_only"
HOLDING_LIFECYCLE_PENDING_ONLY = "pending_only"
HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED = "manual_review_required"

VALID_LIFECYCLE_STATUSES = frozenset({
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_HISTORY_ONLY,
    HOLDING_LIFECYCLE_CONVERSION_ONLY,
    HOLDING_LIFECYCLE_PENDING_ONLY,
    HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED,
})

# Statuses that represent a current holding (for valuation eligibility)
_CURRENT_HOLDING_STATUSES = frozenset({
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
})


@dataclass
class CurrentHoldingCandidate:
    """A fund's current holding status derived from transaction analysis."""

    fund_code: str = ""
    identity_status: str = ""  # provider_verified, name_only, etc.
    lifecycle_status: str = HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED
    buy_count: int = 0
    sell_count: int = 0
    conversion_in_count: int = 0
    conversion_out_count: int = 0
    dividend_count: int = 0
    refund_count: int = 0
    pending_count: int = 0
    unknown_count: int = 0
    gross_buy_amount: float = 0.0
    gross_sell_amount: float = 0.0
    net_cashflow_amount: float = 0.0
    latest_transaction_date: str = ""
    evidence_sources: list[str] = field(default_factory=list)
    confidence: str = "low"  # low, medium, high
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "identity_status": self.identity_status,
            "lifecycle_status": self.lifecycle_status,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "conversion_in_count": self.conversion_in_count,
            "conversion_out_count": self.conversion_out_count,
            "dividend_count": self.dividend_count,
            "refund_count": self.refund_count,
            "pending_count": self.pending_count,
            "unknown_count": self.unknown_count,
            "gross_buy_amount": self.gross_buy_amount,
            "gross_sell_amount": self.gross_sell_amount,
            "net_cashflow_amount": self.net_cashflow_amount,
            "latest_transaction_date": self.latest_transaction_date,
            "evidence_sources": self.evidence_sources,
            "confidence": self.confidence,
            "blocking_reasons": self.blocking_reasons,
        }


@dataclass
class HoldingDiscoverySummary:
    """Aggregate summary of holding discovery results."""

    ledger_fund_count: int = 0
    identity_verified_fund_count: int = 0
    current_position_confirmed_count: int = 0
    current_position_probable_count: int = 0
    closed_position_probable_count: int = 0
    history_only_count: int = 0
    conversion_only_count: int = 0
    pending_only_count: int = 0
    manual_review_required_count: int = 0
    blocking_reasons: list[str] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_fund_count": self.ledger_fund_count,
            "identity_verified_fund_count": self.identity_verified_fund_count,
            "current_position_confirmed_count": self.current_position_confirmed_count,
            "current_position_probable_count": self.current_position_probable_count,
            "closed_position_probable_count": self.closed_position_probable_count,
            "history_only_count": self.history_only_count,
            "conversion_only_count": self.conversion_only_count,
            "pending_only_count": self.pending_only_count,
            "manual_review_required_count": self.manual_review_required_count,
            "blocking_reasons": self.blocking_reasons,
            "source_notes": self.source_notes,
        }


# ── Identity verification check ──────────────────────────────────────────

_IDENTITY_VERIFIED_STATUSES = frozenset({
    "provider_verified",
    "verified",
    "user_verified_override",
})


def _is_identity_verified(identity_status: str) -> bool:
    """Check if a fund's identity is verified enough for current_position_confirmed."""
    return identity_status in _IDENTITY_VERIFIED_STATUSES


# ── Core discovery logic ─────────────────────────────────────────────────


def _classify_transaction_action(txn: dict[str, Any]) -> str:
    """Classify a single transaction into a canonical action category.

    Returns one of: buy, sell, conversion_in, conversion_out, dividend,
    refund, pending, fee, unknown.
    """
    action = txn.get("action", "").lower()
    pending = txn.get("pending", False)

    if pending:
        return "pending"

    # Map raw actions to canonical categories
    if action in ("buy", "申购", "定投"):
        return "buy"
    if action in ("sell", "赎回"):
        return "sell"
    if action == "conversion":
        # Determine direction from product name or remark
        product_name = txn.get("fund_name", "") or txn.get("product_name", "")
        remark = txn.get("remark", "") or ""
        text = f"{product_name} {remark}"
        if "转出" in text or "转换出" in text:
            return "conversion_out"
        if "转入" in text or "转换至" in text or "转换入" in text:
            return "conversion_in"
        # Ambiguous — treat as conversion_out for the source fund
        # (the conversion_in will be a separate transaction for the target fund)
        return "conversion_out"
    if action in ("dividend",):
        return "dividend"
    if action in ("refund",):
        return "refund"
    if action in ("fee",):
        return "fee"

    # Check product_name keywords for unclassified transactions
    product_name = txn.get("fund_name", "") or txn.get("product_name", "")
    if product_name:
        for kw in ("买入", "购买", "申购", "定投"):
            if kw in product_name:
                return "buy"
        for kw in ("卖出", "赎回"):
            if kw in product_name:
                return "sell"
        for kw in ("转换至", "转入"):
            if kw in product_name:
                return "conversion_in"
        for kw in ("转出",):
            if kw in product_name:
                return "conversion_out"
        for kw in ("分红", "收益发放"):
            if kw in product_name:
                return "dividend"
        for kw in ("退款", "退回"):
            if kw in product_name:
                return "refund"
        for kw in ("确认中",):
            if kw in product_name:
                return "pending"
        # Check remark for keywords too
        remark = txn.get("remark", "") or ""
        for kw in ("买入", "购买", "申购", "定投"):
            if kw in remark:
                return "buy"

    return "unknown"


def _aggregate_transactions_by_fund(
    transactions: Sequence[dict[str, Any]],
    identity_resolution: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Aggregate transactions by fund_code, computing lifecycle counts.

    Returns dict mapping fund_code → aggregate stats.
    """
    # Build identity lookup: fund_code → identity_verification_status
    identity_lookup: dict[str, str] = {}
    name_to_code: dict[str, str] = {}
    if identity_resolution:
        # Support both "funds" and "resolutions" keys
        fund_list = identity_resolution.get("funds", identity_resolution.get("resolutions", []))
        for fund in fund_list:
            fc = fund.get("resolved_fund_code") or fund.get("fund_code", "")
            ivs = fund.get("identity_verification_status", "")
            if fc:
                identity_lookup[fc] = ivs
                # Map all name variants to the same code
                for name_key in ("raw_fund_name", "fund_name", "normalized_name", "raw_reference"):
                    name = fund.get(name_key, "")
                    if name:
                        name_to_code[name] = fc

    fund_stats: dict[str, dict[str, Any]] = {}

    for txn in transactions:
        # Resolve fund_code — try direct code first, then name lookups
        fund_code = txn.get("fund_code", "") or ""
        if not fund_code:
            # Try multiple name fields in order of specificity
            for name_field in ("fund_name", "normalized_name", "product_name"):
                name = txn.get(name_field, "")
                if name and name in name_to_code:
                    fund_code = name_to_code[name]
                    break

        if not fund_code:
            continue  # Skip transactions with no resolvable fund_code

        if fund_code not in fund_stats:
            identity_status = identity_lookup.get(fund_code, "name_only")
            fund_stats[fund_code] = {
                "fund_code": fund_code,
                "identity_status": identity_status,
                "buy_count": 0,
                "sell_count": 0,
                "conversion_in_count": 0,
                "conversion_out_count": 0,
                "dividend_count": 0,
                "refund_count": 0,
                "pending_count": 0,
                "fee_count": 0,
                "unknown_count": 0,
                "gross_buy_amount": 0.0,
                "gross_sell_amount": 0.0,
                "latest_transaction_date": "",
                "evidence_sources": set(),
            }

        stats = fund_stats[fund_code]
        action = _classify_transaction_action(txn)
        amount = txn.get("amount")
        if amount is not None:
            amount = abs(float(amount))
        else:
            amount = 0.0

        if action == "buy":
            stats["buy_count"] += 1
            stats["gross_buy_amount"] += amount
        elif action == "sell":
            stats["sell_count"] += 1
            stats["gross_sell_amount"] += amount
        elif action == "conversion_in":
            stats["conversion_in_count"] += 1
            stats["gross_buy_amount"] += amount
        elif action == "conversion_out":
            stats["conversion_out_count"] += 1
            stats["gross_sell_amount"] += amount
        elif action == "dividend":
            stats["dividend_count"] += 1
        elif action == "refund":
            stats["refund_count"] += 1
            stats["gross_sell_amount"] += amount
        elif action == "pending":
            stats["pending_count"] += 1
            stats["gross_buy_amount"] += amount
        elif action == "fee":
            stats["fee_count"] += 1
        else:
            stats["unknown_count"] += 1

        # Track latest date
        trade_date = txn.get("trade_date", "")
        if trade_date and trade_date > stats["latest_transaction_date"]:
            stats["latest_transaction_date"] = trade_date

        # Track evidence source
        source = txn.get("source", "") or txn.get("confirmation_source", "")
        if source:
            stats["evidence_sources"].add(source)

    return fund_stats


def _determine_lifecycle_status(
    stats: dict[str, Any],
    identity_verified: bool,
    holdings_snapshot_funds: set[str] | None = None,
) -> tuple[str, list[str], str]:
    """Determine lifecycle status from aggregated transaction stats.

    Returns (lifecycle_status, blocking_reasons, confidence).
    """
    buy_count = stats.get("buy_count", 0)
    sell_count = stats.get("sell_count", 0)
    conversion_in_count = stats.get("conversion_in_count", 0)
    conversion_out_count = stats.get("conversion_out_count", 0)
    dividend_count = stats.get("dividend_count", 0)
    refund_count = stats.get("refund_count", 0)
    pending_count = stats.get("pending_count", 0)
    unknown_count = stats.get("unknown_count", 0)

    has_buy = buy_count > 0 or conversion_in_count > 0
    has_sell = sell_count > 0
    has_conversion_out = conversion_out_count > 0
    has_conversion_in = conversion_in_count > 0
    has_dividend = dividend_count > 0
    has_refund = refund_count > 0
    has_pending = pending_count > 0
    has_unknown = unknown_count > 0
    has_any_outflow = has_sell or has_conversion_out

    blocking_reasons: list[str] = []

    # Net cashflow analysis
    gross_buy = stats.get("gross_buy_amount", 0.0)
    gross_sell = stats.get("gross_sell_amount", 0.0)
    net_cashflow = gross_buy - gross_sell

    # ── Dividend/refund only → history_only ──────────────────────────
    if not has_buy and not has_any_outflow and has_dividend and not has_refund and not has_pending:
        return HOLDING_LIFECYCLE_HISTORY_ONLY, [], "low"

    if not has_buy and not has_any_outflow and has_refund and not has_dividend and not has_pending:
        return HOLDING_LIFECYCLE_HISTORY_ONLY, [], "low"

    # ── Dividend + refund only → history_only ────────────────────────
    if not has_buy and not has_any_outflow and (has_dividend or has_refund) and not has_pending:
        return HOLDING_LIFECYCLE_HISTORY_ONLY, [], "low"

    # ── Pending only → pending_only ──────────────────────────────────
    if has_pending and not has_buy and not has_any_outflow:
        return HOLDING_LIFECYCLE_PENDING_ONLY, [], "low"

    # ── Conversion out only → conversion_only ────────────────────────
    if has_conversion_out and not has_buy and not has_sell and not has_conversion_in:
        return HOLDING_LIFECYCLE_CONVERSION_ONLY, [], "low"

    # ── Buy-only (no sells, no conversions out) → current_position_probable ──
    if has_buy and not has_any_outflow:
        if not identity_verified:
            blocking_reasons.append("identity_unverified")
            return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

        if has_unknown:
            blocking_reasons.append("unknown_transactions_in_chain")
            return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "medium"

        # Check if holdings snapshot confirms
        fund_code = stats.get("fund_code", "")
        if holdings_snapshot_funds and fund_code in holdings_snapshot_funds:
            return HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED, [], "high"

        # Without snapshot, can only be probable
        return HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE, [], "medium"

    # ── Buy + sell (full sell likely) → closed_position_probable ─────
    if has_buy and has_sell:
        # If net cashflow is near zero or negative, likely fully sold
        sell_ratio = gross_sell / gross_buy if gross_buy > 0 else 1.0

        if not identity_verified:
            blocking_reasons.append("identity_unverified")
            return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

        if sell_ratio >= 0.95:
            # Nearly all sold → closed
            return HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE, [], "medium"

        if sell_ratio >= 0.5:
            # Partial sell — unclear if still holding
            blocking_reasons.append("partial_sell_unclear_remaining_position")
            return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

        # Low sell ratio — likely still holding
        fund_code = stats.get("fund_code", "")
        if holdings_snapshot_funds and fund_code in holdings_snapshot_funds:
            return HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED, [], "high"

        return HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE, [], "medium"

    # ── Conversion out with buy → closed or manual_review ────────────
    if has_buy and conversion_out_count > 0:
        if not identity_verified:
            blocking_reasons.append("identity_unverified")
            return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

        # Conversion out suggests position closed
        if buy_count == conversion_out_count:
            return HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE, [], "medium"

        # Mixed — some buys, some conversion outs
        blocking_reasons.append("mixed_buy_and_conversion_out")
        return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

    # ── Sell-only (no buys in ledger) → closed_position_probable ─────
    if has_any_outflow and not has_buy:
        return HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE, [], "medium"

    # ── Unknown transactions → manual_review ─────────────────────────
    if has_unknown:
        blocking_reasons.append("unknown_transactions")
        return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"

    # ── Fallback: manual_review ──────────────────────────────────────
    blocking_reasons.append("unclassifiable_transaction_pattern")
    return HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED, blocking_reasons, "low"


def discover_current_holdings(
    transactions: Sequence[dict[str, Any]],
    identity_resolution: dict[str, Any] | None = None,
    holdings_snapshot_funds: set[str] | None = None,
) -> tuple[list[CurrentHoldingCandidate], HoldingDiscoverySummary]:
    """Discover current holdings from transaction ledger and identity resolution.

    Args:
        transactions: Normalized transaction ledger entries.
        identity_resolution: Fund identity resolution result dict.
        holdings_snapshot_funds: Set of fund_codes present in holdings snapshot.

    Returns:
        Tuple of (candidates list, summary).
    """
    fund_stats = _aggregate_transactions_by_fund(transactions, identity_resolution)

    candidates: list[CurrentHoldingCandidate] = []
    summary = HoldingDiscoverySummary()
    summary.ledger_fund_count = len(fund_stats)

    if holdings_snapshot_funds:
        summary.source_notes.append("holdings_snapshot_loaded")

    # Count identity-verified funds
    identity_verified_count = 0
    for stats in fund_stats.values():
        if _is_identity_verified(stats.get("identity_status", "")):
            identity_verified_count += 1
    summary.identity_verified_fund_count = identity_verified_count

    # Classify each fund
    for fund_code, stats in sorted(fund_stats.items()):
        identity_verified = _is_identity_verified(stats.get("identity_status", ""))
        lifecycle_status, blocking_reasons, confidence = _determine_lifecycle_status(
            stats, identity_verified, holdings_snapshot_funds,
        )

        candidate = CurrentHoldingCandidate(
            fund_code=fund_code,
            identity_status=stats.get("identity_status", ""),
            lifecycle_status=lifecycle_status,
            buy_count=stats.get("buy_count", 0),
            sell_count=stats.get("sell_count", 0),
            conversion_in_count=stats.get("conversion_in_count", 0),
            conversion_out_count=stats.get("conversion_out_count", 0),
            dividend_count=stats.get("dividend_count", 0),
            refund_count=stats.get("refund_count", 0),
            pending_count=stats.get("pending_count", 0),
            unknown_count=stats.get("unknown_count", 0),
            gross_buy_amount=stats.get("gross_buy_amount", 0.0),
            gross_sell_amount=stats.get("gross_sell_amount", 0.0),
            net_cashflow_amount=stats.get("gross_buy_amount", 0.0) - stats.get("gross_sell_amount", 0.0),
            latest_transaction_date=stats.get("latest_transaction_date", ""),
            evidence_sources=sorted(stats.get("evidence_sources", set())),
            confidence=confidence,
            blocking_reasons=blocking_reasons,
        )
        candidates.append(candidate)

        # Update summary counts
        if lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED:
            summary.current_position_confirmed_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE:
            summary.current_position_probable_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE:
            summary.closed_position_probable_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_HISTORY_ONLY:
            summary.history_only_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_CONVERSION_ONLY:
            summary.conversion_only_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_PENDING_ONLY:
            summary.pending_only_count += 1
        elif lifecycle_status == HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED:
            summary.manual_review_required_count += 1

        if blocking_reasons:
            summary.blocking_reasons.extend(blocking_reasons)

    return candidates, summary


def is_current_holding(lifecycle_status: str) -> bool:
    """Check if a lifecycle status represents a current holding."""
    return lifecycle_status in _CURRENT_HOLDING_STATUSES
