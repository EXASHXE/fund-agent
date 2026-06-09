# START HERE — fund-agent

## What is fund-agent?

`fund-agent` is a **host-agnostic, Markdown-first personal fund analysis skill
pack**. It provides deterministic Python runtime skills that an external agent
host (OpenCode, Claude Code, Codex, Hermes, OpenClaw, custom subprocess host)
can call through a local runtime bridge CLI or direct Python import.

## What fund-agent is NOT

- **Not an autonomous agent** or planner — the external host owns orchestration.
- **Not a provider integration** — does not fetch NAV, holdings, news, sentiment,
  market, macro, or calendar data.
- **Not a broker or order execution system** — does not place trades or connect
  to brokerage APIs.
- **Not a formal investment advisor** — all output is analysis, diagnostics,
  and suggested plans. Formal `Decision` / `ExecutionLedger` requires
  `decision_support`.

## Fastest local run

```bash
# 1. Requires Python 3.11+
git clone ... && cd fund-agent
pip install -e .

# 2. Discover skills
python scripts/run_skill.py --list-skills --pretty

# 3. Explain what fund_analysis expects
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty

# 4. Validate a fake scenario input
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json \
  --validate-input --pretty

# 5. Run fund_analysis
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json --pretty

# 6. Emit a Markdown report
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json \
  --emit-report markdown --output report.md

# 7. Run decision_support with a fake fixture
python scripts/run_skill.py --skill decision_support \
  --input examples/decision_support/single_active_buy_with_evidence.json --pretty
```

## Key docs

- [README.md](../README.md) — full project overview
- [Runtime bridge CLI](install/runtime-bridge-cli.md) — JSON-in/JSON-out host execution
- [Host integration cookbooks](host-integrations/README.md) — host-specific recipes
- [Fund analysis input contract](contracts/fund-analysis-input-contract.v1.md) — what `fund_analysis` expects
- [Fund analysis artifact contract](contracts/fund-analysis-artifacts.v1.md) — what `fund_analysis` emits
- [Decision support contract](contracts/decision-support-contract.v1.md) — formal `Decision` / `ExecutionLedger` semantics
- [Thesis generation contract](contracts/thesis-generation-contract.v1.md) — `ThesisDraft` artifact semantics
- [Skill output contract](contracts/skill-output-contract.v1.md) — `SkillOutput` shape, error objects, status values
- [Report output contract](contracts/report-output-contract.v1.md) — deterministic report section shape
- [Tools inventory](tools-inventory.md) — public vs internal tool classification
- [Fake scenario fixtures](../examples/scenarios/README.md) — sample data exercising fund_analysis diagnostics
- [Decision support fixtures](../examples/decision_support/README.md) — sample data exercising decision_support
- [Thesis generation fixtures](../examples/thesis_generation/README.md) — sample data exercising thesis_generation
- [Golden regression snapshots](../tests/golden/README.md) — behavior-freeze contract tests

## Boundary rules

- **Host owns** data fetching, provider SDKs, network access, credentials,
  retries, memory, planning, orchestration, and final UX.
- **OpenCode plugin** is metadata + doc-reader only; it does not invoke Python.
- **Runtime bridge CLI** is the source-checkout/manual-host execution path.
- **fund_analysis** produces reports, artifacts, warnings, evidence, and
  suggested analysis plans only. It does **not** produce formal
  `Decision` or `ExecutionLedger` artifacts.
- **decision_support** is the **only** runtime skill that may produce formal
  `Decision` / `ExecutionLedger` artifacts. Even then, it does **not** execute
  trades or connect to brokerage systems.
- **No broker/order execution** — this skill pack is analysis-only.
