# User Portfolio Templates

Templates and synthetic demo data for fund-agent portfolio input.

## Files

| File | Purpose |
|------|---------|
| `fund_portfolio_input_template.json` | Empty portfolio input template |
| `fund_portfolio_input_demo.json` | Synthetic demo portfolio (3 funds) |
| `portfolio_input_with_transactions.example.json` | Portfolio input with transactions (v0.10.6+) |
| `provider_data_snapshot_template.json` | Empty provider snapshot template |
| `provider_data_snapshot_demo.json` | Synthetic demo provider snapshot |
| `transaction_history_template.csv` | Transaction history CSV template |
| `manual_transaction_entries_template.csv` | Manual transaction entries CSV template (v0.10.1 bootstrap) |
| `risk_profile_template.yaml` | Risk profile YAML template |
| `investment_constraints_template.yaml` | Investment constraints YAML template |
| `private_data_gitignore_note.md` | Private data handling rules |
| `.gitignore_example` | Example gitignore for private data |

## Usage

1. Copy the template files to `local_data/` (outside repo)
2. Fill in your real portfolio data
3. Run fund-agent with `--input local_data/your_portfolio.json`
4. Generated reports go to `local_reports/` (outside repo)

## Manual Transaction Bootstrap (v0.10.1)

For users building their first portfolio from Alipay transaction records:

1. Export Alipay history to `private_data/alipay_record.private.csv` (never commit)
2. Manually curate entries into `private_data/manual_transactions.private.csv` using `manual_transaction_entries_template.csv`
3. Build current holding snapshot as `private_data/portfolio_input.private.json`
4. Run fund-agent with `--input private_data/portfolio_input.private.json`
5. Reports go to `local_reports/`

Key rules:
- **Raw Alipay CSV must not be committed** — keep in `private_data/`
- **Do not guess fund_code** — leave empty if unknown
- **Do not fabricate units/NAV/cost_basis** — leave null if unknown
- **Current holding snapshot is the authoritative source**
- **pending_confirmation entries are not confirmed holdings**
- **No Alipay importer, no auto-parsing, no auto-calculation**

See `docs/development/manual-portfolio-maintenance.md` for full details.

## Checking Your Setup (v0.10.6+)

After placing files in `private_data/`, run the private data doctor:

```bash
bin/fund-agent-private-data-doctor --pretty
```

This validates:
- Identity override YAML has `funds` list with valid six-digit `fund_code`
- NAV override JSON has valid dates (`YYYY-MM-DD`) and positive values
- No private files are tracked by git
- Output contains counts only — no real fund names, amounts, or IDs

## Safety

- **Never commit real portfolio data** — use `local_data/` or `private_data/`
- **Never commit provider cookies/tokens** — use environment variables
- **Never commit generated reports with private amounts** — use `local_reports/`
- All demo data in this directory is **synthetic**
- See `private_data_gitignore_note.md` for full rules
