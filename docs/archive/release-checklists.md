# Historical Release Checklists

The checklists below represent historical milestones and are
preserved for reference. They are **NOT** the current release
checklist for `v0.4.8-dev`. Do NOT apply historical version checks
to the current release.

For the current checklist, see `docs/release-checklist.md` sections
1–9 and 13.

---

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

## 14. v0.4.5 Native Skill Install Hardening

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

## 15. v0.4.6 Install Packaging Smoke

- [ ] All v0.4.5 install-hardening items above still pass
- [ ] `VERSION` is `0.4.6` and matches `package.json`,
      `pyproject.toml`, `skillpack/fund-agent.skillpack.yaml`, and
      `opencode.plugin.js` `PLUGIN_VERSION`
- [ ] `package.json` `files` field is a curated whitelist that:
      - includes `opencode.plugin.js`, `skillpack/`, `skills/`,
        `docs/install/`;
      - excludes `__pycache__/`, `*.pyc`, `__init__.py` from the
        `skills/` subtree;
      - does not include `tests/`, `src/`, `scripts/`, `examples/`,
        `.opencode/INSTALL.md`, `docs/archive/`, or `legacy/`.
- [ ] `npm pack --dry-run --json` produces a tarball listing that
      contains the five canonical `skills/<slug>/SKILL.md` files and
      the three install docs, and does not contain `legacy/`,
      `docs/archive/fund-analyst/`, `tests/`, or build artifacts
- [ ] `tests/install/test_npm_pack_contents.py` passes (6 npm-pack
      assertions)
- [ ] `tests/install/test_opencode_native_install_tree.py` passes
      (6 native-install-tree assertions: full simulation, marker
      content, `--clean` safety, dry-run, idempotency, source
      mirror)
- [ ] `tests/install/test_opencode_plugin_runtime_smoke.py` passes
      (11 plugin-runtime smoke assertions: `node --check`,
      dynamic import, `listSkills()` primary + 4 supporting,
      `readSkillDoc` accepts `fund-analysis`, rejects
      `fund_analysis` / `decision_support` / `fund-analyst` /
      `../README.md`; `runtimeHint` accepts both
      `fund-analysis` and `fund_analysis`; startup log does not
      classify `fund-analysis` as supporting)
- [ ] `.opencode/INSTALL.md` and `docs/install/opencode.md` both
      mention Mode A / Mode B / Mode C, both say Mode C is a future
      runtime bridge, both say the plugin does not shell out to
      Python, both say the Mode B sync helper is a plain file copy,
      and both list `fund-analysis` as primary and the four
      supporting slugs explicitly
- [ ] `.opencode/INSTALL.md` includes a "Package contents — npm vs
      git" section that states the npm package is Mode A only and
      the Mode B helper is git-clone-only
- [ ] `tests/docs/test_install_mode_consistency.py` passes
      (cross-doc consistency assertions: Mode A/B/C coverage,
      primary + four supporting, no double-slash skill-path
      placeholders, no npm-published claim)
- [ ] No new `__pycache__/`, `*.pyc`, `__init__.py`, or
      underscore-skill dirs in the published npm tarball
- [ ] No new provider SDKs, no new network calls, no new
      autonomous loop, no runtime bridge, no planner loop

## 16. v0.4.7-dev Runtime Bridge CLI

- [ ] `python scripts/run_skill.py --list-skills --pretty` returns
      a JSON envelope listing all five manifest runtime IDs
      (`fund_analysis`, `news_research`, `sentiment_analysis`,
      `thesis_generation`, `decision_support`)
- [ ] `python scripts/run_skill.py --skill fund_analysis --input
      examples/runtime_bridge_fund_analysis_input.json --pretty`
      exits 0 and emits `ok=true` JSON
- [ ] `python scripts/run_skill.py --skill decision_support --input
      examples/runtime_bridge_decision_support_input.json --pretty`
      exits 0 and emits `ok=true` JSON
- [ ] `PYTHONPATH=. pytest tests/runtime_bridge -q` passes (CLI,
      manifest resolution, no-network, decision support, examples,
      MCP capability resolution, output contract)
- [ ] `scripts/run_skill.py` delegates to
      `src.skillpack.run_skill:main`
- [ ] `src/skillpack/run_skill.py` resolves runtime classes from
      the manifest via `src.skillpack.loader.resolve_runtime`; it
      does not hardcode runtime classes
