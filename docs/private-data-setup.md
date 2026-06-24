# Personal Data Setup and Scenario Guide

This guide explains how to set up private data files, run the personal
portfolio E2E pipeline, and interpret the reconstruction scenarios
(A / B / C2 / D2).

## Private Data Directory Structure

```
private_data/
  alipay_record.private.csv          # Raw Alipay export (never committed)
  manual_transactions.private.csv    # Curated transaction entries
  portfolio_input.private.json       # Holdings snapshot + optional transactions
  fund_identity_overrides.private.yaml  # Manual fund code → identity mappings
  nav_overrides.private.json         # Trade-date NAV overrides for reconstruction
```

All files matching `*.private.*` and the `private_data/` directory are
in `.gitignore`. **Never commit real portfolio data.**

## Transaction Sources

The pipeline supports two transaction sources:

### Alipay CSV (default)

When an Alipay CSV file exists in `private_data/`, the pipeline imports
transactions from it automatically. This is the default and preferred source.

### portfolio_input.transactions (fallback)

When no Alipay CSV is available, the pipeline can use transactions embedded
in `portfolio_input.private.json`. This is useful for:

- Manual transaction entry without Alipay
- Curated transaction lists from other sources
- Testing with synthetic data

**Transaction schema** (inside `portfolio_input.private.json`):

```json
{
  "transactions": [
    {
      "trade_date": "2026-06-01",
      "fund_code": "000001",
      "fund_name": "示例基金A",
      "transaction_type": "buy",
      "amount": 100.00,
      "units": 81.00,
      "nav": 1.2345
    }
  ]
}
```

**Field rules**:
- `trade_date` (required): `YYYY-MM-DD` format
- `fund_code` (optional): If present, must be 6 digits
- `fund_name` (optional): Chinese names are OK here
- `transaction_type` (required): `buy`, `sell`, `dividend`, `fee`, `conversion_in`, `conversion_out`, `refund`, `unknown`
- `amount` (required): Numeric
- `units` (optional): Explicit share count
- `nav` (optional): Trade-date NAV

**Key differences from Alipay CSV**:
- `fund_code` is optional (name-only entries allowed)
- `units` and `nav` can be provided directly
- `confirmation_type` is `user_provided_private_input` (not `evidence_confirmed`)
- `latest_nav` alone does NOT create historical units

**Validation visibility** (v0.10.6+):

When portfolio_input.transactions contains invalid rows, the adapter:
- Marks each invalid transaction with `needs_manual_review: true` and `validation_status: "warning"`
- Reports `warning_count`, `invalid_count`, and `manual_review_count` in the summary
- The E2E pipeline surfaces these counts in `e2e_summary.json` and adds a pipeline warning
- The report mentions manual review needed in the reconstruction_status section
- Warning text contains counts only — no real fund names, amounts, or IDs

**Source precedence** (`--transaction-source` flag):

| Mode | Behavior |
|------|----------|
| `auto` (default) | Alipay CSV preferred; falls back to portfolio_input.transactions if no CSV |
| `alipay` | Only use Alipay CSV; error if missing; no fallback |
| `portfolio_input` | Only use portfolio_input.transactions; error if missing; ignores Alipay CSV |

To explicitly choose a source:
```bash
bin/fund-agent-e2e --transaction-source portfolio_input --skip-akshare --skip-news
```

## Override Files

### fund_identity_overrides.private.yaml

Maps fund names (from Alipay/product descriptions) to canonical fund
codes and metadata. Used when fund codes cannot be resolved automatically.

```yaml
funds:
  - raw_name: "示例基金A"
    fund_code: "110011"
    fund_name: "示例基金A"
  - raw_name: "示例基金B"
    fund_code: "000002"
    fund_name: "示例基金B"
```

Schema rules:
- Top-level key must be `funds` (a list)
- Each entry requires `raw_name` (Chinese names are OK here)
- `fund_code` must be a valid six-digit code if provided (empty string
  is allowed for unresolved identities)
- Chinese names may appear in `raw_name` and `fund_name`, but never in
  `resolved_fund_code`

### nav_overrides.private.json

