# Host Integration

`fund-agent` is a host-agnostic skill pack. The external agent host is the
planner and orchestrator. `fund-agent` provides manifest metadata, runtime
skills, schemas, tools, and contracts.

## Responsibilities

- Host agent: planning, skill order, task memory, MCP provider wiring,
  orchestration, retries, and final UX.
- `fund-agent`: callable skills, pure tools, evidence contracts, graph helpers,
  decision support, and audit-friendly outputs.

Host integrations do not need to call `src.core.research_os`.

## Integration Flow

1. Load `skillpack/fund-agent.skillpack.yaml`.
2. Resolve the runtime path for the skill the host wants to call.
3. Inject an `MCPHostAdapter` implementation if the skill needs MCP data.
4. Build a `SkillInput`.
5. Call `Skill.run(input)`.
6. Collect `SkillOutput.evidence_items`, `artifacts`, `warnings`, and `errors`.
7. Call `compile_evidence_graph` when the host wants to consolidate evidence.
8. Call `DecisionSupportSkill` when the host wants a formal `Decision` and
   `ExecutionLedger`.
9. Choose any order. `fund-agent` does not impose an agent loop.

## Pseudocode

```python
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.evidence.validators import compile_evidence_graph

manifest = load_skillpack_manifest("skillpack/fund-agent.skillpack.yaml")

news_spec = manifest.skill("news_research")
news_skill_cls = resolve_runtime("src.skills_runtime.news_research:NewsResearchSkill")
news_skill = news_skill_cls(mcp_adapter=host_mcp)

skill_input = SkillInput(
    task_id="host-task-1",
    step_id="news-1",
    skill_name="news_research",
    payload={"query": "fund:110011"},
    required_mcp_capabilities=news_spec.requires_mcp,
)
news_output = news_skill.run(skill_input)

compile_result = compile_evidence_graph(news_output.evidence_items)

decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="host-task-1",
        step_id="decision-1",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "review fund",
            "risk_budget": {"max_drawdown": 0.1},
            "portfolio_context": {},
            "time_horizon": "1 year",
        },
    )
)
```

## MCP Adapter Injection

`src.tools.adapters.mcp.MCPHostAdapter` is a boundary interface. Host runtimes
can adapt any provider behind it, but provider SDKs must stay outside
`fund-agent` skills.

Skills receive the adapter through their constructor:

```python
news_skill = NewsResearchSkill(mcp_adapter=host_mcp)
```

or through host-specific dependency injection. MCP call results must be
structured dictionaries.

## Decision Support

Only `src.skills_runtime.decision_support.DecisionSupportSkill` produces formal
`Decision` and `ExecutionLedger` artifacts. Active actions require real
EvidenceGraph anchors. WAIT/HOLD decisions may be anchorless only when
insufficient evidence is explicitly recorded.

`src.skills_runtime.thesis_generation.ThesisGenerationSkill` produces a
`thesis_draft` artifact only. It must not produce a formal `Decision`; hosts
should call `DecisionSupportSkill` for that step.

## No Required Workflow

External agents can:

- call only quant/fund analysis,
- collect news and sentiment first,
- compile evidence after every step or once at the end,
- call their own planner,
- skip decision support,
- combine this skill pack with other repositories.

`fund-agent` does not own the agent loop.
