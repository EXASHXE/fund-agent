# v0.4.9 Release Checklist

## Status

- v0.4.9-dev is a release-ready candidate.
- No tag has been created yet.
- No PyPI package has been published.
- No npm package has been published.
- Source checkout plus `scripts/run_skill.py` is the canonical deterministic runtime path.

## Final Gate Commands

Run each in order from the repo root:

```bash
python -m compileall src tests scripts
python -m pytest tests/schemas -q
python -m pytest tests/architecture -q
python -m pytest tests/skills_runtime -q
python -m pytest tests/tools -q
python -m pytest tests/integration -q
python -m pytest tests/runtime_bridge -q
python -m pytest tests/contracts -q
python -m pytest tests/docs -q
python -m pytest tests/golden -q
python -m pytest tests/skillpack -q
python -m pytest tests/install -q
python -m pytest -q
node --check opencode.plugin.js
bash scripts/check_plugin_gate.sh
```

All must pass with zero failures (pre-existing skips are acceptable).

## Optional Checks

- Local build dry-run may skip if the `build` module is unavailable.
- Editable install smoke may skip if `venv`, `pip`, or offline editable install
  support is unavailable.
- Source-checkout smoke remains the canonical deterministic runtime gate.

## Manual Smoke Commands

```bash
# List skills
python scripts/run_skill.py --list-skills --pretty

# fund_analysis Markdown report
python scripts/run_skill.py \
  --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json \
  --emit-report markdown

# decision_support fixture
python scripts/run_skill.py \
  --skill decision_support \
  --input examples/decision_support/single_active_buy_with_evidence.json \
  --pretty

# thesis_generation fixture
python scripts/run_skill.py \
  --skill thesis_generation \
  --input examples/thesis_generation/evidence_graph_balanced_thesis.json \
  --pretty
```

Expected:

- `--list-skills` shows fund_analysis, decision_support, thesis_generation,
  news_research, sentiment_analysis.
- fund_analysis Markdown starts with `# Personal fund report` and includes
  `## Professional diagnostics`.
- decision_support emits formal `decision` and `execution_ledger` artifacts.
- thesis_generation emits `thesis_draft` and no formal `decision` or
  `execution_ledger` artifacts.

## Boundary Confirmations

- [ ] OpenCode plugin remains metadata + doc-reader only.
- [ ] No provider SDKs imported in runtime code.
- [ ] No network calls in runtime code.
- [ ] No broker/order execution in runtime code.
- [ ] `fund_analysis` does not emit formal `Decision` or `ExecutionLedger`.
- [ ] `thesis_generation` does not emit formal `Decision` or `ExecutionLedger`.
- [ ] `decision_support` is the only runtime skill that may emit formal
      `Decision` or `ExecutionLedger`.
- [ ] Host-visible errors remain canonical `code` / `message` / `details` /
      `recoverable` objects.
- [ ] Deprecated src-level surfaces remain absent (core, infra, workflows,
  config, data, db, kg, vectorstore directories and cli.py under src/).

## Tag Decision Options

1. **Keep v0.4.9-dev as a development checkpoint.** No tag, no version bump.
   The current state is a validated candidate on the default branch.
2. **Bump metadata from 0.4.9-dev to 0.4.9, rerun all gates, then tag v0.4.9.**
   This makes the version string explicit and creates a permanent reference.
3. **Optionally create a non-release checkpoint tag** (e.g.
   `v0.4.9-dev-checkpoint`) only if a maintainer wants a lightweight
   reference without implying a release.

## Manual Post-Tag Commands (NOT YET EXECUTED)

These commands are for reference only. Do not run them until a maintainer
decides to create a release tag.

```bash
# Create annotated tag
git tag -a v0.4.9 -m "v0.4.9"

# Push tag to remote
git push origin v0.4.9
```
