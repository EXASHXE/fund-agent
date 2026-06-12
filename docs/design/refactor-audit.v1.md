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

### Public Facade Package (`src/fund_agent/` + top-level `fund_agent/`)

**Preferred public import paths:** `fund_agent.*` (see `src/fund_agent/__init__.py`
and top-level `fund_agent/` shim). The `src.*` paths below are internal
implementations; external consumers should use the `fund_agent.*` facade.

| Module | Wraps |
|--------|-------|
| `fund_agent.__init__` | Version |
| `fund_agent.workflow` | `src.skills_runtime.workflow`, `src.tools.workflow.final_report` |
| `fund_agent.regression` | `src.skills_runtime.workflow.personal_regression` |
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

- `fund-agent = "fund_agent.cli:main"` (primary entry point via public facade)
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

---

## v1.8.2 — Cleanup After Audit / Pre-0.9 Finalization

### Audit Date

Deterministic run via `python scripts/audit/run_all_audits.py --json`

### Audit Scripts Run

| Script | Key Findings |
|--------|-------------|
| `audit_project_structure.py` | 6 src areas, 13 large files, 25 missing READMEs |
| `audit_dead_code.py` | 0 HIGH, 0 MEDIUM, 0 LOW confidence deletion candidates |
| `audit_public_api.py` | 3 console scripts, 112 deep test imports, 18 deep example imports, 6 facade recommendations |
| `audit_docs_links.py` | 0 broken links, 17 overclaims (autonomous-agent-loop wording, LangGraph, ResearchOS), 0 missing boundaries |

### Key Findings

1. **No dead code** — zero HIGH/MEDIUM/LOW deletion candidates
2. **17 overclaims** — "autonomous agent loop" (9), "LangGraph" (2), "ResearchOS" as active concept (6)
3. **Deep imports** — 112 in tests, 18 in examples; expected for internal test code, not a facade problem
4. **Console script** — already updated to `fund_agent.cli:main` in v1.8.1

### Files Kept Intentionally

- `legacy/README.md` — historical archive pointer
- `docs/archive/` — historical reference docs
- `tools/` — project root utility scripts
- All compatibility wrappers (`tests/helpers/personal_regression_runner.py`, etc.)

### Files Cleaned (Docs Only)

| File | Change | Audit Reason |
|------|--------|-------------|
| `README.md` | Full rewrite: removed ResearchOS/autonomous agent loop/LangGraph; added fund_agent.* as preferred API; clarified provider boundary | overclaim: ResearchOS, autonomous agent loop, LangGraph |
| `docs/host-integration.md` | "ResearchOS / autonomous agent loop" → "autonomous agent"; ResearchOS marked historical | overclaim: autonomous agent loop, ResearchOS as active |
| `docs/install/manual-host.md` | "autonomous agent loop" → "agent loop" | overclaim: autonomous agent loop |
| `docs/install/opencode.md` | "autonomous agent loop" → "autonomous agent" (2 occurrences) | overclaim: autonomous agent loop |
| `docs/design/runtime-bridge.md` | "autonomous agent loop" → "autonomous agent" | overclaim: autonomous agent loop |
| `docs/architecture/skill-runtime-contract.md` | "ResearchOS converts" → "The host converts" | overclaim: ResearchOS as active |
| `docs/architecture/runtime-contract.md` | "ResearchOS converts" → "The host converts" with historical note | overclaim: ResearchOS as active |
| `docs/agent-host-quickstart.md` | ResearchOS marked as historical, not "optional reference" | overclaim: ResearchOS as optional |
| `docs/plugin-api.md` | Added "(historical; removed from current runtime)" to research_os reference | overclaim: research_os as active path |
| `docs/host-compatibility.md` | ResearchOS marked as "historical reference only" | overclaim: ResearchOS |
| `docs/maintenance.md` | "langgraph" → "langgraph (historical)" | overclaim: LangGraph as current |
| `docs/archive/fund-analyst/references/evidence-contract.md` | LangGraph agent_state → "(legacy; not produced by current skill runtime)" | overclaim: LangGraph |
| `docs/archive/release-checklists.md` | "autonomous agent loop" → "autonomous agent" (2 occurrences) | overclaim: autonomous agent loop |
| `CHANGELOG.md` | "autonomous agent loop" wording standardized (3 occurrences) | overclaim: autonomous agent loop |
| `docs/design/refactor-audit.v1.md` | Fixed stale entry point; added fund_agent.* as preferred API note; updated regression facade mapping | stale: src.fund_agent.cli:main, tests.helpers import |

### Files Not Cleaned and Why

- `docs/archive/` files beyond the specific fixes above — they are historical records and already marked as archive
- `docs/maintenance.md` ResearchOS references — already clearly marked as historical/legacy
- `docs/release-checklist.md` ResearchOS guard clause — this is a safety check, not an overclaim
- `docs/v1-release-readiness.md`, `docs/v1-analysis-pipeline.md` — early v1 docs, not actively misleading
- `docs/v1.2-host-integration-checklist.md` — referenced from README, may still be useful

### No File Deletions

No file deletions were performed in v1.8.2 because audit did not identify
high-confidence unused files safe to remove. The dead code audit returned
0 candidates at all confidence levels.

### Remaining Cleanup Candidates

- `docs/release-checklist-v0.4.9.md`, `docs/release-notes-v0.4.9-draft.md`,
  `docs/release-readiness-v0.4.9-dev.md`: stale v0.4.9 release docs
- `docs/v1-analysis-pipeline.md`, `docs/v1-release-readiness.md`: early v1 docs
- `docs/v1.2-host-integration-checklist.md`: may be superseded
- `tools/` directory at project root: purpose unclear
- 25 directories missing READMEs (low priority)

### Risks Avoided

- No behavior changes — all doc edits are wording only
- No test changes to weaken assertions
- No compatibility wrappers removed
- No public API surface changed
- No version bump or tag