- [ ] Bridge-level error codes are exactly
      `INVALID_INPUT | UNKNOWN_SKILL | RUNTIME_LOAD_FAILED |
      SKILL_RUN_FAILED | JSON_SERIALIZATION_FAILED |
      MISSING_MCP_CAPABILITY`
- [ ] Bridge stdout is JSON only; diagnostics go to stderr
- [ ] Bridge does not import provider SDKs, does not call
      `requests` / `httpx` / `urllib.request` / `subprocess`, does
      not shell out to OpenCode, and does not reference
      `opencode.plugin.js` or `@opencode-ai/plugin`
- [ ] `opencode.plugin.js` still does not call Python, does not
      spawn subprocesses, does not fetch data, and does not run
      providers (independent surface)
- [ ] `docs/design/runtime-bridge.md` is updated to mark the thin
      CLI bridge as implemented in v0.4.7-dev and the deeper
      runtime bridge (subprocess handlers, OpenCode plugin tool
      wrapper) as still future
- [ ] `docs/install/runtime-bridge-cli.md` exists and documents
      the JSON-in / JSON-out contract, the MCP boundary, and the
      relationship to the plugin, the design doc, and the manifest
- [ ] `examples/minimal_runtime_bridge_fund_analysis.py` runs
      end-to-end (asserted by
      `tests/runtime_bridge/test_runtime_bridge_examples.py` and
      `scripts/check_examples.py`)
- [ ] No new fund metrics, no new portfolio tools, no new
      schemas, no new runtime contracts, no new MCP providers, no
      autonomous loop, no planner loop, no server, no daemon

### v0.4.7-dev hardening additions

- [ ] `python scripts/run_skill.py --skill news_research --input
      <news_research with no mcp_responses>` exits 2 and emits
      `ok=false` with `error.code = MISSING_MCP_CAPABILITY`,
      `metadata.required_mcp_capabilities` includes `web_search`
      and `financial_news`, and
      `metadata.missing_mcp_capabilities` is the same set
- [ ] `python scripts/run_skill.py --skill sentiment_analysis
      --input <sentiment_analysis with no mcp_responses>` exits 2
      and emits `ok=false` with
      `metadata.missing_mcp_capabilities` containing
      `social_sentiment`
- [ ] `python scripts/run_skill.py --skill news_research --input
      <news_research with canned web_search + financial_news
      mcp_responses>` exits 0, runs the skill, and reports
      `missing_mcp_capabilities = []`
- [ ] A convenience `{"payload": {...}}` envelope with no
      `required_mcp_capabilities` still surfaces the manifest
      `requires_mcp` (asserted by
      `tests/runtime_bridge/test_runtime_bridge_mcp_capabilities.py`)
- [ ] `_emit_envelope` returns exit code 2 when the
      `JSON_SERIALIZATION_FAILED` fallback fires, even if the
      original envelope had `ok=true` (asserted by
      `tests/runtime_bridge/test_runtime_bridge_mcp_capabilities.py`)
- [ ] Bridge output envelope has stable top-level keys
      (`ok, skill_name, step_id, status, artifacts,
      evidence_items, warnings, errors, used_mcp_capabilities,
      metadata`) and metadata keys (`manifest_path, runtime_path,
      required_mcp_capabilities, missing_mcp_capabilities`) for
      successful skill runs (asserted by
      `tests/runtime_bridge/test_runtime_bridge_output_contract.py`)
- [ ] Bridge-failure envelopes have top-level `ok=false` and
      `error.{code, message, details}`; stdout contains no
      Python traceback (asserted by
      `tests/runtime_bridge/test_runtime_bridge_output_contract.py`)
- [ ] `package.json` does NOT include runtime bridge files
      (`scripts/run_skill.py`, `src/skillpack/run_skill.py`,
      `examples/runtime_bridge_*`, `tests/runtime_bridge/`).
      The bridge is git-clone-only; the npm package remains
      Mode A only (asserted by
      `tests/install/test_npm_pack_contents.py`)
- [ ] `docs/install/runtime-bridge-cli.md` and the install
      matrix in `.opencode/INSTALL.md` /
      `docs/install/opencode.md` agree that the runtime bridge
      is a separate, host-invoked, source-checkout surface
      (asserted by
      `tests/docs/test_runtime_bridge_doc_consistency.py`)
