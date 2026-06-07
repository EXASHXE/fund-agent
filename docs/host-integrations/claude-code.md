# Claude Code Integration Cookbook

Claude Code should use a source checkout, repository docs, and the runtime
bridge when deterministic local execution is available.

Before modifying code, read:

- [`README.md`](../../README.md)
- [`skillpack/fund-agent.skillpack.yaml`](../../skillpack/fund-agent.skillpack.yaml)
- [`skills/SKILL.md`](../../skills/SKILL.md)
- [`skills/fund-analysis/SKILL.md`](../../skills/fund-analysis/SKILL.md)
- [`docs/contracts/fund-analysis-input-contract.v1.md`](../contracts/fund-analysis-input-contract.v1.md)
- [`docs/contracts/fund-analysis-artifacts.v1.md`](../contracts/fund-analysis-artifacts.v1.md)
- [`docs/install/runtime-bridge-cli.md`](../install/runtime-bridge-cli.md)

Claude Code should keep host-owned data outside `fund-agent` unless using
examples or fixtures. Do not insert provider SDKs or network clients into the
core runtime. Preserve contracts and run the plugin gate after changes.

## Recommended Verification

```bash
python -m pytest -q
bash scripts/check_plugin_gate.sh
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --validate-input --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_personal_report_quality_input.json --emit-report markdown --output report.md
```

Host owns data fetching, provider SDKs, credentials, MCP providers,
orchestration, retries, memory, and final UX. `fund-agent` must not fetch NAV,
holdings, benchmark, peer, news, sentiment, market, macro, or calendar data by
itself.

Formal decisions require `decision_support`; `fund_analysis` reports and
suggested plans are not formal `Decision` or `ExecutionLedger` output.
