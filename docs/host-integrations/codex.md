# Codex Integration Cookbook

Codex can work with a repository/source checkout. Treat `fund-agent` as a
skill pack plus deterministic runtime, not as a daemon or autonomous planner.

Codex should inspect:

- [`skillpack/fund-agent.skillpack.yaml`](../../skillpack/fund-agent.skillpack.yaml)
- [`skills/fund-analysis/SKILL.md`](../../skills/fund-analysis/SKILL.md)
- [`docs/contracts/fund-analysis-input-contract.v1.md`](../contracts/fund-analysis-input-contract.v1.md)
- [`docs/contracts/fund-analysis-artifacts.v1.md`](../contracts/fund-analysis-artifacts.v1.md)
- [`docs/install/runtime-bridge-cli.md`](../install/runtime-bridge-cli.md)

Codex may run tests and local CLI commands in a checkout when permitted by the
user and environment. Codex should not add provider SDKs to `fund-agent`, should
not make `fund-agent` fetch data directly, and should preserve the host-owned
data boundary.

## Useful Commands

```bash
python scripts/run_skill.py --list-skills --pretty
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --validate-input --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --pretty
python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_personal_report_quality_input.json --emit-report markdown --output report.md
python scripts/run_skill.py --skill fund_analysis --output-schema --pretty
```

## Safe Codex Workflow

1. Inspect the manifest and contracts.
2. Validate sample or host-supplied input.
3. Run the example or host-provided envelope.
4. Read `warnings`, `report_limitations`, and `report_quality_gate`.
5. Do not convert `suggested_rebalance_plan` into formal trades.
6. Use `decision_support` only with an `EvidenceGraph` when formal
   `Decision` / `ExecutionLedger` output is needed.

Host owns data fetching, provider SDKs, credentials, MCP providers,
orchestration, memory, retries, and final UX. `fund-agent` must not fetch NAV,
holdings, benchmark, peer, news, sentiment, market, macro, or calendar data by
itself.
