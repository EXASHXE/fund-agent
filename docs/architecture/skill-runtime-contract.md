# Skill Runtime Contract

This document defines the beta Skill runtime boundary for Research OS. It is a
host-native capability contract, not a production provider integration.

## Flow

`Planner -> PlanStep.required_mcp_capabilities -> SkillInput -> SkillRegistry -> MCPHostAdapter -> SkillOutput`

1. `Planner` reads task and KG context, then emits ordered `PlanStep` objects.
2. Each `PlanStep` declares `required_mcp_capabilities` and
   `evidence_requirements`.
3. `ResearchOS` converts the step to `SkillInput` with task id, step id,
   payload, KG context, required MCP capabilities, current evidence ids, and
   metadata.
4. `SkillRegistry` injects `MCPHostAdapter` and invokes the registered skill.
5. Skills may call only host-declared MCP capabilities through the adapter.
6. `SkillOutput` is the only return channel: evidence items, artifacts,
   warnings, errors, used MCP capabilities, and status.
7. `DecisionEngine` is the only formal `Decision` source. Skills must not
   return active or passive decisions.

## SkillInput

`src.schemas.skill.SkillInput` contains:

- `task_id`
- `step_id`
- `skill_name`
- `payload`
- `kg_context`
- `required_mcp_capabilities`
- `evidence_context`
- `metadata`

## SkillOutput

`src.schemas.skill.SkillOutput` contains:

- `step_id`
- `skill_name`
- `evidence_items`
- `artifacts`
- `warnings`
- `errors`
- `used_mcp_capabilities`
- `status`: `OK`, `PARTIAL`, or `FAILED`

`SkillOutput.to_dict()` must be JSON serializable.

## MCP Capability Audit

When a required MCP capability is missing, the failure is represented as a
structured `SkillOutput.errors` entry and copied into
`FinalThesis.artifacts["mcp_capability_audit"]`.

Audit records include:

- `step_id`
- `skill_name`
- `required_mcp_capabilities`
- `missing_mcp_capabilities`
- `used_mcp_capabilities`
- `status`

## Evidence Rules

- News and sentiment runtime skills produce `SoftEvidence` by default.
- Quant/fund analysis runtime skills produce `HardEvidence`.
- `HardEvidence.confidence_weight` must be exactly `1.0`.
- Thesis generation produces draft artifacts only.
- Formal decisions and execution ledgers are generated after EvidenceGraph
  compilation and Critic review.

## Provider Boundary

Research OS declares host MCP capabilities through
`src.tools.adapters.mcp.MCPHostAdapter`. The repository does not import or bind
concrete provider SDKs in runtime skills. Provider credentials, network access,
rate limits, and vendor clients belong to the host process.
