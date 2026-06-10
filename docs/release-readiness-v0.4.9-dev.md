# v0.4.9-dev Release Readiness Audit

This is an audit note for a v0.4.9-dev release-ready candidate. It is not a
release tag, and no PyPI or npm package has been published from this note.

## Current Status

`fund-agent` is ready for final candidate validation as a host-agnostic,
Markdown-first, source-checkout runtime skill pack. Source checkout plus
`scripts/run_skill.py` remains the canonical deterministic Python execution
path for external hosts.

## What Works

- Skill discovery through `skillpack/fund-agent.skillpack.yaml`.
- Runtime bridge JSON-in / JSON-out execution through `scripts/run_skill.py`.
- `fund_analysis` JSON output with report artifacts and diagnostics.
- `fund_analysis --emit-report markdown` deterministic Markdown output.
- `decision_support` formal `Decision` and `ExecutionLedger` artifacts.
- `thesis_generation` `thesis_draft` artifact output.
- `news_research` and `sentiment_analysis` with host-injected canned MCP
  adapter responses.
- OpenCode plugin metadata + doc-reader behavior.

## Host Responsibilities

External hosts own data fetching, provider SDKs, network access, credentials,
MCP providers, orchestration, memory, retries, final UX, and any
brokerage/order execution that might exist outside `fund-agent`.

## Not Provided By fund-agent

- Live NAV, holdings, benchmark, peer, fee, manager, market, macro, calendar,
  news, or sentiment data fetching.
- Provider SDK integration or network calls.
- Broker/order execution.
- Autonomous planner, daemon, server, scheduler, or HTTP API.
- OpenCode Python runtime execution.

## Test Gates

Candidate validation uses:

- `python -m compileall src tests scripts`
- pytest subsets for schemas, architecture, skills_runtime, tools,
  integration, runtime_bridge, contracts, docs, golden, skillpack, and install
- `python -m pytest -q`
- `node --check opencode.plugin.js`
- `bash scripts/check_plugin_gate.sh`

## Optional Checks

- Local build metadata dry-run may skip when the `build` module is unavailable.
- Editable install smoke may skip when `venv`, `pip`, or offline editable
  install support is unavailable.
- Source-checkout host smoke remains the canonical deterministic runtime gate.

## Boundary Guarantees

- `fund_analysis` does not emit formal `Decision` or `ExecutionLedger`
  artifacts.
- `thesis_generation` does not emit formal `Decision` or `ExecutionLedger`
  artifacts.
- `decision_support` is the only runtime skill that may emit formal `Decision`
  or `ExecutionLedger` artifacts.
- `decision_support` structured justification fields remain part of formal
  decisions.
- `news_research` and `sentiment_analysis` call only host-injected MCP
  adapters.
- Host-visible errors remain canonical `code` / `message` / `details` /
  `recoverable` objects.
- OpenCode plugin remains metadata + doc-reader only and does not invoke
  Python.

## Non-Release Statements

- No tag was created.
- No PyPI or npm package was published.
- Fixtures are fake/sample data only.
- This project does not guarantee production investment advice.
