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

## Template Files

- examples/user_portfolio_templates/fund_portfolio_input_template.json
- examples/user_portfolio_templates/transaction_history_template.csv
- examples/user_portfolio_templates/risk_profile_template.yaml
- examples/user_portfolio_templates/investment_constraints_template.yaml
- examples/user_portfolio_templates/provider_data_snapshot_template.json
