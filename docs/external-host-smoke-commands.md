# External Host Smoke Commands

Copy-paste commands for external hosts to verify the fund-agent runtime bridge
in a source-checkout environment. All commands use existing fixtures and fake/
sample data only.

**Not investment advice. No live data. No broker execution.**
**Host owns provider SDKs, network, credentials, and MCP adapter.**
**Requires Python 3.11+ for source-checkout runtime.**

## 1. List skills

```bash
python scripts/run_skill.py --list-skills --pretty
```

Expected: five runtime skill IDs listed with ok=true.

## 2. Explain fund_analysis input

```bash
python scripts/run_skill.py --skill fund_analysis --explain-input --pretty
```

Expected: input_contract describes portfolio_snapshot, ledger_derived,
and related_entities_baseline modes.

## 3. Validate fund_analysis fixture

```bash
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json \
  --validate-input --pretty
```

Expected: validation_result.valid is true.

## 4. Run fund_analysis JSON

```bash
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json --pretty
```

Expected: ok=true, status OK, artifacts include report_sections.

## 5. Emit fund_analysis Markdown

```bash
python scripts/run_skill.py --skill fund_analysis \
  --input examples/scenarios/cn_fund_7d_redemption_fee.json \
  --emit-report markdown --output /tmp/report.md
```

Expected: Markdown file written, starts with "# Personal fund report".

## 6. Run decision_support

```bash
python scripts/run_skill.py --skill decision_support \
  --input examples/decision_support/single_active_buy_with_evidence.json --pretty
```

Expected: ok=true, artifacts include decision and execution_ledger.

## 7. Run thesis_generation

```bash
python scripts/run_skill.py --skill thesis_generation \
  --input examples/thesis_generation/thesis_with_mixed_evidence.json --pretty
python scripts/run_skill.py --skill thesis-generation \
  --input examples/thesis_generation/thesis_with_mixed_evidence.json --pretty
```

Expected: ok=true, artifacts include thesis_draft. Both slug forms work.

## 8. Run news_research with canned MCP input

Write `news_input.json`:

```json
{
  "payload": {"query": "fund:FAKE001"},
  "mcp_responses": {
    "financial_news": {
      "items": [
        {
          "source_type": "financial_news",
          "timestamp": "2026-01-01T00:00:00",
          "related_entities": ["fund:FAKE001"],
          "claim": "Fake host-supplied financial news item",
          "direction": "neutral",
          "confidence_weight": 0.5
        }
      ]
    }
  }
}
```

Then:

```bash
python scripts/run_skill.py --skill news_research --input news_input.json --pretty
```

Expected: ok=true, SoftEvidence items, mcp_response artifact.

## 9. Run sentiment_analysis with canned MCP input

Write `sentiment_input.json`:

```json
{
  "payload": {"query": "fund:FAKE001"},
  "mcp_responses": {
    "social_sentiment": {
      "items": [
        {
          "source_type": "social_sentiment",
          "timestamp": "2026-01-01T00:00:00",
          "related_entities": ["fund:FAKE001"],
          "claim": "Fake host-supplied sentiment signal",
          "sentiment_score": 0.2,
          "direction": "neutral"
        }
      ]
    }
  }
}
```

Then:

```bash
python scripts/run_skill.py --skill sentiment_analysis --input sentiment_input.json --pretty
```

Expected: ok=true, SoftEvidence items, mcp_response artifact.

## 10. OpenCode plugin boundary note

The OpenCode plugin is metadata + doc-reader only. It does not invoke
Python, call the runtime bridge, or execute the deterministic runtime.
External hosts must use the runtime bridge CLI or direct Python import for
deterministic skill execution. Source checkout is required for Python
runtime access. See `docs/install/opencode.md` and `docs/install/manual-host.md`.

## Data disclaimer

All fixture files under `examples/` contain fake/sample data only. They are
not investment advice, not real-time market data, and do not include real
personal holdings or transaction records. The host owns real data fetching,
provider SDK integration, credentials, and MCP provider implementation.
