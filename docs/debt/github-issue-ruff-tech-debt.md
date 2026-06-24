# Tech Debt: Clean Legacy Ruff Violations Outside v0.10.4 Incremental Gate

## Summary

The CI ruff gate currently checks only v0.10.4-clean paths. Running `ruff check src/ tests/` on the full repo produces ~626 pre-existing violations in legacy code paths that are not yet covered by the gate.

## Motivation

- Full-repo ruff compliance is required for long-term maintainability.
- The incremental gate was introduced in v0.10.4 to unblock the release without a risky large-scale lint cleanup.
- Each expansion of the gate scope improves code quality and catches issues earlier.

## Scope

### Auto-fixable (~496 violations)

- **F401** (unused imports): ~120 — most can be auto-fixed with `ruff --fix`
- **I001** (import sorting): ~200 — auto-fixable
- **UP035** (typing upgrades): ~30 — auto-fixable
- Other auto-fixable: ~146

### Manual fixes (~130 violations)

- **E402** (module import position): ~80 — many in test files with `sys.path` manipulation; need `# noqa: E402` or restructure
- **SIM*** (simplify): ~90 — some require careful review
- **E741** (ambiguous names): a few — rename variables
- **B011** (assert False): a few — replace with `raise AssertionError()`
- Other: mixed

## Approach

1. **Phase 1** — Auto-fix: Run `ruff --fix src/ tests/` to clear ~496 violations automatically.
2. **Phase 2** — Manual E402: Add `# noqa: E402` to test files with `sys.path` patterns, or restructure imports.
3. **Phase 3** — Manual SIM/E741/B011: Fix remaining violations one by one.
4. **Phase 4** — Expand gate: After each phase, expand the CI gate scope and verify tests pass.

## Acceptance Criteria

- [ ] `ruff check src/ tests/` returns 0 violations
- [ ] CI gate checks `ruff check src/ tests/` (full scope)
- [ ] All tests pass: `PYTHONPATH=. pytest -q`
- [ ] `docs/debt/incremental-ruff-gate.md` updated to reflect full scope

## References

- Incremental gate design: `docs/debt/incremental-ruff-gate.md`
- CI configuration: `.github/workflows/ci.yml`
- Baseline violation count: 626 (as of v0.10.4)
