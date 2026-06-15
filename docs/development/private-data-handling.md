# Private Data Handling

## Rules

1. **Never commit real portfolio data** — use local_data/ or private_data/
2. **Never commit provider cookies/tokens** — use environment variables
3. **Never commit generated reports with private amounts** — use local_reports/
4. **Sanitize before sharing** — remove real amounts, fund codes, personal info
5. **Use synthetic demo fixtures** — all data in repo is synthetic

## .gitignore Patterns

The following patterns are in .gitignore:

- local_data/
- private_data/
- local_reports/
- *.private.json
- *.private.yaml
- *.private.csv

## Workflow

1. Copy template from examples/user_portfolio_templates/
2. Fill in real data in local_data/
3. Run fund-agent with --input local_data/your_portfolio.json
4. Output to local_reports/
5. Sanitize before sharing

## Sanitization Checklist

- [ ] Remove or replace real monetary amounts
- [ ] Replace real fund codes with generic labels
- [ ] Remove personal identifiers
- [ ] Remove provider credentials
- [ ] Verify no secrets in output

## Manual Transaction Bootstrap Flow (v0.10.1)

For users bootstrapping their first portfolio from Alipay transaction records:

```
private_data/alipay_record.private.csv
  → user/agent manually reads and verifies
  → private_data/manual_transactions.private.csv
  → private_data/portfolio_input.private.json
  → fund-agent analyze-portfolio
  → local_reports/real_portfolio_report.md
```

Key rules:
- **Raw Alipay CSV must be placed in `private_data/`** — never commit to GitHub.
- **`manual_transactions.private.csv` must also be in `private_data/`** — never commit.
- **The current holding snapshot (`portfolio_input.private.json`) is the authoritative source of current positions.**
- **Manual transaction records are supplementary evidence, not a complete accounting ledger.**
- **Do not guess `fund_code`** — leave empty/null if unknown.
- **Do not fabricate `units`, `NAV`, or `cost_basis`** — leave null/unknown if unknown.
- **`pending_confirmation` entries must not be treated as confirmed holdings.**
- **fund-agent core does not read private credentials, make network requests, pull real-time NAVs, or place orders.**
- **No Alipay importer, no product name parser, no automatic cost/NAV calculation.**

See `docs/development/manual-portfolio-maintenance.md` for full details.

## Template Files

- examples/user_portfolio_templates/fund_portfolio_input_template.json
- examples/user_portfolio_templates/transaction_history_template.csv
- examples/user_portfolio_templates/manual_transaction_entries_template.csv
- examples/user_portfolio_templates/risk_profile_template.yaml
- examples/user_portfolio_templates/investment_constraints_template.yaml
- examples/user_portfolio_templates/provider_data_snapshot_template.json
