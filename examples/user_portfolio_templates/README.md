# User Portfolio Templates

Templates and synthetic demo data for fund-agent portfolio input.

## Files

| File | Purpose |
|------|---------|
| `fund_portfolio_input_template.json` | Empty portfolio input template |
| `fund_portfolio_input_demo.json` | Synthetic demo portfolio (3 funds) |
| `provider_data_snapshot_template.json` | Empty provider snapshot template |
| `provider_data_snapshot_demo.json` | Synthetic demo provider snapshot |
| `transaction_history_template.csv` | Transaction history CSV template |
| `risk_profile_template.yaml` | Risk profile YAML template |
| `investment_constraints_template.yaml` | Investment constraints YAML template |
| `private_data_gitignore_note.md` | Private data handling rules |
| `.gitignore.example` | Example gitignore for private data |

## Usage

1. Copy the template files to `local_data/` (outside repo)
2. Fill in your real portfolio data
3. Run fund-agent with `--input local_data/your_portfolio.json`
4. Generated reports go to `local_reports/` (outside repo)

## Safety

- **Never commit real portfolio data** — use `local_data/` or `private_data/`
- **Never commit provider cookies/tokens** — use environment variables
- **Never commit generated reports with private amounts** — use `local_reports/`
- All demo data in this directory is **synthetic**
- See `private_data_gitignore_note.md` for full rules
