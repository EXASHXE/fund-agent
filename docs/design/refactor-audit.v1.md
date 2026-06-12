# Refactor Audit v1 — v1.8 Comprehensive Refactor

## What Was Audited

### Audit Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/audit/audit_project_structure.py` | Repository structure, large files, missing READMEs |
| `scripts/audit/audit_dead_code.py` | Candidate unused files, stale references |
| `scripts/audit/audit_public_api.py` | Public entrypoints, deep imports, facade recommendations |
| `scripts/audit/audit_docs_links.py` | Broken links, overclaims, missing boundary statements |
| `scripts/audit/run_all_audits.py` | Run all audits, write `artifacts/audit/` |

### Audit Findings Summary

- **Project structure**: 6 src package areas, multiple large files (>500 lines)
- **Dead code**: Candidates found at LOW/MEDIUM confidence only; no HIGH confidence deletions
- **Public API**: Multiple deep imports in tests/examples that should use facade
- **Docs links**: Some broken local links; no critical overclaims found

## What Was Kept

- All existing `src/` package structure unchanged
- All existing `skills/` directory unchanged
- All existing `skillpack/` manifest unchanged
- All existing `examples/` directory unchanged
- All existing `tests/` directory unchanged
- All existing console scripts (`fund-agent-run-skill`, `fund-agent-doctor`)
- All existing scripts (`scripts/run_skill.py`, `scripts/run_personal_regressions.py`, etc.)
- Old deep import paths remain functional (backward compatible)

## What Was Added

### Public Facade Package (`src/fund_agent/`)

| Module | Wraps |
|--------|-------|
| `fund_agent.__init__` | Version |
| `fund_agent.workflow` | `src.skills_runtime.workflow`, `src.tools.workflow.final_report` |
| `fund_agent.regression` | `tests.helpers.personal_regression_runner` |
| `fund_agent.quality` | `src.tools.workflow.advisory_quality_gate`, `report_safety` |
| `fund_agent.providers` | `src.host_data` (contracts only, no adapters) |
| `fund_agent.reporting` | `src.tools.workflow.final_report`, `report_status` |
| `fund_agent.runtime` | `src.skills_runtime.fund_analysis`, `decision_support` |
| `fund_agent.version` | `VERSION` file |
| `fund_agent.cli` | Unified CLI with subcommands |

### Unified CLI

```
fund-agent doctor [--pretty] [--json]
fund-agent run-skill --skill ID --input PATH [--pretty]
fund-agent regressions [--pretty] [--scenario NAME] [--show-trace]
fund-agent provider-smoke [--provider NAME] [--all] [--resolve-env] [--json]
fund-agent audit [--pretty] [--json]
```

### New Console Script

- `fund-agent = "src.fund_agent.cli:main"` (new primary entry point)
- `fund-agent-run-skill` and `fund-agent-doctor` preserved for compatibility

## What Was Deleted

No files were deleted in this refactor phase. The audit found no HIGH confidence
deletion candidates. All cleanup candidates are at LOW or MEDIUM confidence and
require manual review before any removal.

## What Was Intentionally Not Changed

- No version bump (remains 1.1.0, pending v0.9.0 tag)
- No file moves or renames
- No behavior changes
- No new product features
- No new data providers
- No new install modes
- No broker/order execution fields
- No network calls in core runtime
- No provider SDK imports in core

## Known Remaining Cleanup Candidates

- `legacy/` directory: contains only `README.md`, should remain as historical archive
- `docs/archive/`: historical docs, should remain for reference
- `docs/release-checklist-v0.4.9.md`, `docs/release-notes-v0.4.9-draft.md`,
  `docs/release-readiness-v0.4.9-dev.md`: stale v0.4.9 release docs, review for removal
- `docs/v1-analysis-pipeline.md`, `docs/v1-release-readiness.md`: early v1 docs, may be stale
- `docs/v1.2-host-integration-checklist.md`: may be superseded by current host-integration docs
- `tools/` directory at project root: contents and purpose need review

## Why No Behavior Changes Were Intended

This is a behavior-preserving refactor. The public facade modules are thin
wrappers that delegate to existing implementations without modification.
The CLI delegates to existing script entry points. All existing tests continue
to pass without modification.
