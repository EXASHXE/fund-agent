# Non-Decision Policy

`thesis_generation` must not produce formal trade decisions.

## Allowed

- `thesis_draft`
- narrative reasoning;
- counterarguments;
- evidence gap summaries;
- escalation recommendation to `decision_support`.

## Forbidden

- `Decision`
- `ExecutionLedger`
- executable BUY, SELL, INCREASE, REDUCE, WAIT, HOLD, or PAUSE_DCA output;
- fabricated evidence IDs;
- direct network calls or provider SDK imports.

If the user asks what action to take, the host should compile an EvidenceGraph
and call `decision_support`.
