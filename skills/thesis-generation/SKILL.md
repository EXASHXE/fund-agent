---
id: thesis_generation
name: thesis-generation
runtime: src.skills_runtime.thesis_generation:ThesisGenerationSkill
input_schema: src.schemas.skill:SkillInput
output_schema: src.schemas.skill:SkillOutput
required_mcp_capabilities: []
produced_artifact: thesis_draft
forbidden_behavior:
  - formal_decision_generation
role: supporting
---

# Thesis Generation (supporting skill)

`thesis-generation` is a **supporting skill** in the
`fund-agent` Superpowers-compatible skill collection. It should be
loaded only when the host wants a draft investment thesis before
deciding whether to escalate to a formal decision. For ordinary
portfolio and fund report requests, start with the primary skill
`fund-analysis` and stop there.

`thesis-generation` itself maps to the Python runtime ID
`thesis_generation` declared in
`skillpack/fund-agent.skillpack.yaml`. The agent-facing skill name is
the hyphenated slug `thesis-generation`; the underscore
`thesis_generation` is the runtime ID only.

This skill produces a **`thesis_draft` artifact only**. It **must
not** produce a formal `Decision` or `ExecutionLedger`. Only
`decision-support` may produce those.

## Purpose

Use `thesis_generation` to create a `thesis_draft` artifact from host-provided
context and evidence references. It helps hosts write an investment thesis but
must not produce formal `Decision` or `ExecutionLedger` artifacts.

## When to use

- The host has already gathered evidence and wants a draft thesis.
- The user asks for reasoning, thesis framing, counterpoints, or a narrative
  report section.
- The host wants an intermediate artifact before deciding whether to call
  `decision_support`.

**`thesis-generation` is not required for ordinary `fund-analysis`
flows.** Load it only when the host wants a draft thesis.

## When not to use

- Do not use it to produce BUY, SELL, INCREASE, REDUCE, WAIT, or HOLD.
  Only `decision-support` may produce formal `Decision` artifacts.
- Do not use it for portfolio calculations.
- Do not use it to fetch news or sentiment.
- Do not treat a thesis draft as executable advice.

## Host responsibilities

The host owns evidence selection, context assembly, final wording, user
suitability, and the decision to escalate to `decision_support`. The host must
provide evidence references or context; the skill does not fetch data.

## MCP capabilities required

None.

## Inputs

Runtime skill ID: `thesis_generation`.
Runtime: `src.skills_runtime.thesis_generation:ThesisGenerationSkill`.

Expected inputs include:

- `evidence_context`
- `payload.objective`
- `payload.evidence_items` or host summary context
- optional portfolio or fund context

## Outputs

- `artifacts.thesis_draft`
- `warnings`
- `errors`

## Missing-data policy

If evidence context is thin, emit a limited thesis draft or warnings. Do not
invent missing facts, evidence IDs, market data, or user constraints.

## Forbidden behavior

This skill must never produce formal `Decision` or `ExecutionLedger`, make
direct network calls, import provider SDKs, call LLMs, or bypass the host's
evidence selection.

## How it composes with other skills

Use it after `fund_analysis`, `news_research`, or `sentiment_analysis` have
provided evidence. If the user then asks what to buy, sell, increase, reduce,
wait on, or hold, compile evidence and call `decision_support`.

## Minimal example

```json
{
  "task_id": "task-1",
  "step_id": "thesis-1",
  "skill_name": "thesis_generation",
  "payload": {},
  "evidence_context": ["ev-1", "ev-2"],
  "required_mcp_capabilities": []
}
```

See `references/thesis-template.md` and `references/non-decision-policy.md`.
