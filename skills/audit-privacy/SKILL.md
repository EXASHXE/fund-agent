---
name: audit-privacy
description: Use when checking that no private data or API keys would be committed to the repository
---

# Privacy Audit

Run the fund-agent privacy checker to verify no private data would be committed.

## Invocation

```
/fund-agent:audit-privacy
```

## What This Skill Does

Runs `bin/fund-agent-privacy-check` which scans the repository for:

1. Tracked private directories (private_data/, local_data/, local_reports/, eval_workspace/)
2. Tracked .private files (*.private.json, *.private.yaml, *.private.csv)
3. API keys, tokens, cookies, and Authorization headers in tracked files
4. Raw Alipay IDs in tracked files
5. Tracked .env files

## Runner

```bash
bin/fund-agent-privacy-check
```

The runner calls `python scripts/privacy_audit.py`.

## Safety Rules

- **NEVER** print API key values even when reporting violations
- Report violations by file path and pattern type only
- If violations are found, the runner exits non-zero
- Fix violations by adding paths to `.gitignore` and removing from git tracking

## Fixing Violations

If violations are found:

1. Add the offending path pattern to `.gitignore`
2. Remove from git tracking: `git rm --cached <path>`
3. Re-run the audit to confirm the fix

## Exit Codes

- 0: No privacy violations
- 1: Privacy violations detected