Provides trade-date NAV values for reconstructing position units from
cashflow-only transaction history. Keys are `fund_code`, values are
date→NAV maps.

```json
{
  "110011": {
    "2026-01-15": 2.5432,
    "2026-02-10": 2.6100
  }
}
```

Schema rules:
- Top-level keys must be six-digit fund codes
- Date keys must be in `YYYY-MM-DD` format
- NAV values must be positive numbers (int or float)
- Zero, negative, or non-numeric values will be flagged as errors

## Reconstruction Scenarios

The E2E pipeline handles four reconstruction scenarios depending on what
data is available:

### Scenario A: Raw Alipay CSV, No Overrides

**Input**: `alipay_record.private.csv` only.

**Expected behavior**:
- Transactions parsed: yes (`txns > 0`)
- Ledger transactions: yes (`ledger txns > 0`)
- Identity schema version: `fund_identity_resolution.v2`
- `valid_fund_codes_count`: 0 or very low
- `name_only_count > 0` (fund names not resolved to codes)
- `resolved_fund_code`: null for name-only entries
- Report does **not** show fake `0.00` values
- Report does **not** label cashflow as valuation

### Scenario B: Alipay CSV + Identity Overrides, No NAV

**Input**: `alipay_record.private.csv` + `fund_identity_overrides.private.yaml`.

**Expected behavior**:
- `valid_fund_codes_count > 0`
- `manual_override_matches_count > 0`
- Status: `partial`
- `reconstruction_status`: `nav_unavailable`
- `portfolio_input_source`: `unavailable`
- Warnings do **not** include "no resolved fund codes"

### Scenario C2: Alipay CSV + Identity Overrides + Trade-date NAV Overrides

**Input**: `alipay_record.private.csv` + identity overrides + `nav_overrides.private.json`.

**Expected behavior**:
- `reconstruction_status`: `reconstructed_from_ledger`
- Positions: `> 0`
- Estimated positions: `> 0`
- `cashflow_only` positions may exist
- `units_estimated` populated: `> 0`
- `current_value` populated: `> 0`
- Partial valuation coverage is clearly noted
- `estimated_current_value_total` is **not** presented as complete portfolio value

### Scenario D2: Existing portfolio_input Fallback

**Input**: `portfolio_input.private.json` (pre-built snapshot).

**Expected behavior**:
- When reconstruction is not available: `portfolio_input_source` = `existing_private_portfolio_input`
- Report does **not** use `reconstructed_from_ledger` wording
- Report clearly states cashflow comes from Alipay, valuation from existing private portfolio input

## Valuation Type Distinctions

The pipeline distinguishes four valuation types for positions:

| Type | Meaning | Report Treatment |
|------|---------|-----------------|
| `confirmed` | NAV-verified current value from provider | Full precision shown |
| `estimated` | Units estimated from cashflow + NAV overrides | Labeled as estimated |
| `cashflow_only` | Only transaction cashflow known, no NAV | No fake `0.00` value shown |
| `none` | No valuation data at all | Marked as missing |

### Valuation Quality (v0.10.6+)

Each position also has a `valuation_quality` label:

| Quality | Meaning |
|---------|---------|
| `estimated_full_coverage` | All buy/sell have trade-date NAV or explicit units |
| `estimated_partial_coverage` | Some trades missing NAV — value is approximate |
| `cashflow_only` | No units or current_value — cashflow only |
| `unavailable` | No data at all |
| `manual_review_required` | Conversion/refund/unknown present, or validation warnings |

### NAV Coverage (v0.10.6+)

Each position has a `nav_coverage_status`:

| Status | Meaning |
|--------|---------|
| `full` | All buy/sell have trade-date NAV or explicit units |
| `partial` | Some trades have NAV, but not all |
| `none` | No trade-date NAV available |
| `latest_only` | Only latest NAV available (cannot infer historical units) |

Key rules:
- `latest_nav` alone does NOT create historical units
- Explicit `units` from user input satisfy coverage without requiring NAV
- Stale NAV (>7 days domestic, >10 days QDII) triggers a warning
- QDII-like detection requires `is_qdii` from fund profile — no guessing

### Special Transaction Semantics (v0.10.6+)

