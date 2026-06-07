# OpenCode Integration Cookbook

OpenCode has two separate integration modes. Keep them separate.

## Mode A: Plugin Metadata And Doc Reader

The npm package / OpenCode plugin exposes metadata and lets OpenCode discover
and read skill docs. It is a metadata + doc-reader surface.

The OpenCode plugin must not call Python. It must not fetch data. It must not
become a runtime bridge. Use [OpenCode install](../install/opencode.md) and
`.opencode/INSTALL.md` for installation details.

The plugin can expose:

- available skills
- `skills/<slug>/SKILL.md` content
- runtime hints from the manifest

The plugin cannot provide deterministic Python runtime execution by itself.
npm/plugin install alone does not provide Python runtime execution.

## Mode B: Source Checkout Plus Runtime Bridge

For actual deterministic runtime execution, use a Python source checkout and
run `scripts/run_skill.py` as a host-owned subprocess. The OpenCode agent may
read docs and tell the user or host how to run the runtime bridge, but the
plugin itself must not invoke Python.

## Canonical Flow

1. Discover plugin skills.
2. Read [`skills/fund-analysis/SKILL.md`](../../skills/fund-analysis/SKILL.md).
3. Ask the host or user for portfolio, NAV, holdings, ledger, benchmark, peer,
   fee, manager, and scenario data.
4. If a Python checkout is available, inspect input:
   `python scripts/run_skill.py --skill fund_analysis --explain-input --pretty`
5. Validate before running:
   `python scripts/run_skill.py --skill fund_analysis --input examples/runtime_bridge_fund_analysis_input.json --validate-input --pretty`
6. Run `fund_analysis` through the runtime bridge.
7. Use `--emit-report markdown` if a deterministic Markdown report is desired.
8. Use `decision_support` only for formal `Decision` / `ExecutionLedger`
   outputs.

## Warnings

- Do not merge archived `docs/archive/fund-analyst` material into installable
  skills.
- Do not restore `skills/fund-analyst`.
- Do not expose underscore runtime IDs as agent-facing skill slugs.
- Do not claim npm install alone gives Python runtime execution.
- Host owns data fetching, provider SDKs, credentials, MCP providers,
  orchestration, retries, and final UX.
- `fund-agent` must not fetch NAV, holdings, benchmark, peer, news, or
  sentiment data by itself.
- Formal decisions require `decision_support`.
