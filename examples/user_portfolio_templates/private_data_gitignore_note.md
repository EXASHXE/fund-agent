# Private Data Handling

**Never commit real portfolio data, provider cookies/tokens, or generated reports with private amounts.**

## Local directories for private data

- `local_data/` — private portfolio input files
- `private_data/` — sensitive provider snapshots
- `local_reports/` — generated reports with real amounts

## .gitignore patterns

The following patterns are in `.gitignore`:

- `local_data/`
- `private_data/`
- `local_reports/`
- `*.private.json`
- `*.private.yaml`
- `*.private.csv`

## Rules

1. Use synthetic demo data in all repo fixtures
2. Real portfolio data lives only in local_data/ or private_data/
3. Generated reports with real amounts go to local_reports/
4. Sanitize before sharing any output
5. Never commit cookies, tokens, or API keys
6. Provider snapshots with real data must not be committed
