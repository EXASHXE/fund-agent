# Private Data Local Run Example

## Setup

1. Copy template to local_data/:
```bash
cp examples/user_portfolio_templates/fund_portfolio_input_template.json local_data/my_portfolio.json
```

2. Fill in real data in local_data/my_portfolio.json

3. Run analysis:
```bash
fund-agent analyze-portfolio --input local_data/my_portfolio.json --format markdown --output local_reports/my_report.md
```

## Safety

- local_data/ is in .gitignore — never committed
- local_reports/ is in .gitignore — never committed
- Sanitize before sharing:
  - Remove real amounts
  - Replace fund codes with generic labels
  - Remove personal info

## What NOT to do

- Do not commit local_data/ or local_reports/
- Do not share reports with real amounts
- Do not store credentials in portfolio input files
