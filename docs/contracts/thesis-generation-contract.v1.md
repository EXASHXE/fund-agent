# Thesis Generation Contract v1

## Overview

`thesis_generation` is an **artifact-only** supporting skill. It produces a
`ThesisDraft` artifact from host-supplied evidence and context. It does **not**
fetch data, call LLMs, or produce formal decisions.

## Runtime

- Runtime skill ID: `thesis_generation`
- Runtime class: `src.skills_runtime.thesis_generation:ThesisGenerationSkill`
- Markdown slug: `thesis-generation`

## Inputs

| Field | Source | Required | Notes |
|---|---|---|---|
| `payload.evidence_graph` | SkillInput.payload | No | Host-compiled EvidenceGraph dict |
| `payload.evidence_items` | SkillInput.payload | No | List of evidence item dicts |
| `payload.fund_analysis_report` | SkillInput.payload | No | Fund analysis report dict |
| `payload.artifacts` | SkillInput.payload | No | Additional artifacts dict |
| `payload.thesis_question` | SkillInput.payload | No | Primary thesis question |
| `payload.topic` | SkillInput.payload | No | Alternative to thesis_question |
| `payload.related_entities` | SkillInput.payload | No | Entity identifiers |
| `payload.research_focus` | SkillInput.payload | No | Focused research area |
| `payload.constraints` | SkillInput.payload | No | Constraint dict |
| `payload.risk_profile` | SkillInput.payload | No | Risk profile dict |
| `skill_input.evidence_context` | SkillInput | No | List of evidence context refs |
| `skill_input.kg_context.fund_codes` | SkillInput | No | Fund code identifiers |

## Output Artifact: `thesis_draft`

| Field | Type | Notes |
|---|---|---|
| `task_id` | string | From SkillInput |
| `topic` | string | Resolved thesis question/topic |
| `related_entities` | list[string] | Normalized entity identifiers |
| `thesis_statement` | string | Deterministic thesis statement |
| `supporting_evidence` | list[dict] | Evidence classified as supporting |
| `counter_evidence` | list[dict] | Evidence classified as counter |
| `neutral_evidence` | list[dict] | Evidence classified as neutral |
| `missing_evidence` | list[dict] | Identified evidence gaps |
| `confidence_assessment` | dict | `{level, score, reason}` |
| `watch_conditions` | list[string] | Conditions to monitor |
| `invalidating_conditions` | list[string] | Conditions that would invalidate |
| `next_research_questions` | list[string] | Suggested next research |
| `source_summary` | dict | Source type counts |
| `limitations` | list[string] | Known limitations |
| `decision_boundary_note` | string | Always present; marks draft-only status |

## Confidence Assessment

| Level | Score Range | Meaning |
|---|---|---|
| `HIGH` | >= 0.7 | Strong evidence basis |
| `MEDIUM` | 0.4 - 0.69 | Moderate evidence with gaps |
| `LOW` | < 0.4 | Insufficient evidence |

## Status Semantics

| Status | Condition |
|---|---|
| `OK` | Evidence context exists and confidence is not LOW |
| `PARTIAL` | Evidence is sparse/missing or confidence is LOW |
| `FAILED` | Invalid input shape or unrecoverable error |

## Forbidden

- `thesis_generation` must **not** produce formal `Decision` or `ExecutionLedger`.
- `thesis_generation` must **not** output BUY/SELL/HOLD formal actions.
- `thesis_generation` must **not** call LLMs, provider SDKs, or network.
- Formal decisions require `decision_support`.

## Evidence Classification

Evidence items are classified by `direction` and `category` fields:

- `direction: "positive"` or `category: "supporting"/"bullish"` → supporting
- `direction: "negative"` or `category: "counter"/"bearish"/"risk"` → counter
- `category: "missing"/"gap"/"absent"` → missing
- All others → neutral
