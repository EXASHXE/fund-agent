# Decision Support Evidence Anchor Policy

Formal active decisions must be anchored to real, trade-specific evidence.

## Active Actions

The active actions are:

- `BUY`
- `SELL`
- `INCREASE`
- `REDUCE`

Each active action requires rationale anchors that:

- exist in the supplied `EvidenceGraph`;
- are listed in the trade's `evidence_refs` or `risk_flags_refs`;
- relate to the specific fund, trade, risk flag, or action;
- are not arbitrary first-N evidence IDs.

## Downgrade Rule

If active evidence anchors are missing, fake, unrelated, or not present in the
graph, downgrade to `WAIT` or `HOLD` and explain the missing evidence in the
audit trail.

## Passive Actions

`WAIT`, `HOLD`, and `PAUSE_DCA` may be anchorless only when insufficient
evidence is explicitly recorded.
