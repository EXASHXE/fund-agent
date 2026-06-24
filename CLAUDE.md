# CLAUDE.md — Claude Code Agent Rules

## Mandatory

- Use `bin/fund-agent-e2e` for E2E portfolio reconstruction runs
- Run `bin/fund-agent-privacy-check` before every commit
- Never commit private artifacts (private_data/, local_data/, local_reports/, *.private.*, .env*)
- Never execute broker/trade operations — fund-agent is analysis-only
- Never use stale round3 envelopes

## Prohibited

- No merge, tag, or release unless explicitly told
- No pushing to master
- No printing private file contents into chat
- No printing API key / env var values

## E2E Invocation

```
/fund-agent:e2e-report --as-of YYYY-MM-DD
```

## Install

```
claude --plugin-dir <repo-root>
```
