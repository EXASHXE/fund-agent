# Skill Output Contract v1

**Version:** 1.0
**Contract ID:** `skill-output.v1`

This document defines the stable host-facing output contract for all
`fund-agent` runtime skills.

## SkillOutput Fields

| Field | Type | Description |
|---|---|---|
| `step_id` | string | Step identifier from the input |
| `skill_name` | string | Runtime skill identifier |
| `evidence_items` | list[EvidenceItem] | Evidence produced by the skill |
| `artifacts` | dict | Skill-specific output artifacts |
| `warnings` | list[string] | Non-fatal warning messages |
| `errors` | list[error object] | Structured error objects (see below) |
| `used_mcp_capabilities` | list[string] | MCP capabilities used during execution |
| `status` | string | One of `OK`, `PARTIAL`, `FAILED` |

## Error Object Shape

Every item in `SkillOutput.errors` must be a dict with these canonical fields:

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `code` | string | Yes | — | Machine-readable error code (e.g. `INVALID_INPUT`, `EVIDENCE_BUILD_FAILED`) |
| `message` | string | Yes | — | Human-readable error description |
| `details` | dict | Yes | `{}` | Structured error context; must be a dict, never None or string |
| `recoverable` | boolean | Yes | `true` | Whether the skill could potentially succeed with different input |

### Rules

- `code` must be a non-empty string from the `SkillErrorCode` literal or a
  bridge-level error code.
- `message` must be a non-empty string.
- `details` must always be a dict. If no details are available, it defaults to
  an empty dict `{}`. Non-dict values are wrapped as `{"raw_details": value}`.
- `recoverable` must always be a boolean. It defaults to `true` for
  potentially transient errors and `false` for contract violations or
  permanent failures.
- Partial dicts (missing fields) are normalized to canonical shape by
  `normalize_skill_error()` during `SkillOutput.to_dict()` serialization.

### Standard Error Codes

| Code | Meaning | Typical recoverable |
|---|---|---|
| `MISSING_MCP_CAPABILITY` | Required MCP capability not available | `false` |
| `MCP_CALL_FAILED` | MCP adapter call returned an error | `true` |
| `INVALID_INPUT` | Input payload is malformed or missing required fields | `false` |
| `EVIDENCE_BUILD_FAILED` | Individual evidence item construction failed | `true` |
| `EMPTY_RESULT` | Skill produced no evidence items | `true` |
| `INTERNAL_ERROR` | Unexpected runtime failure | `true` |
| `CONTRACT_VIOLATION` | Skill contract rule violated (e.g. a formal artifact crosses a forbidden boundary) | `false` |

### Bridge-Level Error Codes

Bridge-level errors (from the runtime bridge CLI) use the same canonical shape:

| Code | Meaning |
|---|---|
| `INVALID_INPUT` | Bridge input is missing, malformed, or invalid |
| `UNKNOWN_SKILL` | Requested skill ID is not in the manifest |
| `RUNTIME_LOAD_FAILED` | Runtime class could not be imported or instantiated |
| `SKILL_RUN_FAILED` | Skill raised an unhandled exception |
| `JSON_SERIALIZATION_FAILED` | Skill output is not JSON-serializable |
| `MISSING_MCP_CAPABILITY` | Bridge could not provide required MCP capabilities |
| `MISSING_REPORT_SECTIONS` | fund_analysis did not produce report_sections for --emit-report |
| `UNSUPPORTED_EMIT_REPORT` | --emit-report markdown requested for non-fund_analysis skill |

Bridge-level errors default `recoverable` to `false` since they represent
structural failures that require host-side changes.

## Warnings

Warnings are plain strings in `SkillOutput.warnings`. They are informational
and do not indicate failure.

## Evidence Items

Evidence items are `EvidenceItem` objects/dicts as defined by the
[evidence contract v2](./evidence-contract.v2.md).

## Artifacts

Artifacts are skill-specific. See per-skill artifact contracts:
- [fund-analysis-artifacts.v1.md](./fund-analysis-artifacts.v1.md)
- [decision-support-contract.v1.md](./decision-support-contract.v1.md)
- [thesis-generation-contract.v1.md](./thesis-generation-contract.v1.md)

## Status Values

| Status | Meaning |
|---|---|
| `OK` | Skill completed successfully with usable output |
| `PARTIAL` | Skill produced output but with degraded quality, missing data, or non-fatal errors |
| `FAILED` | Skill could not produce usable output due to invalid input or runtime error |

## Formal Decision Boundary

Only `decision_support` may produce formal `Decision` / `ExecutionLedger`
artifacts. All other skills are forbidden from producing these artifact types.

- `fund_analysis` MUST NOT produce formal `Decision` or `ExecutionLedger`.
- `thesis_generation` MUST NOT produce formal `Decision` or `ExecutionLedger`.
- `news_research` and `sentiment_analysis` are MCP adapter skills that produce
  `SoftEvidence` only.

## Cross-References

- [Evidence contract v2](./evidence-contract.v2.md)
- [Decision support contract v1](./decision-support-contract.v1.md)
- [Fund analysis artifacts v1](./fund-analysis-artifacts.v1.md)
- [Thesis generation contract v1](./thesis-generation-contract.v1.md)
- [Report output contract v1](./report-output-contract.v1.md)
- [Runtime bridge CLI](../install/runtime-bridge-cli.md)
