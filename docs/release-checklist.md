# Release Checklist

Run this checklist before tagging a release.

## 1. Plugin Identity

- [ ] README title is "Host-Agnostic AI Financial Research Skill Pack"
- [ ] `skillpack/fund-agent.skillpack.yaml` exists
- [ ] Skill layer is Markdown-first: `skills/<slug>/SKILL.md` files are primary
      agent-facing instructions
- [ ] External hosts discover runtime skills from the manifest, not folder names
- [ ] `fund-analyst` is legacy/reference-only
- [ ] `package_role` == `agent_plugin`
- [ ] `orchestration_owner` == `external_agent`
- [ ] `mcp_provider_owner` == `external_host`
- [ ] `required_entrypoint` == `skillpack/fund-agent.skillpack.yaml`
- [ ] Only `decision_support` produces `Decision` and `ExecutionLedger`
- [ ] `thesis_generation` forbids `formal_decision_generation`

## 2. Host Integration

- [ ] `docs/host-integration.md` exists and describes host-owned orchestration
- [ ] `docs/agent-host-quickstart.md` exists
- [ ] External host smoke test passes:
  ```bash
  PYTHONPATH=. pytest tests/integration/test_external_host_smoke.py -q
  ```

## 3. Contracts

- [ ] `SkillInput` / `SkillOutput` schemas are stable
- [ ] `EvidenceItem` / `EvidenceGraph` schemas are stable
- [ ] `Decision` / `ExecutionLedger` schemas are stable
- [ ] Contract tests pass:
  ```bash
  PYTHONPATH=. pytest tests/contracts -q
  ```

## 4. MCP Boundary

- [ ] No provider SDK (tavily, finnhub, exa, firecrawl, reddit, akshare,
      openai, anthropic, langchain) in skills_runtime
- [ ] No network calls in skills_runtime except via mcp_adapter
- [ ] MCP adapter tests pass:
  ```bash
  PYTHONPATH=. pytest tests/tools/test_mcp_adapter_contract.py -q
  ```

## 5. Tools

- [ ] quant / ledger / evidence tools do not import network or LLM
- [ ] Tool catalog resolves:
  ```bash
  PYTHONPATH=. pytest tests/skillpack/test_tool_catalog.py -q
  ```

## 6. Tests

- [ ] compileall passes:
  ```bash
  PYTHONPATH=. python -m compileall src tests
  ```
- [ ] Default pytest gate passes:
  ```bash
  PYTHONPATH=. pytest -q
  ```
- [ ] Architecture boundaries pass:
  ```bash
  PYTHONPATH=. pytest tests/architecture -q
  ```
- [ ] `tests/deprecated` is NOT in default gate

## 7. Legacy

- [ ] `v0.1.0-skillpack-alpha` preserves the pre-prune legacy archive
- [ ] Legacy implementation removed from current mainline
- [ ] `tests/deprecated` removed from current mainline
- [ ] `docs/archive/legacy-system.md` documents historical modules
- [ ] No `src` import `legacy`
- [ ] No `skillpack` reference to `legacy`

## 8. CI

- [ ] `.github/workflows/plugin-ci.yml` exists
- [ ] `.github/workflows/ci.yml` delegates to `bash scripts/check_plugin_gate.sh`
- [ ] `.github/workflows/plugin-ci.yml` delegates to `bash scripts/check_plugin_gate.sh`
- [ ] Canonical gate includes compileall, parser checks, architecture,
      contracts, skillpack, examples, skills, tools, integration, install smoke,
      and default pytest
- [ ] `scripts/check_plugin_gate.sh` exists and is executable
- [ ] `scripts/check_plugin_gate.sh` auto-installs only `pytest` and
      `pyyaml` (via `python -m pip install --quiet pytest pyyaml`) if
      they are missing on the host. This keeps the gate runnable on a
      fresh `pip install`-less environment (such as a minimal CI
      runner). The script does **not** install any other dependency,
      does **not** add new auto-install targets, and does **not**
      mutate the project requirements.

## 9. Host Integration UX

- [ ] `AGENTS.md` exists
- [ ] `skillpack/examples/README.md` exists
- [ ] `examples/minimal_host_news_to_decision.py` runs:
  ```bash
  python examples/minimal_host_news_to_decision.py
  ```
