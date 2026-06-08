# Host Integration Cookbooks

This directory collects host-specific integration cookbooks for external
agents and host runtimes.

`fund-agent` is a host-agnostic, Markdown-first, externally installable
personal fund analysis skill pack. It provides deterministic Python runtime
skills that can be called by direct import or through the runtime bridge CLI.
External hosts own planning, orchestration, data fetching, provider credentials,
MCP providers, memory, retries, and final UX.

`fund-agent` is not an autonomous planner, daemon, server, provider SDK bundle,
data fetcher, or replacement for host orchestration.

## Canonical Flow

1. Discover skills from [`skillpack/fund-agent.skillpack.yaml`](../../skillpack/fund-agent.skillpack.yaml).
2. Read the relevant Markdown skill, usually [`skills/fund-analysis/SKILL.md`](../../skills/fund-analysis/SKILL.md).
3. Inspect the input contract:
   `python scripts/run_skill.py --skill fund_analysis --explain-input --pretty`
4. Validate host-supplied input:
   `python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --validate-input --pretty`
5. Run `fund_analysis` through the runtime bridge or direct Python import.
6. Inspect `status`, `warnings`, `errors`, `data_completeness`, and
   `report_quality_gate`.
7. Render deterministic Markdown when desired:
   `python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_personal_report_quality_input.json --emit-report markdown --output report.md`
8. Optionally compile evidence and call `decision_support` for formal
   `Decision` / `ExecutionLedger` output.

For fake personal fund scenarios that exercise common host-supplied data
shapes, see
[`examples/scenarios/README.md`](../../examples/scenarios/README.md).

## Boundary Rules

- The host owns data fetching, credentials, provider SDKs, MCP providers,
  memory, retries, planning, orchestration, and final UX.
- `fund-agent` must not fetch NAV, holdings, benchmark, peer, fee, manager,
  news, sentiment, market, macro, or calendar data by itself.
- `fund_analysis` may output reports, artifacts, evidence, warnings, and
  suggested plans.
- Formal `Decision` and `ExecutionLedger` outputs belong only to
  `decision_support`.

## Cookbooks

- [Generic subprocess host](./generic-subprocess-host.md)
- [OpenCode](./opencode.md)
- [Codex](./codex.md)
- [Claude Code](./claude-code.md)
- [Hermes](./hermes.md)
- [OpenClaw](./openclaw.md)

## Core References

- [docs/install/manual-host.md](../install/manual-host.md)
- [docs/install/runtime-bridge-cli.md](../install/runtime-bridge-cli.md)
- [examples/scenarios/README.md](../../examples/scenarios/README.md)
- [docs/install/opencode.md](../install/opencode.md)
- [docs/install/codex.md](../install/codex.md)
- [docs/contracts/fund-analysis-input-contract.v1.md](../contracts/fund-analysis-input-contract.v1.md)
- [docs/contracts/fund-analysis-artifacts.v1.md](../contracts/fund-analysis-artifacts.v1.md)
- [docs/contracts/report-output-contract.v1.md](../contracts/report-output-contract.v1.md)
- [docs/contracts/decision-support-contract.v1.md](../contracts/decision-support-contract.v1.md)
- [skillpack/decision-contracts.yaml](../../skillpack/decision-contracts.yaml)
- [examples/decision_support/README.md](../../examples/decision_support/README.md)
- [scripts/update_decision_support_golden.py](../../scripts/update_decision_support_golden.py)
