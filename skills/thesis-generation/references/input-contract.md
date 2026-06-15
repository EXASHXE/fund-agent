# Thesis Generation Input Contract

## Required fields

- `related_entities` (list[str]): Fund codes or market identifiers for thesis generation
- OR `fund_codes` (list[str]) in `kg_context`: Alternative entity specification

## Optional fields

- `evidence_context` (list): Existing evidence items to ground the thesis
- `user_goal` (str): User's investment goal or question
- `thesis_type` (str): Type of thesis to generate (bullish, bearish, neutral)

## MCP requirements

None — this skill is fully local and deterministic.

## Output

Produces `ThesisDraft` artifact with thesis statement, supporting arguments, counter-arguments, and evidence references.

## Forbidden

This skill must NOT produce formal `Decision` or `ExecutionLedger` artifacts.
