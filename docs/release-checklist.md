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

## 10. Domain Core Development (v0.4.0.dev0)

- [ ] `VERSION` exists and reads `0.4.0.dev0`
- [ ] `CHANGELOG.md` exists
- [ ] `docs/CONTRACT_FREEZE.md` exists
- [ ] Manifest version equals `VERSION`
- [ ] Pyproject version equals `VERSION`
- [ ] `fund_analysis` supports host-provided portfolio, NAV, holdings, risk profile, and constraints
- [ ] `examples/minimal_host_portfolio_review.py` runs without network, ResearchOS, or legacy imports
- [ ] Manifest `schema_version` == `skillpack.v1`
- [ ] Manifest `package_role` == `agent_plugin`
- [ ] `bash scripts/check_plugin_gate.sh` passes
- [ ] `.github/workflows/plugin-ci.yml` is valid YAML
- [ ] No legacy runtime code on mainline
- [ ] `tests/deprecated` does not exist
- [ ] External host smoke passes
- [ ] No provider SDKs in `skills_runtime`

## 11. RC-1 Host Compatibility

- [ ] `skillpack/schema/skillpack.v1.schema.json` exists
- [ ] Manifest validates against skillpack.v1 schema
- [ ] `docs/host-compatibility.md` exists
- [ ] Install smoke test passes:
      ```bash
      PYTHONPATH=. pytest tests/integration/test_install_smoke.py -q
      ```
- [ ] Public import paths resolve:
      ```bash
      PYTHONPATH=. pytest tests/contracts/test_public_import_paths.py -q
      ```
- [ ] Examples checker passes:
      ```bash
      python scripts/check_examples.py
      ```
- [ ] Minimal host demo emits JSON subprocess

## 12. v0.4.3 Installable Skillpack

- [ ] `package.json` exists at repo root
- [ ] `package.json` version matches `VERSION`
- [ ] `package.json` name is `fund-agent`
- [ ] `package.json` repository points at `EXASHXE/fund-agent`
- [ ] `package.json` declares zero runtime dependencies
- [ ] `opencode.plugin.js` exists and passes `node --check`
- [ ] `.opencode/INSTALL.md` exists
- [ ] `docs/install/opencode.md` exists
- [ ] `docs/install/manual-host.md` exists
- [ ] `docs/install/codex.md` exists
- [ ] `docs/design/runtime-bridge.md` exists and is marked as
      design / future
- [ ] `tests/install` passes:
      ```bash
      PYTHONPATH=. pytest tests/install -q
      ```
- [ ] `tests/install` is included in `scripts/check_plugin_gate.sh`
- [ ] `tests/install` is in `pyproject.toml` testpaths
- [ ] No provider SDK in `opencode.plugin.js` (only optional
      `@opencode-ai/plugin` peer dep)
- [ ] No network IO in `opencode.plugin.js` (only fs reads for docs)
- [ ] No runtime bridge claims in v0.4.3 install docs

## Quick Verification

```bash
bash scripts/check_plugin_gate.sh
python scripts/check_examples.py
python examples/minimal_host_news_to_decision.py
python examples/minimal_host_portfolio_review.py
python examples/minimal_host_trade_plan_to_decisions.py
PYTHONPATH=. pytest tests/install -q
```

## 13. v0.4.5 Native Skill Install Hardening

- [ ] `.gitattributes` exists and enforces LF for `*.sh`, `*.yml`,
      `*.yaml`, `*.toml`, `*.json`, `*.js`, `*.py`, `*.md`
- [ ] `git ls-files --eol scripts/check_plugin_gate.sh .github/workflows/ci.yml .github/workflows/plugin-ci.yml opencode.plugin.js package.json skills/fund-analysis/SKILL.md`
      shows `i/lf    w/lf` for all listed text files
- [ ] `scripts/check_plugin_gate.sh` is executable
      (`test -x scripts/check_plugin_gate.sh`)
- [ ] `bash scripts/check_plugin_gate.sh` succeeds on Linux
- [ ] `node --check opencode.plugin.js` succeeds
- [ ] `python -m json.tool package.json >/dev/null` succeeds
- [ ] `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` succeeds
- [ ] `python -c "import yaml; yaml.safe_load(open('skillpack/fund-agent.skillpack.yaml'))"` succeeds
- [ ] `PYTHONPATH=. python -m compileall src tests` succeeds
- [ ] `tests/ci/test_line_endings.py` passes (8 line-ending tests)
- [ ] OpenCode plugin startup log says
      `primary skill: fund-analysis; supporting skills: decision-support, news-research, sentiment-analysis, thesis-generation`
      (i.e. `fund-analysis` MUST NOT appear in the supporting-skills
      clause)
- [ ] `listSkills().primary_skill` is `fund-analysis` and
      `listSkills().supporting_skills` is exactly the four canonical
      supporting slugs
- [ ] `.opencode/INSTALL.md` and `docs/install/opencode.md` use the
      corrected log example and document Mode A / Mode B / Mode C
      install modes
- [ ] `scripts/install_opencode_skills.py` exists, is executable, and
      supports `--dry-run`, `--target`, and `--clean`
- [ ] `python scripts/install_opencode_skills.py --dry-run` lists the
      five canonical skills
- [ ] `tests/install/test_opencode_native_skill_sync.py` passes
      (12 sync-helper tests)
- [ ] No provider SDKs in `opencode.plugin.js` or
      `scripts/install_opencode_skills.py`
- [ ] No network calls in `opencode.plugin.js` or
      `scripts/install_opencode_skills.py`
- [ ] No runtime / domain feature changes
