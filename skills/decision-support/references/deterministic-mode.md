# Deterministic Mode

When `payload.deterministic=true`, the runtime must make repeatable identifiers
and timing fields for the same payload.

## Stable Fields

- `decision_id`
- `created_at`
- audit trail generated timestamp

## Nondeterministic Mode

When `deterministic=false` or the field is absent, runtime UUIDs and current
timestamps are allowed.

## Host Use

Use deterministic mode in tests, demos, reproducible examples, and audit
snapshots. Hosts may omit it for live workflows where unique IDs and live
timestamps are desired.