- [ ] `docs/skill-io-examples.md` exists
- [ ] `docs/workflows/personal-fund-report.md` exists
- [ ] `docs/plugin-api.md` documents `SkillError` standard codes
- [ ] Minimal host demo does not import ResearchOS or legacy
- [ ] `fund_analysis` artifacts include deterministic `report_sections`,
      `report_outline`, and `report_quality_gate`
- [ ] `report_quality_gate` documents whether a professional report is
      publishable; formal actions still require `DecisionSupportSkill`
- [ ] Missing benchmark, peer, manager, factor, fee, and redemption data
      produces `PARTIAL`/`MISSING` sections rather than fabricated analysis

## Quick Verification

```bash
bash scripts/check_plugin_gate.sh
python scripts/check_examples.py
python examples/minimal_host_news_to_decision.py
python examples/minimal_host_portfolio_review.py
python examples/minimal_host_trade_plan_to_decisions.py
PYTHONPATH=. pytest tests/install -q
```

## 10. v0.4.8-dev Release Hygiene and Readability

- [ ] All version-bearing files agree on the current version:
  `VERSION`, `package.json`, `pyproject.toml`,
  `skillpack/fund-agent.skillpack.yaml`, `opencode.plugin.js`
  `PLUGIN_VERSION`, and `CHANGELOG.md` current section.
  ```bash
  cat VERSION
  python -c "import json; print(json.load(open('package.json'))['version'])"
  python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
  python -c "import yaml; print(yaml.safe_load(open('skillpack/fund-agent.skillpack.yaml'))['version'])"
  grep 'const PLUGIN_VERSION' opencode.plugin.js
  ```
- [ ] No broken double-slash skill-path placeholder strings
  anywhere in the repo. Run the quality guard:
  ```bash
  PYTHONPATH=. pytest tests/docs/test_skill_doc_quality.py \
    tests/docs/test_skill_surface_docs.py \
    tests/docs/test_install_mode_consistency.py -q
  ```
- [ ] Readability regression tests pass (key source line counts,
  config parseability, plugin placeholder check, version consistency).
  ```bash
  PYTHONPATH=. pytest tests/docs/test_readability_regression.py -q
  ```
- [ ] Dependency boundary is clean:
  ```bash
  PYTHONPATH=. pytest tests/ci/test_dependency_boundary.py -q
  ```
- [ ] Capability discovery CLI works:
  ```bash
  python scripts/run_skill.py --list-capabilities --pretty
  python scripts/run_skill.py --describe-capability fund_nav_history --pretty
  ```
- [ ] Ledger and research query plan runtime bridge examples work:
  ```bash
  python scripts/run_skill.py --skill fund_analysis \
    --input examples/runtime_bridge_ledger_snapshot_input.json --pretty
  python scripts/run_skill.py --skill fund_analysis \
    --input examples/runtime_bridge_research_query_plan_input.json --pretty
  ```
- [ ] Report quality example works:
  ```bash
  python scripts/run_skill.py --skill fund_analysis \
    --input examples/runtime_bridge_personal_report_quality_input.json --pretty
  ```
- [ ] Report quality tests pass:
  ```bash
  PYTHONPATH=. pytest tests/tools/test_report_quality.py \
    tests/skills/test_fund_analysis_report_quality.py \
    tests/runtime_bridge/test_runtime_bridge_report_quality_examples.py -q
  ```
- [ ] Package Mode A boundary is intact:
  ```bash
  PYTHONPATH=. pytest tests/install/test_npm_pack_contents.py -q
  PYTHONPATH=. pytest tests/docs/test_install_mode_consistency.py -q
  ```
- [ ] No provider SDKs in `skills_runtime` or plugin.
- [ ] No network calls in plugin or runtime bridge.
- [ ] `opencode.plugin.js` comments are version-neutral (no pinned
  `v0.4.X` claims in Scope / Skill surface headers).
- [ ] Default `requirements.txt` contains only `pyyaml` (no
  provider SDKs). Provider SDKs are in `requirements-legacy.txt`
  only.

## Historical Checklists

Sections for previous milestones (v0.4.0.dev0 through v0.4.7-dev) have
been moved to [`docs/archive/release-checklists.md`](./archive/release-checklists.md).
They are **historical only** — do NOT apply their version-specific
checks to the current release.
