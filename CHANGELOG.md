# Changelog

## 0.4.6-install-packaging-smoke

### Added

- `tests/install/test_npm_pack_contents.py` — 6 assertions that
  `npm pack --dry-run --json` produces a tarball containing the
  five canonical `skills/<slug>/SKILL.md` files and the three
  install docs, and does **not** contain `legacy/`,
  `docs/archive/fund-analyst/`, `tests/`, `scripts/` (Mode B
  helper), `.opencode/INSTALL.md`, `__pycache__/`, `*.pyc`, or
  `__init__.py` (stale Python leftovers in `skills/`). Skipped if
  `npm` is not on the test host.
- `tests/install/test_opencode_native_install_tree.py` — 6
  assertions that simulate a fresh project-local install. The
  test creates `<project>/.opencode/skills/`, runs the sync
  helper, and asserts: the install tree contains exactly the five
  canonical skills, each `SKILL.md` has a YAML frontmatter with
  `name: <slug>` and a non-empty `description`, `references/` is
  copied where the source has it, no underscore runtime dirs are
  written, no archived `fund-analyst` is written, no
  `__pycache__/` / `*.pyc` / `__init__.py` files are written, the
  marker file lists exactly the five canonical skills, `--clean`
  removes only the generated skills (user-authored files are
  preserved), and the install is idempotent.
- `tests/install/test_opencode_plugin_runtime_smoke.py` — 11
  assertions that exercise the OpenCode plugin's helper functions
  through a dynamic-import test harness: `node --check` succeeds,
  the plugin is dynamically importable, `listSkills()` returns
  `primary_skill == "fund-analysis"`, exactly four
  `supporting_skills`, and a `skills` array of length 5,
  `readSkillDoc` accepts `fund-analysis` and rejects
  `fund_analysis`, `decision_support`, `fund-analyst`, and
  `../README.md` (path-traversal), `runtimeHint` accepts both
  `fund-analysis` and `fund_analysis`, and the startup log does
  not classify `fund-analysis` as a supporting skill.
- `tests/docs/test_install_mode_consistency.py` — cross-doc
  consistency assertions for the install docs. Both
  `.opencode/INSTALL.md` and `docs/install/opencode.md` must
  mention Mode A / Mode B / Mode C, must say Mode C is a future
  runtime bridge, must say the plugin does not shell out to
  Python, must say the Mode B sync helper is a plain file copy,
  must mention `fund-analysis` as primary and the four supporting
  slugs explicitly, and must not contain `skills//SKILL.md`
  placeholders or claim the npm package is published.
- `description:` field in the YAML frontmatter of all five
  canonical `skills/<slug>/SKILL.md` files. Each description is a
  single-quoted, non-empty scalar that captures the skill's
  role, MCP requirements (if any), and produced artifacts. This
  satisfies the OpenCode Agent Skills frontmatter contract that
  requires a `description` for native skill discovery.

### Changed

- `package.json` `files` field is now an explicit whitelist with
  negation patterns: includes `opencode.plugin.js`, `skillpack/`,
  `skills/`, and `docs/install/`; excludes `__pycache__/`,
  `*.pyc`, `*.pyo`, and `__init__.py` from the `skills/`
  subtree. The resulting `npm pack` tarball is a clean
  Mode-A-only install surface (plugin + skill docs + install
  docs) with no Python build artifacts, no tests, no archive
  material, and no Mode B helper. Verified by
  `tests/install/test_npm_pack_contents.py`.
- `.opencode/INSTALL.md` and `docs/install/opencode.md` updated to
  document three install modes consistently: **Mode A** (the
  plugin, Mode A only, npm-shipped), **Mode B** (native Agent
  Skills sync via `scripts/install_opencode_skills.py`,
  git-clone-only), and **Mode C** (future runtime bridge, design
  only). `.opencode/INSTALL.md` adds an explicit
  "Install modes (Mode A / Mode B / Mode C)" section and a
  "Package contents — npm vs git" section that states the npm
  package is Mode A only and the Mode B helper is
  git-clone-only.
