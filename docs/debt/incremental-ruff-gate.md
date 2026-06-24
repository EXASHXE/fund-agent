# Incremental Ruff Gate — v0.10.4

## Status

**Active** — CI enforces ruff on a curated set of clean paths only.

## Background

As of v0.10.4, running `ruff check src/ tests/` produces ~626 pre-existing
violations across legacy code paths. These violations predate v0.10.4 and are
not introduced by the current release.

A full-repo ruff cleanup was evaluated but rejected for v0.10.4 because:

1. It would touch ~130 files with manual fixes, creating high regression risk.
2. Many violations are in test files with structural patterns (e.g., `sys.path`
   manipulation before imports) that require careful review.
3. The release timeline does not allow for a full lint cleanup alongside
   feature work.

## Current Gate Scope

The CI ruff step checks **only** the following paths, which are clean under
v0.10.4 standards:

```
src/host_data/
src/skills_runtime/workflow/final_report.py
src/tools/adapters/
src/tools/evidence/
src/tools/portfolio/report_sections/render.py
tests/host_adapters/
tests/release/test_v010_release_consistency.py
tests/schemas/test_provider_data_snapshot_schema.py
tests/scripts/
tests/workflow/test_portfolio_input_bridge.py
tests/tools/portfolio/
```

These paths cover all v0.10.4 additions and modifications.

## Expansion Protocol

To expand the gate scope:

1. Run `ruff check <path>` on the candidate path.
2. Fix all violations (auto-fix with `ruff --fix`, then manual fixes).
3. Verify `PYTHONPATH=. pytest -q` still passes.
4. Add the path to the CI ruff step in `.github/workflows/ci.yml`.
5. Update this document.

## Tech Debt Tracking

A GitHub issue tracks the remaining violations outside the gate scope.
The goal is to incrementally expand the gate until `ruff check src/ tests/`
passes fully.

## Violation Breakdown (Baseline)

| Category | Count | Auto-fixable |
|----------|-------|-------------|
| F401 (unused imports) | ~120 | Yes |
| I001 (import sorting) | ~200 | Yes |
| E402 (module import position) | ~80 | Partial |
| SIM* (simplify) | ~90 | Partial |
| UP035 (typing upgrades) | ~30 | Yes |
| Other | ~106 | Mixed |
| **Total** | **~626** | **~496** |
