# v0.4.9 Release Notes (Draft)

## Summary

fund-agent v0.4.9-dev is a host-agnostic, source-checkout runtime skill pack.
It provides Markdown-first external agent skill documentation and a
deterministic runtime bridge for structured financial research tasks. Formal
decision boundaries have been hardened: only `decision_support` may emit
`Decision` and `ExecutionLedger` artifacts.

## Added / Hardened

- Runtime bridge introspection (`--explain-input`, `--validate-input`,
  `--output-schema`), validation, and output schema commands.
- `fund_analysis` artifact and input contracts with YAML declarations.
- Markdown report rendering via `--emit-report markdown`.
- Realistic fake scenario fixtures (redemption fee, QDII overlap, AI
  semiconductor overweight, DCA drawdown, ledger-derived snapshot).
- Golden regression snapshots for fund_analysis, decision_support, and
  thesis_generation.
- Professional diagnostics artifact in fund_analysis output.
- `decision_support` structured justification fields on formal decisions.
- `thesis_generation` artifact-only runtime (no formal decision emission).
- MCP adapter base for `news_research` and `sentiment_analysis` host-injected
  data.
- `SkillOutput` error normalization with canonical `code` / `message` /
  `details` / `recoverable` shape.
- Source-checkout host smoke tests covering skill discovery, slug resolution,
  fixture validation, and deterministic output.
- Host readiness matrix and command catalog documentation.
- OpenCode plugin metadata and doc-reader boundary (no Python invocation).
- Final boundary audit: no provider SDKs, no network calls, no broker/order
  execution, no deprecated src-level surfaces.

## Boundaries

- External hosts own data fetching, provider SDKs, network access, credentials,
  MCP providers, orchestration, memory, retries, final UX, and any
  brokerage/order execution outside fund-agent.
- No broker/order execution in fund-agent.
- No live data fetching inside fund-agent.
- No OpenCode Python runtime execution.
- Fixtures are fake/sample data only.

## Known Optional Checks

- Local build dry-run may skip if the `build` module is unavailable.
- Editable install smoke may skip if `venv`, `pip`, or offline editable install
  support is unavailable.

## Migration Notes

- Use `scripts/run_skill.py` for runtime bridge execution, not the deprecated
  `src/cli.py` (which has been removed).
- Use `skills/<slug>/SKILL.md` and `skillpack/fund-agent.skillpack.yaml` as
  the primary agent-facing discovery and contract surfaces.
- Do not use the archived `skills/fund-analyst` directory; it is legacy only.
- Runtime IDs use underscores (e.g. `fund_analysis`); documentation slugs use
  hyphens (e.g. `fund-analysis`). Both resolve through the runtime bridge.

## Not Included

- No provider SDKs.
- No live market data fetching.
- No order execution.
- No autonomous daemon, server, scheduler, or HTTP API.
- No package publication (no PyPI, no npm).
