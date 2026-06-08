# Thesis Generation Fixtures

Fake/sample data for exercising `thesis_generation` runtime skill.

**NOT investment advice. NOT real-time market data. No real personal holdings.**

`thesis_generation` produces draft artifacts only. The host owns real data
fetching and provider integration. Formal decisions require `decision_support`.

## Fixtures

| Fixture | Purpose |
|---|---|
| `thesis_with_mixed_evidence.json` | Mixed positive/negative evidence produces balanced thesis |
| `thesis_missing_evidence_partial.json` | Minimal evidence context produces partial, low-confidence thesis |
| `thesis_from_fund_analysis_artifacts.json` | Fund analysis report and artifacts inform thesis from existing analysis |
| `evidence_graph_balanced_thesis.json` | Evidence graph format with balanced supporting and counter evidence |
| `sparse_context_low_confidence.json` | Sparse evidence context results in low-confidence thesis |
| `fund_analysis_report_thesis.json` | Combined evidence graph and fund analysis report produce informed thesis |

## Usage

```bash
python scripts/run_skill.py --skill thesis_generation --input examples/thesis_generation/evidence_graph_balanced_thesis.json --pretty
python scripts/run_skill.py --skill thesis-generation --input examples/thesis_generation/evidence_graph_balanced_thesis.json --pretty
```

Both underscore (`thesis_generation`) and hyphenated (`thesis-generation`) slug
forms are supported.

## Boundary Disclaimers

- All data in fixtures is fake/sample only.
- Not investment advice.
- Not real-time market data.
- No real personal holdings.
- Host owns real data fetching and provider integration.
- `thesis_generation` produces artifact-only `ThesisDraft`.
- Formal decisions require `decision_support`.
