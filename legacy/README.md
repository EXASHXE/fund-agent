# Legacy Archive — Historical Reference Only

## Overview

The legacy `analyze` pipeline is preserved as a historical archive for old CLI,
report, news, recommendation, strategy, and UI experiments. It is not part of
the host-agnostic plugin contract.

The old pipeline has been replaced by the host-agnostic skillpack,
`skills_runtime`, tools, EvidenceGraph compiler, and `DecisionSupportSkill`.

## Archive Boundary

- No new code should import `legacy`.
- No new tests should depend on `legacy`.
- Legacy may be deleted after an archive tag.
- Provider-specific clients here are not part of the plugin contract.

## Historical Components

- `legacy/cli.py`, `legacy/routes/`: old CLI analyze route.
- `legacy/news/`: old holdings-driven news pipeline and provider clients.
- `legacy/analysis/scoring/`: old multi-dimensional scoring engine.
- `legacy/strategy/`: old WAIT/HOLD/ADD/REDUCE/STOP_LOSS state machine.
- `legacy/output/`: old Markdown/JSON report rendering.
- `legacy/agents/`: old LangGraph-style multi-agent experiment.
- `legacy/services/`, `legacy/engine/`, `legacy/forecast/`: old workflow
  support modules.

## Current Replacement

New host integrations should load `skillpack/fund-agent.skillpack.yaml`, call
`src.skills_runtime` handlers directly, use `src.tools` for pure calculations
and evidence compilation, and call
`src.skills_runtime.decision_support.DecisionSupportSkill` only when a formal
`Decision` and `ExecutionLedger` are needed.

ResearchOS reference modules under `src/core` and `src/workflows` are optional
reference workflows only. They are not the plugin entrypoint.
