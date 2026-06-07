# Hermes Integration Cookbook

Treat `fund-agent` as a host-agnostic skill pack. Discover skills through
[`skillpack/fund-agent.skillpack.yaml`](../../skillpack/fund-agent.skillpack.yaml)
and read the corresponding `skills/<slug>/SKILL.md` file before execution.

If Hermes supports Markdown skill ingestion, point it at the hyphenated skill
docs under `skills/`. If Hermes supports subprocess tools, wire
`scripts/run_skill.py` as a host-owned command from a source checkout. If the
host has no subprocess integration, use the docs and contracts as agent
guidance.

Useful bridge commands:

```bash
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --validate-input --pretty
python scripts/run_skill.py --skill fund_analysis --output-schema --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_personal_report_quality_input.json --emit-report markdown --output report.md
```

Hermes owns data fetching, provider SDKs, credentials, MCP providers,
orchestration, memory, retries, and final UX. `fund-agent` must not fetch NAV,
holdings, benchmark, peer, news, sentiment, market, macro, or calendar data by
itself.
Host owns data fetching, provider SDKs, credentials, MCP providers,
orchestration, memory, retries, and final UX.

Do not turn `fund-agent` into a daemon, server, provider bundle, or autonomous
planner. Formal decisions require `decision_support`.
