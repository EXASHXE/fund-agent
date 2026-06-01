# Changelog

## 0.4.1-personal-portfolio-advisor-core

### Added
- Extended portfolio analysis tools (PnL, cost_basis, DCA review, trade budget)
- Transaction/cost basis schemas and tools (weighted-average cost basis)
- Fund NAV extended metrics (period returns, momentum, risk-adjusted score)
- Multi-leg trade plan generation with deterministic ranking
- 5 realistic personal portfolio example JSON payloads
- 38 new tests across tools, skills, and integration
- docs/host-compatibility.md host compatibility matrix

### Changed
- FundAnalysisSkill extended for personal portfolio analysis with transactions/DCA/market_scenario
- DecisionSupportSkill extended for multi-trade decision making from trade_plan
- Portfolio analysis API stabilized with 14 public functions
- Fund metrics produce per-period returns and risk-adjusted scores

## 0.4.0.dev0

### Added

- Personal portfolio domain schemas in `src.schemas.fund`
- Pure fund NAV metric tools in `src.tools.fund.metrics`
- Pure portfolio analysis tools in `src.tools.portfolio.analysis`
- Structured portfolio review support in `FundAnalysisSkill`
- `examples/minimal_host_portfolio_review.py`
- Domain core tests for fund metrics, portfolio analysis, and portfolio review integration

### Changed

- `DecisionSupportSkill` derives active trade amounts from host-provided
  portfolio context, risk profile, constraints, and target trade amount when
  those are available.
- Skillpack version advanced to `0.4.0.dev0`.

## 0.3.0-skillpack-rc

### Added

- `AGENTS.md` — coding agent integration guide
- `examples/minimal_host_news_to_decision.py` — self-contained host integration demo
- `skillpack/examples/README.md` — host-facing examples documentation
- `docs/skill-io-examples.md` — JSON-like SkillInput/SkillOutput reference
- `docs/plugin-api.md` — full plugin API reference for external agents
- `docs/archive/legacy-system.md` — historical module documentation
- `docs/release-checklist.md` — release verification checklist
- `docs/CONTRACT_FREEZE.md` — frozen contracts for rc
- `VERSION` — canonical version file
- `CHANGELOG.md` — this file
- `scripts/check_plugin_gate.sh` — plugin health gate script
- `.github/workflows/plugin-ci.yml` — CI workflow
- `tests/integration/test_external_host_smoke.py` — external host integration smoke
- `tests/integration/test_minimal_host_demo.py` — minimal host demo test
- `tests/skillpack/test_version_consistency.py` — version consistency tests
- `tests/contracts/test_contract_freeze_docs.py` — contract freeze validation
- `tests/skillpack/test_project_metadata.py` — project metadata sanity tests

### Changed

- Repository is now a host-agnostic Skill Pack / Agent Plugin
- ResearchOS is not required; optional reference only
- External host owns orchestration, MCP provider injection, and retry policy
- `README.md` rewritten for Host-Agnostic Skill Pack narrative
- `legacy/README.md` reduced to pointer to `v0.1.0-skillpack-alpha`

### Removed

- Legacy code removed from mainline (analysis, news, output, strategy, workflows, etc.)
- `tests/deprecated` removed
- Low-value legacy dirs removed (ui, routes, services, agents, forecast)

### Fixed

- Architecture boundary tests enforce no legacy imports
- Skillpack manifest does not require ResearchOS
- DecisionSupportSkill is the only formal Decision producer

### Compatibility

- Old legacy implementation available at `v0.1.0-skillpack-alpha`
  ```bash
  git checkout v0.1.0-skillpack-alpha
  ```
- Skillpack schema is `skillpack.v1`

### Known Limitations

- No real MCP providers bundled
- No provider SDKs bundled (Tavily, Finnhub, Exa, Firecrawl, Reddit)
- fund-agent is not a production autonomous agent runtime
- MCP providers must be injected by the external host