- `docs/install/codex.md` and `docs/install/manual-host.md` and
  `docs/install/opencode.md` version references updated from
  `v0.4.4` / `v0.4.5` to `v0.4.6`.
- `docs/design/runtime-bridge.md` version references updated
  from `v0.4.5` to `v0.4.6` (the design is still not
  implemented).
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  `package.json`, and `opencode.plugin.js` `PLUGIN_VERSION` all
  advanced to `0.4.6`.
- `tests/install/test_opencode_plugin_skeleton.py`
  `PLUGIN_VERSION` assertion bumped to `0.4.6`.
- `tests/install/test_install_docs_no_overclaim.py`
  runtime-bridge design doc assertion now accepts `v0.4.4`,
  `v0.4.5`, or `v0.4.6` in the doc text (forward-compatible; the
  contract — "runtime bridge is not implemented in the current
  release" — is unchanged).
- `docs/release-checklist.md` adds a "v0.4.6 Install Packaging
  Smoke" section.

### Honesty

- The v0.4.6 milestone is **purely about install packaging and
  the install-side smoke test surface**. No new domain features,
  no new schemas, no new providers, no new tools, no new
  Python runtime bridge.
- The npm package is **declared but not yet published**. The
  install still works end-to-end via the project-local symlink
  path. The npm convenience install is a future milestone.
- The npm package is **Mode A only**. A user who installs the
  npm package and also wants Mode B (native `Agent Skills`
  directory copy) must run `scripts/install_opencode_skills.py`
  from a git clone of the repo, not from the npm package. This
  split is intentional and is documented in
  `.opencode/INSTALL.md` and `docs/install/opencode.md`.
- No provider SDKs, no LLM clients, no autonomous loop, no
  planner loop, no runtime bridge, no database, no server, no
  autonomous agent runtime.
- All v0.4.5 install-hardening items (Mode A vs Mode B vs Mode C
  docs, plugin startup log primary / supporting distinction,
  sync helper safety) are still in place and still pass.

## 0.4.5-native-skill-install-hardening

### Added

- `.gitattributes` enforcing LF line endings for `*.sh`, `*.yml`,
  `*.yaml`, `*.toml`, `*.json`, `*.js`, `*.py`, `*.md`, with `text=auto`
  as the default. This is a regression guard for the v0.4.4 zip
  extraction issue where `scripts/check_plugin_gate.sh` shipped with
  CRLF line endings even though the git index was LF.
- `scripts/install_opencode_skills.py` — Mode B of the OpenCode
  install. Copies the five canonical hyphenated skill directories
  from `skills/` into `.opencode/skills/<slug>/SKILL.md` so OpenCode's
  native `Agent Skills` discovery sees the same five skills as the
  plugin. Supports `--dry-run`, `--target <path>`, and `--clean`
  (which only removes the skills this script wrote, identified by
  the marker file `.opencode/skills/.fund-agent-generated.json`).
  Does not edit `opencode.json`, does not start a subprocess, does
  not install the Python runtime, and does not call any network.
- `tests/ci/test_line_endings.py` — file-level CRLF guard for
  `scripts/check_plugin_gate.sh`, `.github/workflows/*.yml`,
  `opencode.plugin.js`, canonical `skills/<slug>/SKILL.md`, and
  canonical `skills/<slug>/references/*.md`. The test does not
  depend on git and catches CRLF even if the renormalize step is
  bypassed.
- `tests/install/test_opencode_native_skill_sync.py` — 12 tests
  covering dry-run output, apply output, copied `SKILL.md`
  frontmatter, references preservation, refusal to copy
  `fund-analyst` and underscore runtime IDs, marker file behavior,
  and `--clean` safety.
- Four new tests in `tests/install/test_opencode_skill_surface.py`
  guarding the startup log primary / supporting distinction: the
  log message text must not list `fund-analysis` under
  `supporting skills:`, the structured `extra` payload must split
  primary from supporting, and `listSkills().supporting_skills`
  must equal exactly the four canonical supporting slugs.

### Changed

- `opencode.plugin.js` startup log message now correctly splits
  the primary skill from the four supporting skills. v0.4.4 had a
  bug where the message joined all five slugs into the
  `supporting skills:` clause; v0.4.5 filters by `role ===
  "supporting"` and asserts the distinction via tests. The plugin
  exports a new `buildStartupLogMessage()` helper for testability.
- `.opencode/INSTALL.md` and `docs/install/opencode.md` updated to
  use the corrected startup log example and to document three
  install modes: Mode A (plugin metadata + doc-reader, current
  target), Mode B (native `Agent Skills` install via the sync
  helper, optional), and Mode C (future runtime bridge, design
  only). The docs now distinguish OpenCode **plugins** (the JS
  module loaded via `opencode.json`) from OpenCode **Agent Skills**
  (`SKILL.md` directories under `.opencode/skills/<slug>/`).
- `docs/install/opencode.md` and `.opencode/INSTALL.md` version
  pinning examples updated to `v0.4.5`.
- `docs/design/runtime-bridge.md` updated to reference v0.4.5
  (the design is still not implemented).
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  `package.json`, and `opencode.plugin.js` `PLUGIN_VERSION` all
  advanced to `0.4.5`.
- `tests/install/test_opencode_plugin_skeleton.py` PLUGIN_VERSION
  assertion bumped to `0.4.5`.
- `tests/install/test_install_docs_no_overclaim.py` runtime-bridge
  design doc assertion accepts `v0.4.4` or `v0.4.5` (forward-
  compatible; the contract — "runtime bridge is not implemented in
  the current release" — is unchanged).
- `scripts/install_opencode_skills.py` is executable
  (`chmod +x`).

### Honesty

- Mode A is **plugin metadata + doc-reader only**; it does not
  invoke the Python runtime and does not call any network.
- Mode B is a **plain file copy**; it does not start a subprocess,
  does not edit `opencode.json`, does not install the Python
  runtime, and does not call any network. The marker file is the
  only state it writes outside the copied skill files.
- Mode C is **design only**, not implemented in v0.4.5.
- No provider SDKs, no LLM clients, no autonomous loop, no
  planner loop, no new fund metrics, no new schemas, no new
  portfolio tools, no new providers, no runtime bridge, no
  database, no server, no autonomous agent runtime.
- No runtime / domain feature changes. The v0.4.5 milestone is
  purely about install-surface hardening and OpenCode install
  honesty (Mode A vs Mode B).

## 0.4.4-superpowers-compatible-skill-surface

### Changed

- Skill surface is now a **Superpowers-compatible composable
  Markdown collection**: one hyphenated `skills/<slug>/SKILL.md`
  directory per skill, with the directory name matching the
  frontmatter `name` field.
- `fund-analysis` is the **primary / default skill**. For ordinary
  user requests like `分析下我的基金给出报告`, load `fund-analysis`
  first. It alone is sufficient for a report-only flow.
- `decision-support`, `news-research`, `sentiment-analysis`, and
  `thesis-generation` are **supporting skills**. They are loaded
  only when the subtask description matches the supporting skill
  and only after the primary skill (or equivalent evidence) is in
  scope. `decision-support` remains the only skill that may produce
  a formal `Decision` / `ExecutionLedger`.
- `skills/fund-analysis/SKILL.md` now has a "Default entrypoint"
  section and a "When to load supporting skills" table.
- Each supporting `SKILL.md` has a "supporting skill" preamble that
  states the policy: `decision-support` is only for actionable trade
  decisions after an `EvidenceGraph` exists, `news-research` and
  `sentiment-analysis` are host/MCP-backed evidence skills with no
  direct provider SDK calls, and `thesis-generation` produces a
  `thesis_draft` artifact only and must not produce formal decisions.
- Python runtime IDs remain underscore names in the manifest and
  Python (`fund_analysis`, `decision_support`, `news_research`,
  `sentiment_analysis`, `thesis_generation`). External hosts should
  pass the underscore runtime ID to `fund_agent_runtime_hint` and to
  `SkillInput(skill_name=...)`.

### Removed

- Underscore skill directories deleted: `skills/fund_analysis/`,
  `skills/news_research/`, `skills/sentiment_analysis/`,
  `skills/thesis_generation/`. They are not part of the
  v0.4.4+ surface and are not exposed by the OpenCode plugin.
- Legacy persona directory `skills/fund-analyst/` moved to
  `docs/archive/fund-analyst/`. It is archived legacy reference
  material, not a runtime skill, not installed, and not discovered.
- `tests/skills/test_skill_classes.py` removed (it tested the
  legacy underscore skill classes that have been removed).

### Plugin

- The OpenCode plugin now exposes the **five hyphenated Markdown
  doc slugs** as agent-facing skill names: `fund-analysis` (primary)
  + `decision-support`, `news-research`, `sentiment-analysis`,
  `thesis-generation` (supporting).
- `fund_agent_skills` returns `primary_skill`, `supporting_skills`,
  and per-skill `role` metadata.
- `fund_agent_skill_doc` accepts **hyphenated slugs only** and
  rejects underscore skill slugs and the archived `fund-analyst`
  persona.
- `fund_agent_runtime_hint` accepts either a hyphenated agent-facing
  slug **or** an underscore Python runtime ID; both resolve to the
  same Python runtime class path.
- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  and `package.json` all advanced to `0.4.4`.

### Honesty

- No provider SDKs, no LLM clients, no autonomous loop, no
  subprocess spawn, no planner loop. The host-agnostic architecture
  constraints are preserved.
- No runtime / domain feature changes. The new milestone is purely
  about the agent-facing skill surface and the install surface.

## 0.4.3-installable-skillpack

### Added

- OpenCode project-local plugin install: `package.json` at the repo
  root + `opencode.plugin.js` plugin entrypoint + `.opencode/INSTALL.md`
  + `docs/install/opencode.md`. The plugin is a metadata + doc reader
  only; it registers `fund_agent_skills`, `fund_agent_skill_doc`, and
  `fund_agent_runtime_hint` tools and does not run an autonomous loop.
- Manual / Python host install documented at
  `docs/install/manual-host.md`. The canonical install path for any
  Python host.
- Codex install (manual / light) at `docs/install/codex.md`. No
  OMO-style installer in v0.4.3.
- Future runtime bridge design at `docs/design/runtime-bridge.md`.
  Document-only, not implemented.
- New `tests/install/` package with 55 installability tests covering
  `package.json` metadata, the OpenCode plugin skeleton (syntax +
  no-network + no-provider-SDK invariants), install docs honesty, and
  manifest-runtime-id-to-doc-slug mapping consistency.

### Changed

- `VERSION`, `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`,
  and `package.json` all advanced to `0.4.3`.
- `scripts/check_plugin_gate.sh` now runs `tests/install` after the
  install smoke suite.
- `pyproject.toml` `tool.pytest.ini_options.testpaths` includes
  `tests/install`.
- `tests/docs/test_skill_doc_quality.py` canonical-docs list now
  includes the new install docs and runtime-bridge design doc.

### Honesty

- The OpenCode install is **metadata + docs only**. The Python runtime
  is host-driven; the plugin does not invoke skills or fetch data.
- The runtime bridge is **not** in v0.4.3. The design is documented for
  a future milestone.
- No provider SDKs, no LLM clients, no autonomous loop. The
  host-agnostic architecture constraints are preserved.

## 0.4.2-skill-md-first

### Added
- Markdown-first skill architecture documentation under `skills/README.md`
- Canonical hyphenated SKILL.md workflow guides for all manifest skills
- Fund analysis policy references for inputs, reports, risk, missing data, DCA,
  short-term trade budgets, market scenarios, and examples
- Decision support references for evidence anchors, WAIT/HOLD, execution amount
  caps, deterministic mode, contracts, and examples
- Host workflow guide for `分析下我的基金给出报告`
- Documentation policy tests for skill docs and directory naming

### Changed
- Project docs now state that the manifest is the discovery entrypoint and
  `skills/<slug>/SKILL.md` is the agent-facing policy layer
- Underscore `skills/` directories are documented as compatibility-only
- `fund-analyst` is explicitly marked legacy/reference-only

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
