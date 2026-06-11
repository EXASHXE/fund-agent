# Minimal Open Agent Workflow

This document describes the recommended host workflow when integrating
fund-agent skills into an external agent.

## Workflow steps

1. **Agent discovers fund-analysis SKILL.md.** The agent reads the
   `fund-analysis` skill from `.opencode/skills/fund-analysis/SKILL.md`
   (or equivalent discovery path).

2. **Host collects user portfolio data.** The host gathers portfolio
   positions, NAV history, fund profiles, and other input fields
   required by `fund_analysis`. The host may fetch these from internal
   APIs, databases, or MCP providers.

3. **Host calls fund_analysis runtime bridge.** The host invokes:
   ```
   python scripts/run_skill.py --skill fund_analysis --input <json> --pretty
   ```
   Or calls `FundAnalysisSkill().run(skill_input)` directly in-process.

4. **Agent reads analysis_plan and evidence_gap_diagnostics.** These
   artifacts tell the agent what data was available and what was
   missing. If critical data is missing, the agent may ask the host to
   fetch it.

5. **Host optionally fetches missing data.** If the host has MCP
   providers for `web_search`, `financial_news`, or `social_sentiment`,
   it can fetch additional data and re-run `fund_analysis` with richer
   inputs.

6. **If user asks for formal action and decision_support_ready is true,
   host calls decision_support.** The host compiles the evidence graph
   from `fund_analysis` output and passes it to `decision_support`:
   ```
   python scripts/run_skill.py --skill decision_support --input <json> --pretty
   ```

7. **Host renders final response.** The host presents the analysis
   report, decision, or HOLD/WAIT recommendation to the user.

## Critical boundaries

- **fund_analysis must never emit formal Decision or ExecutionLedger.**
  Only `decision_support` produces those artifacts.
- **suggested_rebalance_plan is not execution.** It is a diagnostic
  artifact. The host must not treat it as a trade order.
- **broker execution is outside fund-agent.** fund-agent does not
  contain broker APIs, order placement, or trade execution.
- **MCP/live provider integration is host-owned.** fund-agent core
  runtime does not fetch NAV, news, or sentiment data.
