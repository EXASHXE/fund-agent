# Manual Portfolio Maintenance

This document describes how to bootstrap and maintain a personal fund portfolio
using manual transaction entries, without any automated Alipay CSV parsing,
fund-code guessing, or cost/NAV calculation.

## Overview

fund-agent v0.10.1 adds lightweight support for users who want to build their
first portfolio snapshot from Alipay transaction records and then maintain it
manually with the help of an external agent. The core runtime does **not**
read private credentials, make network requests, pull real-time NAVs, or place
orders.

## Key Principles

1. **Alipay raw CSV must be placed in `private_data/`** — never commit it to
   GitHub. The `.gitignore` pattern `private_data/` and `*.private.csv`
   already cover this.

2. **`manual_transactions.private.csv` must also be placed in
   `private_data/`** — never commit it to GitHub. This file contains your
   curated transaction entries extracted from Alipay records.

3. **The current holding snapshot (`portfolio_input.private.json`) is the
   authoritative source of current positions.** It represents what you
   actually hold right now, not what transaction history implies.

4. **Manual transaction records are supplementary evidence, not a complete
   accounting ledger.** They help you and the external agent understand how
   positions were built, but they do not replace the snapshot.

5. **If you do not know the `fund_code`, leave it empty/null.** Do not guess
   or fabricate fund codes. You can fill them in later when you find the
   correct code.

6. **If you do not know `units`, `NAV`, or `cost_basis`, leave them
   null/unknown.** Do not fabricate values. `cost_basis = null` means
   "unknown/missing" — it must never be forged as `0`.

7. **`pending_confirmation` entries must not be treated as confirmed
   holdings.** Only entries with `status = confirmed` should inform the
   current holding snapshot.

## Manual Transaction Bootstrap Flow

```
private_data/alipay_record.private.csv
  → user/agent manually reads and verifies
  → private_data/manual_transactions.private.csv
  → private_data/portfolio_input.private.json
  → fund-agent analyze-portfolio
  → local_reports/real_portfolio_report.md
```

### Step-by-Step

1. **Export your Alipay transaction history** to
   `private_data/alipay_record.private.csv`. This raw file is never committed
   and never parsed by fund-agent core.

2. **Manually review and curate** the records. For each fund-related
   transaction, create an entry in `manual_transactions.private.csv` using
   the template from `examples/user_portfolio_templates/manual_transaction_entries_template.csv`.

3. **Build your current holding snapshot** as
   `portfolio_input.private.json`. This is the authoritative source of your
   current positions. Fill in what you know; leave unknown fields as
   null/empty.

4. **Run fund-agent** with `--input private_data/portfolio_input.private.json`
   to generate analysis and reports in `local_reports/`.

5. **Ongoing maintenance**: When you have a new buy/sell/dividend event, tell
   the external agent (e.g. "新增一笔买入华夏成长混合5000元"), and the
   agent will update `manual_transactions.private.csv` and
   `portfolio_input.private.json` locally.

## CSV Template Fields

The `manual_transaction_entries_template.csv` has the following header:

```
date,fund_name,fund_code,action,amount,status,source_platform,source_ref,settlement_account,confidence,notes
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `date` | yes | Transaction date (YYYY-MM-DD) |
| `fund_name` | yes | Fund name as known to the user |
| `fund_code` | no | Fund code; leave empty if unknown |
| `action` | yes | Transaction type (see below) |
| `amount` | yes | Transaction amount in CNY |
| `status` | yes | Confirmation status (see below) |
| `source_platform` | no | Platform (e.g. alipay, tiantian) |
| `source_ref` | no | Reference ID from source platform |
| `settlement_account` | no | Bank/account used for settlement |
| `confidence` | no | Data confidence (high/medium/low) |
| `notes` | no | Free-text notes |

### Allowed `action` Values

| Action | Description |
|--------|-------------|
| `buy` | Purchase / subscription |
| `sell` | Redemption |
| `cash_dividend` | Cash dividend received |
| `conversion` | Fund conversion (in or out) |
| `refund` | Refund (e.g. failed subscription) |
| `fee` | Fee deduction |
| `transfer_in` | Transfer in from another platform |
| `transfer_out` | Transfer out to another platform |
| `manual_adjustment` | Manual correction entry |
| `unknown` | Unknown transaction type |

### Allowed `status` Values

| Status | Description |
|--------|-------------|
| `confirmed` | Verified and confirmed |
| `pending_confirmation` | Awaiting verification |
| `estimated` | Estimated/approximated amount |
| `cancelled` | Cancelled transaction |
| `unknown` | Unknown confirmation status |

## What fund-agent Does NOT Do

- **No Alipay raw CSV parser** — fund-agent core does not read or parse
  Alipay export files.
- **No product name parsing** — fund-agent does not extract fund codes from
  Alipay product descriptions.
- **No transaction normalization engine** — fund-agent does not automatically
  normalize or reconcile transaction records.
- **No automatic cost calculation** — fund-agent does not derive cost_basis
  from transaction history.
- **No automatic share/NAV calculation** — fund-agent does not compute units
  or NAV from raw transaction data.
- **No fund code inference** — fund-agent does not guess fund codes from
  names or descriptions.
- **No real-time NAV fetching** — fund-agent core makes no network requests.
- **No order execution** — fund-agent is not a broker.
- **No autonomous trading** — fund-agent does not initiate trades.

## Schema Extensions (v0.10.1)

The `fund_portfolio_input.schema.json` has been extended with optional fields
to support manual portfolio bootstrap. All new fields are optional and do not
break existing portfolio inputs.

### Top-Level Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `manual_transactions_ref` | string | Path to manual transaction CSV file |
| `manual_transactions_format` | enum (`manual_csv`) | Format of the manual transactions file |
| `source_notes` | string | Free-text notes about portfolio data source |
| `transaction_evidence_refs` | array of strings | References to supporting transaction records |
| `pending_transaction_count` | integer | Count of pending transactions |

### `data_quality` Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `validated_against_manual_transactions` | boolean | Cross-validated against manual records |
| `transaction_history_incomplete` | boolean | Known gaps in transaction history |
| `fund_code_missing` | boolean | Any holding missing fund_code |
| `units_missing` | boolean | Any holding missing units |
| `nav_missing` | boolean | Any holding missing NAV data |
| `cost_basis_partial` | boolean | Cost basis only partially available |

### Holding-Level Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_platform` | string | Platform where holding originates |
| `holding_source` | enum (`manual_snapshot`, `provider_snapshot`, `transaction_derived`, `unknown`) | How the holding was obtained |
| `source_notes` | string | Free-text notes about holding source |
| `transaction_evidence_refs` | array of strings | References to supporting transactions |
| `pending_transaction_count` | integer | Pending transactions for this holding |