| Type | Units Effect | Manual Review |
|------|-------------|---------------|
| buy/sell | Change units | No |
| dividend | No change | No |
| fee | No change | No |
| conversion_in/out | Ambiguous | Yes |
| refund | Ambiguous | Yes |
| unknown | Unknown | Yes |
| `none` | No valuation data at all | Marked as missing |

### Key Rules

- **cashflow_only** positions must **not** display fake `0.00` as current value.
- **estimated** positions must **not** be presented as confirmed/verified.
- **fallback** source must **not** be labeled as `reconstructed_from_ledger`.
- **Partial valuation coverage** means only some positions have NAV; the
  total is an estimate, not a complete portfolio market value.

## Running Scenarios

### Agent-facing evidence package (recommended)

For agent consumption, use `fund-agent-personal-run` which produces a complete
evidence package including `agent_context.md` for external agents:

```bash
# Deterministic mode (default: skip-akshare + skip-news)
bin/fund-agent-personal-run --skip-akshare --skip-news

# With live data (explicit opt-in)
bin/fund-agent-personal-run --no-skip-akshare --no-skip-news
```

See [Personal Run usage guide](usage/personal-run.md) for the full workflow.

### Direct E2E pipeline

```bash
# Scenario A: raw CSV only
bin/fund-agent-e2e --skip-akshare --skip-news

# Scenario B: add identity overrides
# (place fund_identity_overrides.private.yaml in private_data/)
bin/fund-agent-e2e --skip-akshare --skip-news

# Scenario C2: add NAV overrides
# (place nav_overrides.private.json in private_data/)
bin/fund-agent-e2e --skip-akshare --skip-news --as-of 2026-06-20

# Scenario D2: use existing portfolio_input
bin/fund-agent-e2e --skip-akshare --skip-news

# Dry run (no subprocess execution)
bin/fund-agent-e2e --dry-run
```

## Checking Your Setup

Run the private data doctor to verify your files are correctly structured:

```bash
bin/fund-agent-private-data-doctor --pretty
```

To check a custom directory:

```bash
bin/fund-agent-private-data-doctor --pretty --private-data-dir /path/to/custom_data
```

The doctor checks:
1. `private_data/` directory exists
2. CSV files present (count only, no content)
3. Identity overrides YAML exists and is parseable
4. Fund codes are valid six-digit numbers
5. NAV overrides JSON exists and is parseable
6. NAV dates are in `YYYY-MM-DD` format
7. NAV values are positive numbers
8. `portfolio_input.private.json` exists (optional)
9. `local_reports/` and `eval_workspace/` are gitignored
10. No private files are tracked by git

Output contains **counts only** — no real fund names, amounts, transaction IDs, or CSV content.

## Personal Health Report (v0.10.6+)

The E2E pipeline automatically includes a `personal_health_report` section in
`e2e_summary.json`. This provides a quick data-quality diagnostic:

- **overall_status**: `ok` / `partial` / `needs_data` / `needs_manual_review` / `unavailable`
- **confidence_level**: `high` / `medium` / `low` / `unavailable`
- **reason_codes**: Why the status isn't optimal (e.g., `nav_missing`, `partial_nav_coverage`)
- **fix_it_checklist**: Data-quality next steps to improve your report

To print only the health report:

```bash
bin/fund-agent-e2e --health-report-only --skip-akshare --skip-news
```

For agent consumption, use `fund-agent-personal-run` which produces
`agent_context.md` and `agent_context.json` alongside the health report:

```bash
bin/fund-agent-personal-run --skip-akshare --skip-news
```

See [Personal Health Report usage guide](usage/personal-health-report.md) and
[Personal Run usage guide](usage/personal-run.md) for details.

## Safety Boundaries

- fund-agent does **not** place orders or execute trades.
- fund-agent does **not** run an autonomous trading loop.
- `fund_analysis` does **not** output formal `Decision` objects.
- `suggested_rebalance_plan` is analysis advice, not trade instructions.
- Formal `Decision` / `ExecutionLedger` can only be produced by
  `decision_support` skill.
- Real E2E output stays in `local_reports/` — never commit.
