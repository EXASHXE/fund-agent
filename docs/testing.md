# Testing Guide

## Test Layers

| Layer | Script | When | Target time | Scope |
|-------|--------|------|-------------|-------|
| Changed files | `bash scripts/test_changed.sh` | After every edit | <30s | Tests relevant to git diff |
| Identity/NAV | `bash scripts/test_identity_nav.sh` | After identity/NAV/reconstruction changes | <5s | `test_e2e_identity_nav.py` |
| Fast gate | `bash scripts/test_fast.sh` | Before push, every few edits | 30–90s | Fast unit/smoke/critical paths |
| Plugin smoke | `bash scripts/test_plugin_smoke.sh` | After wrapper/skill changes | <30s | Skillpack, contracts, architecture |
| Privacy | `bash bin/fund-agent-privacy-check` | Before push | <5s | Privacy/artifact safety |
| Private data doctor | `bash bin/fund-agent-private-data-doctor --pretty` | After setting up private_data/ | <5s | Override file existence and schema |
| CI gate | `bash scripts/test_ci.sh` | Reproduce GitHub CI locally | 4–5 min | Lint scope + `pytest --cov=src` |
| Release gate | `bash scripts/test_release_gate.sh` | Before release-freeze only | 5–6 min | CI gate + plugin gate + privacy + examples |
| Release lint | `bash scripts/lint_release_scope.sh` | Standalone lint check | <5s | Canonical v0.10.5 release scope only |
| Profile | `bash scripts/profile_tests.sh` | When optimizing | varies | Durations report |

## Daily Workflow

### After modifying identity/NAV/reconstruction
```bash
bash scripts/test_identity_nav.sh
```

### After modifying wrapper/skill/plugin
```bash
bash scripts/test_plugin_smoke.sh
```

### After modifying privacy rules
```bash
bash bin/fund-agent-privacy-check
PYTHONPATH=. pytest -q -m privacy
```

### Quick feedback after any edit
```bash
bash scripts/test_changed.sh
```

### Before push
```bash
bash scripts/test_fast.sh
bash scripts/test_plugin_smoke.sh
bash bin/fund-agent-privacy-check
```

### Before release-freeze
```bash
bash scripts/test_release_gate.sh
# Plus manual A/B/C/C2/D2 scenario review with desensitized output
```

## CI Workflow Mapping

| GitHub Workflow | Script Entry | Environment |
|-----------------|-------------|-------------|
| `ci.yml` | `bash scripts/test_ci.sh` | Full dev deps (`pip install -e ".[dev]"`) |
| `plugin-ci.yml` | `bash scripts/check_plugin_gate_fast.sh` | Minimal deps (`requirements.txt` + pytest + pyyaml) |

- **ci.yml** runs lint scope + `pytest --cov=src` via `test_ci.sh`. It does NOT duplicate ruff commands or run redundant architecture/contract steps (those are already covered by the full pytest).
- **plugin-ci.yml** uses `check_plugin_gate_fast.sh` (architecture + contracts + skillpack + skills + tools), NOT the full `check_plugin_gate.sh`. The full canonical gate is reserved for release-level validation.
- **check_plugin_gate.sh** is the full/canonical/release-level plugin gate. It is NOT suitable as the default entry for minimal plugin-ci because it runs integration, install, and full pytest which require dev extras.

## Important Notes

- **test_fast.sh is NOT a release gate.** It covers ~2300 fast tests but skips install, integration, runtime_bridge, agent_wrappers, release, and privacy directories.
- **Full pytest must still pass** before release-freeze. Run `test_release_gate.sh` for full coverage.
- **real_e2e tests never run by default** and never read `private_data/`.
- **test_changed.sh** is a convenience script; it does not replace test_fast.sh.

## Release Lint Scope (v0.10.5)

The release gate uses `scripts/lint_release_scope.sh` which checks only the canonical runtime path:

```
scripts/fund_agent_e2e.py, import_alipay_transactions.py, resolve_fund_identities.py,
reconstruct_portfolio_from_ledger.py, fund_identity_utils.py, build_fund_data_snapshot.py,
build_factor_snapshot.py, privacy_audit.py,
src/skills_runtime/, src/schemas/, src/tools/portfolio/, src/tools/workflow/,
src/tools/adapters/, src/tools/evidence/, src/fund_agent/,
tests/end_to_end/test_e2e_identity_nav.py, tests/tools/portfolio/,
tests/scripts/, tests/schemas/, tests/contracts/, tests/skills_runtime/, tests/architecture/
```

