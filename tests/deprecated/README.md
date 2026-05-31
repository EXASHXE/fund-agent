# Deprecated Tests — Historical Reference Only

These tests are NOT part of the default plugin test gate. They are preserved
for historical reference and may fail. They are not run by `pytest -q`.

## What's Here

- `research_os/` — old ResearchOS loop, planner, critic, skill registry tests
- `scoring/` — old multi-dimensional scoring engine tests
- `strategy/` — old WAIT/HOLD/ADD/REDUCE/STOP_LOSS state machine tests
- `news/` — old holdings-driven news pipeline and provider client tests
- `misc/` — miscellaneous old pipeline tests
- `reporting/` — old report rendering tests
- `archived_broken/` — tests that referenced deleted legacy code (ui, routes, services, agents, forecast)

## Running

```bash
PYTHONPATH=. pytest tests/deprecated -q
```

Failures are expected. These tests import from `legacy/` modules that may have
been removed or are scheduled for removal.

## Policy

- Do not add new tests here.
- Do not move deprecated tests back into the main gate.
- Deprecated tests are not required to pass.
- This directory is excluded from `pyproject.toml` testpaths.
