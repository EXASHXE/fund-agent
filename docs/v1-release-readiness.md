# v1 Release Readiness

## Checklist

- [ ] `pytest -q` passes
- [ ] Architecture boundary tests pass
- [ ] Plugin/install surface tests pass
- [ ] `fund_analysis` does not emit Decision / ExecutionLedger
- [ ] `decision_support` is the only formal decision runtime
- [ ] Single-decision and trade_plan paths both use gatekeeper
- [ ] OpenCode plugin does not launch Python runtime
- [ ] Core runtime does not network, hold API keys, or bind provider SDKs
- [ ] README quickstart is current
- [ ] Host integration examples run locally
- [ ] Realistic user_flow tests pass
- [ ] zh-CN report can be generated
- [ ] v1 artifact contract docs exist
- [ ] No live-data or broker-execution claims in docs

## Known non-goals for v1

- No broker execution
- No autonomous planner
- No live provider bundled into core runtime
- No complete market prediction engine
- No LLM evidence grading

## Deferred after v1

- Richer MCP harness with live mode
- Provider adapters as external host examples
- Schema v2 for evidence_state / decision_block_state separation
- Broader report i18n beyond zh-CN and en
- Optional packaging improvements (pip install from PyPI)
- Performance benchmarking and optimization
- Additional professional diagnostics beyond v1 set

## Recommended validation commands

```bash
pytest tests/skills_runtime -q
pytest tests/integration -q
pytest tests/contracts -q
pytest tests/docs -q
pytest -q

# Project gate scripts
bash scripts/check_plugin_gate.sh

# Architecture boundary gate
PYTHONPATH=. pytest tests/architecture -q

# Install surface gate
PYTHONPATH=. pytest tests/install -q
```

## Release tag conditions

- All checklist items pass
- VERSION matches skillpack manifest version
- CHANGELOG.md has unreleased v1 section
- No provider SDK in core runtime
- No OpenCode Python launcher
- legacy/ contains only README.md
