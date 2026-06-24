---
name: fund-agent-privacy-audit
description: Use when checking that no private data or API keys would be committed to the repository
---

# fund-agent Privacy Audit

Run the privacy checker to verify no private data would be committed.

## Runner

```bash
bin/fund-agent-privacy-check
```

## Checks

1. No tracked private directories (private_data/, local_data/, local_reports/, eval_workspace/)
2. No tracked .private files (*.private.json, *.private.yaml, *.private.csv)
3. No API keys, tokens, cookies, or Authorization headers in tracked files
4. No raw Alipay IDs in tracked files
5. No tracked .env files

## Safety Rules

- NEVER print API key values even when reporting violations
- NEVER read private file contents
- Report violations by file path and pattern type only

## Exit Codes

- 0: No privacy violations
- 1: Privacy violations detected
