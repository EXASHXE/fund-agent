# Test Support Helpers

Shared test helpers that reduce duplication across test layers while
preserving explicit assertion semantics.

## error_shape.py

Canonical host-visible error shape assertions. Used by runtime_bridge,
integration, and golden tests to verify that every host-visible error
object has `code` (non-empty string), `message` (non-empty string),
`details` (dict), and `recoverable` (bool).

- `assert_canonical_error(error)` — single error object
- `assert_envelope_errors_are_canonical(envelope)` — errors[] list
- `assert_top_level_error_is_canonical(envelope)` — top-level error key
- `assert_all_errors_are_canonical(envelope)` — both errors[] and top-level

## bridge_runner.py

Runtime bridge test invocation helpers for subprocess and in-process
execution. Used by runtime_bridge and integration tests.

- `project_root()` — repository root directory
- `bridge_env()` — environment for source-checkout bridge execution
- `run_bridge_subprocess(args)` — subprocess CLI invocation (canonical)
- `run_bridge_json(args)` — subprocess CLI invocation with parsed JSON output
- `stdout_text(result)` — extract stdout text
- `parse_stdout_json(result)` — parse stdout as JSON with assertion
- `write_temp_json(data)` — write temporary JSON input file
- `write_temp_text(tmp_path, text)` — write raw text under pytest tmp_path
- `run_bridge_inprocess_json(...)` — in-process bridge execution

Compatibility aliases:
- `run_bridge` → `run_bridge_subprocess`
- `parse_json_stdout` → `parse_stdout_json`

## formal_boundary.py

Formal-decision boundary constants and assertions. Used by integration,
skills_runtime, and golden tests to verify that formal decision/ledger
artifacts appear only where allowed.

- `FORMAL_DECISION_ARTIFACT_KEYS` — {"decision", "decisions", "execution_ledger", "execution_ledgers"}
- `ACTIVE_ACTIONS` — {"BUY", "SELL", "INCREASE", "REDUCE"}
- `PASSIVE_ACTIONS` — {"WAIT", "HOLD", "PAUSE_DCA"}
- `FAKE_ANCHORS` — known placeholder anchor strings
- `assert_no_formal_decision_artifacts(artifacts)`
- `extract_formal_decisions(artifacts)`
- `assert_active_decisions_have_anchors(decisions)`
- `assert_passive_empty_anchor_has_structured_justification(decision)`

## Rules

- Support helpers must not import provider SDKs or perform network calls.
- Support helpers should not mask behavior changes; tests should still
  assert explicit semantics.
