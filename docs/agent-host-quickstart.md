# Agent Host Quickstart

`fund-agent` is a host-agnostic financial research skill pack. It is meant to
be mounted by an external agent host such as Codex, Claude Code, OpenCode,
OpenClaw, or Hermes.

## Ownership

The external agent owns orchestration. It decides task decomposition, skill
order, retry policy, memory, MCP provider wiring, and final user interaction.

`fund-agent` provides:

- [`skillpack/fund-agent.skillpack.yaml`](../skillpack/fund-agent.skillpack.yaml)
- [`skills/README.md`](../skills/README.md)
- `skills/<slug>/SKILL.md` Markdown-first policy guides
- [`skillpack/tools.yaml`](../skillpack/tools.yaml)
- host-callable `src.skills_runtime` classes
- `SkillInput` / `SkillOutput` contracts
- EvidenceGraph compile and review tools
- KnowledgeGraph helpers
- Decision support
- MCP adapter boundary interfaces

ResearchOS is a historical reference workflow (see `v0.1.0-skillpack-alpha` tag). It is not required for host integration and not part of the current runtime.

Discover callable skills from the manifest. Do not infer runtime skill IDs from
folder names: `fund_analysis` is a runtime skill ID, while `fund-analysis` is a
Markdown documentation slug. `fund-analyst` is legacy/reference-only material.

## Minimal Flow

```python
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.evidence.validators import compile_evidence_graph

manifest = load_skillpack_manifest()

news_spec = manifest.skill("news_research")
news_cls = resolve_runtime(news_spec.runtime)
news_output = news_cls(mcp_adapter=host_mcp).run(
    SkillInput(
        task_id="host-task-1",
        step_id="news-1",
        skill_name="news_research",
        payload={"query": "fund:110011", "related_entities": ["fund:110011"]},
        required_mcp_capabilities=news_spec.requires_mcp,
    )
)

compile_result = compile_evidence_graph(news_output.evidence_items)

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "review fund",
            "portfolio_context": {},
            "risk_budget": {},
            "time_horizon": "1 year",
        },
    )
)
```

## Handling SkillOutput Errors

Hosts should treat `SkillOutput.errors` as structured control data, not as
exceptions hidden in text:

```python
if news_output.errors:
    for error in news_output.errors:
        code = error["code"]
        if code == "MISSING_MCP_CAPABILITY":
            # Wire or choose a host MCP capability before retrying.
            ...
        elif code == "MCP_CALL_FAILED":
            # Apply host retry/rate-limit policy.
            ...
        else:
            # Decide whether to continue with partial evidence.
            ...
```

## MCPHostAdapter

News and sentiment runtime skills receive host data through
`src.tools.adapters.mcp.MCPHostAdapter`. The host can adapt any provider behind
that interface. Provider SDKs and network calls stay outside this repository.

## SkillOutput Errors

Every runtime skill returns `SkillOutput`. Failures are represented in
`SkillOutput.errors` with standard codes such as:

- `MISSING_MCP_CAPABILITY`
- `MCP_CALL_FAILED`
- `INVALID_INPUT`
- `EVIDENCE_BUILD_FAILED`
- `EMPTY_RESULT`
- `INTERNAL_ERROR`
- `CONTRACT_VIOLATION`

Hosts should inspect `status`, collect `warnings`, and decide whether an error
is recoverable before retrying or moving to another skill.