**Why not `ruff check .`?** The repo has ~590 historical lint issues in `examples/`, `src/graph/`, and other non-critical paths. These are not regressions from v0.10.5 changes. Full-project lint cleanup is tracked for v0.10.6. New/modified files in the canonical scope MUST be ruff-clean.

## What test_fast.sh Covers

Explicit fast paths (no marker-based negative selection alone):

```
tests/end_to_end/test_e2e_identity_nav.py
tests/end_to_end/test_e2e_personal_health_report.py
tests/schemas/ tests/tools/portfolio/ tests/contracts/ tests/ci/
tests/graph/ tests/golden/ tests/public_api/ tests/reporting/
tests/skills/ tests/host_data/ tests/host_adapters/ tests/evidence/
tests/evaluation/ tests/examples/ tests/skills_runtime/ tests/docs/
tests/architecture/test_architecture_boundaries.py
tests/scripts/ tests/workflow/
```

Plus marker exclusion: `-m "not slow and not subprocess and not release ..."`

## What test_fast.sh Skips

| Directory | Reason | Marker |
|-----------|--------|--------|
| `tests/install/` | Subprocess-heavy (93s) | slow, subprocess, install |
| `tests/integration/` | Multi-module (40s) | integration |
| `tests/runtime_bridge/` | Subprocess-heavy (43s) | integration, subprocess |
| `tests/agent_wrappers/` | Plugin smoke (24s) | plugin |
| `tests/release/` | Release gate only | release |
| `tests/privacy/` | Release gate only | privacy, release |
| `tests/personal_regression/` | Regression suite | regression, slow |
| `tests/host_integration/` | Subprocess integration | integration, subprocess |

## Pytest Markers

| Marker | Purpose | Default |
|--------|---------|---------|
| `unit` | Pure fast unit tests | always run |
| `integration` | Multi-module integration | excluded from fast gate |
| `e2e` | Synthetic end-to-end | always run |
| `slow` | Slow tests (>2s) | excluded from fast gate |
| `subprocess` | Spawns subprocesses | excluded from fast gate |
| `release` | Release-freeze gate only | excluded from fast gate |
| `real_e2e` | Requires private local data | never in CI, opt-in only |
| `privacy` | Privacy/artifact safety | run via privacy check |
| `plugin` | Plugin/wrapper/skill | run via plugin smoke |
| `install` | Packaging/install smoke | excluded from fast gate |
| `regression` | Personal regression | excluded from fast gate |

### Running with markers
```bash
# Exclude slow and release tests
PYTHONPATH=. pytest -q -m "not slow and not release"

# Only privacy tests
PYTHONPATH=. pytest -q -m privacy

# Real E2E (requires private data, opt-in)
PYTHONPATH=. pytest -q -m real_e2e
```

## Real E2E Testing

Real E2E tests use private Alipay CSV data and must never run in CI.
They require `private_data/` with real data files.

```bash
# Run real E2E pipeline (requires private_data/)
PYTHONPATH=. python scripts/fund_agent_e2e.py --as-of 2026-06-20 --skip-akshare
```

## Personal Run Testing

The personal-run CLI orchestrates doctor → E2E → health report → agent context.

```bash
# Run personal-run tests
PYTHONPATH=. pytest -q tests/scripts/test_personal_run.py

# Test agent context module
PYTHONPATH=. pytest -q tests/tools/portfolio/test_agent_context.py
```

Key behaviors tested:
- `--private-data-dir` applies to both doctor and E2E
- `--health-report-only --summary-path` reads existing summary without running pipeline
- `--agent-context-only --run-dir` reads existing summary without running pipeline
- Default mode (no --summary-path/--run-dir) runs full pipeline
- No private paths in agent_context or manifest output

## Parallel Testing (Optional)

If `pytest-xdist` is installed (dev extra):
```bash
pip install -e ".[dev]"
PYTHONPATH=. pytest -q -n auto
```

This is optional and not required for CI or minimal environments.
