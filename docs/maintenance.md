# Maintenance Guide

## Plugin Core

Plugin core is the host-facing contract surface:

- `skillpack/` manifests, capabilities, tools, contracts, and examples.
- `skills/` Markdown-first host-readable `SKILL.md` instructions and
  references.
- `src/skills_runtime/` host-callable skill handlers.
- `src/schemas/` typed skill, evidence, graph, decision, and ledger contracts.
- `src/tools/` pure tools, evidence compilation, and MCP adapter boundary.
- `src/graph/` KnowledgeGraph helpers.

Core code must not import `legacy`, provider SDKs, network clients, or LLM SDKs.
External hosts own orchestration, credentials, network access, and retries.

## Legacy Archive

Legacy code was removed after `v0.1.0-skillpack-alpha`. To inspect the old
implementation, checkout the tag:

```bash
git checkout v0.1.0-skillpack-alpha
```

See `docs/archive/legacy-system.md` for the full list of removed modules.

`tests/deprecated` has been removed. New code must not import `legacy`. New
code should extend only:

- `skillpack/`
- `skills/`
- `src/skills_runtime/`
- `src/schemas/`
- `src/tools/`
- `src/graph/`
- `src/skillpack/`
- `docs/`
- `tests/` (plugin gate)

ResearchOS modules under `src/core` and `src/workflows` are deprecated reference
code available from historical tags and archive docs. They are not required for
host integration and should not be treated as current plugin runtime surface.

The current plugin core lives only under these directories:
- `skillpack/`
- `skills/`
- `src/skills_runtime/`
- `src/schemas/`
- `src/tools/`
- `src/graph/`
- `src/skillpack/`
- `docs/`
- `tests/`

Do not reintroduce `src/core`, `src/infra`, `src/workflows`, or shim import
packages (`src/config/`, `src/data/`, `src/db/`, `src/kg/`, `src/vectorstore/`)
as current plugin runtime surface. Historical ResearchOS code is archived in the
`v0.1.0-skillpack-alpha` tag.

## Main Test Gate

Default `pytest` targets plugin core only:

- `tests/architecture`
- `tests/contracts`
- `tests/skillpack`
- `tests/skills`
- `tests/tools`
- `tests/integration`

## Adding A Skill

1. Add or update the host-readable `skills/<hyphenated-slug>/SKILL.md`.
2. Add a host-callable runtime class under `src/skills_runtime/`.
3. Use `SkillInput` and `SkillOutput` only for runtime boundaries.
4. Return `EvidenceItem` objects or draft artifacts as appropriate.
5. Register the skill in `skillpack/fund-agent.skillpack.yaml`.
6. Add examples under `skillpack/examples/`.
7. Add main-gate tests under `tests/skills` or `tests/skillpack`.

Only `DecisionSupportSkill` may produce formal `Decision` and
`ExecutionLedger` artifacts.

Runtime skill IDs are underscore names from
`skillpack/fund-agent.skillpack.yaml`; Markdown doc slugs are hyphenated
directories. Do not infer runtime IDs from folder names. Underscore directories
under `skills/` are compatibility-only if retained, and `fund-analyst` is
legacy/reference-only.

## Adding MCP Capability Declarations

Declare new MCP capability names in `skillpack/capabilities.yaml` and reference
them from the relevant skill in `skillpack/fund-agent.skillpack.yaml`.

Do not add Tavily, Finnhub, Exa, Firecrawl, Reddit, or other provider SDKs to
the plugin core. Implement provider-specific networking in the external host and
adapt it through `src.tools.adapters.mcp.MCPHostAdapter`.

## Adding A Tool

1. Place the tool implementation under `src/tools/` (e.g. `src/tools/quant/`).
2. Register it in `skillpack/tools.yaml` with `id`, `import_path`, `category`,
   `pure_function`, `network`, `llm`, and schema fields.
3. Add tests under `tests/tools/`.
4. Do not import `requests`, `httpx`, `aiohttp`, `urllib3`, `socket`, `openai`,
   `anthropic`, `langchain`, `tavily`, `finnhub`, `exa`, `firecrawl`, `reddit`
   unless the code lives within the MCP adapter boundary (`src/tools/adapters/`).

## What Is NOT Plugin Core

- Legacy modules — removed after `v0.1.0-skillpack-alpha`, see `docs/archive/`
- Historical ResearchOS code — available from `v0.1.0-skillpack-alpha` tag; not
  a current plugin runtime surface
- `src/core/` — deprecated ResearchOS modules; historical reference only
- `src/infra/` — infrastructure shims; internal reference only
- `src/workflows/` — deprecated workflow wrappers; historical reference only
- Provider-specific SDKs — host concern

## Dependency Policy

The project maintains four requirements files:

- `requirements.txt` — **default, minimal**. Contains only `pyyaml`.
  The default install does **not** bundle provider SDKs. Provider SDKs
  belong to host implementations.
- `requirements-dev.txt` — test/dev tooling (pytest, pyyaml).
- `requirements-optional.txt` — local analysis helpers (numpy, pandas,
  networkx) for local demos and notebooks, not required for production.
- `requirements-legacy.txt` — **historical / reference-only**. Contains
  all legacy dependencies (akshare, finnhub, tavily, langchain-core,
  langgraph, streamlit, qdrant-client, sqlalchemy, etc.) that were part
  of the old ResearchOS architecture. These are NOT installed by
  default and are NOT required for the current host-agnostic skill pack.

The architecture boundary tests in `tests/architecture/` and
`tests/ci/test_dependency_boundary.py` enforce this policy.

## Running The Gate Locally

```bash
bash scripts/check_plugin_gate.sh
```

Or manually:

```bash
PYTHONPATH=. python -m compileall src tests
PYTHONPATH=. pytest -q
```

## Supporting External Coding Agents

1. Update `AGENTS.md` when host-facing behavior changes.
2. Update `skillpack/examples/` when `SkillInput` / `SkillOutput` shapes change.
3. Update `examples/minimal_host_news_to_decision.py` when loader/runtime APIs change.
4. Run `bash scripts/check_plugin_gate.sh` before push.
5. Do not reintroduce ResearchOS or legacy as primary path.
