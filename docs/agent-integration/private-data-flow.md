# Private Data Flow

## Rules

1. **Never commit real portfolio data** — use `local_data/` or `private_data/`
2. **Never commit provider cookies/tokens** — use environment variables
3. **Never commit generated reports with private amounts** — use `local_reports/`
4. **Sanitize before sharing** — remove real amounts, fund codes, and personal info
5. **Use synthetic demo fixtures** — all data in repo is synthetic

## Local Directories

- `local_data/` — private portfolio input files
- `private_data/` — sensitive provider snapshots
- `local_reports/` — generated reports with real amounts

## .gitignore Patterns

- `local_data/`
- `private_data/`
- `local_reports/`
- `*.private.json`
- `*.private.yaml`
- `*.private.csv`

## Workflow

1. Copy template from `examples/user_portfolio_templates/`
2. Fill in real data in `local_data/`
3. Run fund-agent with `--input local_data/your_portfolio.json`
4. Output to `local_reports/`
5. Sanitize before sharing
