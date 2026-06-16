#!/usr/bin/env python3
"""Import Alipay transaction records from CSV.

Parses GB18030/GBK/UTF-8-sig encoded Alipay CSV files, classifies
transactions (buy/sell/dividend/conversion/refund/fee/unknown), and
outputs normalized_transactions.private.json.

Usage:
    python scripts/import_alipay_transactions.py \
        --input private_data/alipay_record.private.csv \
        --output private_data/normalized_transactions.private.json

This is a host-layer script. It does not compute NAV, units, or current_value.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Alipay CSV column names (Chinese)
_ALIPAY_COLUMNS = {
    "trade_no": "交易号",
    "merchant_order_no": "商户订单号",
    "trade_time": "交易创建时间",
    "payment_time": "付款时间",
    "last_update_time": "最近修改时间",
    "trade_source": "交易来源地",
    "type": "类型",
    "counterparty": "交易对方",
    "product_name": "商品名称",
    "amount": "金额（元）",
    "status": "交易状态",
    "service_fee": "服务费（元）",
    "refund_status": "退款状态",
    "remark": "备注",
}

# Classification keywords for fund transactions
_BUY_KEYWORDS = ["买入", "购买", "申购", "定投"]
_SELL_KEYWORDS = ["卖出", "赎回"]
_DIVIDEND_KEYWORDS = ["分红", "收益发放"]
_CONVERSION_KEYWORDS = ["转换", "转入", "转出"]
_REFUND_KEYWORDS = ["退款", "退回"]
_FEE_KEYWORDS = ["手续费", "管理费", "托管费"]


def _try_read_csv(path: Path) -> list[dict[str, str]]:
    """Read CSV trying multiple encodings."""
    for encoding in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
        try:
            with open(path, encoding=encoding, newline="") as f:
                # Alipay CSV may have leading metadata lines; find the header
                lines = f.readlines()
            header_idx = _find_header_line(lines, encoding)
            if header_idx is None:
                continue
            reader = csv.DictReader(lines[header_idx:], fieldnames=None)
            rows = []
            for row in reader:
                if row:
                    rows.append(dict(row))
            return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Cannot decode {path} with any supported encoding")


def _find_header_line(lines: list[str], encoding: str) -> int | None:
    """Find the line index containing the CSV header row."""
    for i, line in enumerate(lines):
        # Look for known Alipay header markers
        if "交易号" in line or "交易创建时间" in line or "商品名称" in line:
            return i
    # Fallback: first line with comma separation
    for i, line in enumerate(lines):
        if "," in line and len(line.split(",")) >= 5:
            return i
    return None


def _redact_id(raw_id: str) -> str:
    """Hash a raw ID for privacy, keeping first 4 chars for traceability."""
    if not raw_id or len(raw_id) < 4:
        return hashlib.sha256(raw_id.encode()).hexdigest()[:12]
    prefix = raw_id[:4]
    hashed = hashlib.sha256(raw_id.encode()).hexdigest()[:8]
    return f"{prefix}...{hashed}"


def _parse_amount(val: str) -> float | None:
    """Parse a monetary amount string, returning None on failure."""
    if not val or val.strip() in ("", "-"):
        return None
    try:
        return float(val.strip().replace(",", "").replace("¥", ""))
    except (ValueError, TypeError):
        return None


def _parse_datetime(val: str) -> str | None:
    """Parse a datetime string to ISO format date."""
    if not val or val.strip() == "":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(val.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _classify_action(product_name: str, trade_type: str, amount: float | None) -> str:
    """Classify a transaction into buy/sell/dividend/conversion/refund/fee/unknown."""
    text = f"{product_name} {trade_type}"

    # Check refund first (can co-occur with buy keywords)
    for kw in _REFUND_KEYWORDS:
        if kw in text:
            return "refund"

    # Check fee
    for kw in _FEE_KEYWORDS:
        if kw in text:
            return "fee"

    # Check conversion
    for kw in _CONVERSION_KEYWORDS:
        if kw in text:
            return "conversion"

    # Check dividend
    for kw in _DIVIDEND_KEYWORDS:
        if kw in text:
            return "dividend"

    # Check sell
    for kw in _SELL_KEYWORDS:
        if kw in text:
            return "sell"

    # Check buy
    for kw in _BUY_KEYWORDS:
        if kw in text:
            return "buy"

    # Negative amount might indicate sell/refund
    if amount is not None and amount < 0:
        return "sell"

    return "unknown"


def _extract_fund_code(product_name: str, counterparty: str) -> str | None:
    """Try to extract a fund code (6 digits) from product name or counterparty."""
    import re

    text = f"{product_name} {counterparty}"
    matches = re.findall(r"\b(\d{6})\b", text)
    return matches[0] if matches else None


def import_alipay_csv(
    input_path: Path,
    output_path: Path,
    redact_ids: bool = True,
) -> dict[str, Any]:
    """Import Alipay CSV and produce normalized transactions.

    Returns summary dict with counts.
    """
    rows = _try_read_csv(input_path)
    transactions = []
    classification_counts = {"buy": 0, "sell": 0, "dividend": 0, "conversion": 0, "refund": 0, "fee": 0, "unknown": 0}

    for row in rows:
        # Map Chinese column names to values
        product_name = row.get("商品名称", row.get("商品名称 ", ""))
        trade_type = row.get("类型", row.get("类型 ", ""))
        counterparty = row.get("交易对方", row.get("交易对方 ", ""))
        raw_amount = row.get("金额（元）", row.get("金额(元)", row.get("金额", "")))
        trade_time_raw = row.get("交易创建时间", row.get("付款时间", row.get("交易时间", "")))
        raw_trade_no = row.get("交易号", row.get("商户订单号", ""))
        status = row.get("交易状态", row.get("状态", ""))
        remark = row.get("备注", "")

        # Skip non-fund rows or empty rows
        if not product_name and not trade_type:
            continue

        amount = _parse_amount(raw_amount)
        trade_date = _parse_datetime(trade_time_raw)
        action = _classify_action(product_name, trade_type, amount)
        fund_code = _extract_fund_code(product_name, counterparty)

        # Only keep fund-related transactions
        if action == "unknown" and not fund_code:
            continue

        classification_counts[action] += 1

        txn = {
            "transaction_id": _redact_id(raw_trade_no) if redact_ids and raw_trade_no else f"alipay_{len(transactions):06d}",
            "source": "alipay",
            "source_ref": _redact_id(raw_trade_no) if redact_ids and raw_trade_no else None,
            "trade_date": trade_date,
            "action": action,
            "amount": abs(amount) if amount is not None else None,
            "fund_code": fund_code,
            "fund_name": product_name if product_name else None,
            "counterparty": counterparty if counterparty else None,
            "status": status,
            "remark": remark if remark else None,
            "confirmation_type": "evidence_confirmed",
            "confirmation_source": "alipay",
            "confidence": "evidence_confirmed",
        }
        transactions.append(txn)

    output = {
        "schema_version": "normalized_alipay_transactions.v1",
        "source": "alipay_csv_import",
        "imported_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "redacted_ids": redact_ids,
        "transaction_count": len(transactions),
        "classification_counts": classification_counts,
        "transactions": transactions,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return {
        "total_transactions": len(transactions),
        "classification_counts": classification_counts,
        "fund_transactions": sum(v for k, v in classification_counts.items() if k != "unknown"),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Alipay transaction CSV")
    parser.add_argument("--input", required=True, help="Path to Alipay CSV file")
    parser.add_argument("--output", required=True, help="Output path for normalized transactions JSON")
    parser.add_argument("--no-redact", action="store_true", help="Do not redact trade IDs")
    args = parser.parse_args()

    result = import_alipay_csv(
        input_path=Path(args.input),
        output_path=Path(args.output),
        redact_ids=not args.no_redact,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
