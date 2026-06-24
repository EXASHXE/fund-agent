# Factor Snapshot Contract

This document describes the factor snapshot data structure and contract.

## Snapshot Structure

```json
{
  "snapshot_type": "factor_snapshot",
  "generated_at": "2026-06-15T11:21:41.293321+00:00",
  "portfolio_factors": {...},
  "holding_factors": [...],
  "data_completeness_factors": {...},
  "profile_coverage": {...},
  "market_factors": {...},
  "news_factors": {...},
  "data_quality": {...}
}
```

## Key Design Principle: Missing Values

**Critical**: Missing values are represented as `null` (Python `None`), NOT as `0`.

- `current_value: null` means "unknown/missing"
- `current_value: 0` means "explicitly zero"

This prevents fake precision in reports.

## Portfolio Factors

```json
{
  "total_current_value": null,        // null if unknown, not 0
  "total_current_value_missing": true,
  "known_cost_basis_total": null,     // null if no known values
  "cost_basis_missing_count": 15,
  "cash_ratio": null,                 // cannot calculate without total_value
  "cash_ratio_missing": true,
  "risky_asset_ratio": null,
  "low_risk_asset_ratio": null,
  "sector_concentration": null,
  "theme_concentration": null,
  "single_position_weight": null,
  "top_3_concentration": null,
  "top_5_concentration": null,
  "qdii_overseas_exposure": null,
  "equity_like_exposure": null,
  "bond_cash_exposure": null,
  "short_term_trading_bucket_exposure": null
}
```

## Holding Factors

```json
{
  "fund_code": "...",
  "fund_name": "...",
  "current_value": null,           // null if missing, NOT 0
  "current_value_missing": true,
  "weight": null,                  // null if current_value is missing
  "known_cost_basis": null,
  "unrealized_gain_loss_amount": null,
  "unrealized_gain_loss_pct": null,
  "cost_basis_confidence": "missing|high|unparseable",
  "units_missing": true,
  "nav_missing": true,
  "cost_basis_missing": true,
  "risk_bucket": "high|medium|low|unknown",
  "theme_tags": [...],
  "source_platform": "..."
}
```

## Data Completeness Factors

Always computed, even without current_value:

```json
{
  "holdings_count": 15,
  "holdings_with_current_value": 0,
  "holdings_without_current_value": 15,
  "cost_basis_complete_count": 0,
  "cost_basis_missing_count": 15,
  "units_complete_count": 0,
  "units_missing_count": 15,
  "nav_complete_count": 0,
  "nav_missing_count": 15
}
```

## Profile Coverage

From KG context:

```json
{
  "kg_context_available": true,
  "fund_entities_count": 15,
  "entities_count": 62,
  "provider_snapshot_available": false,
  "fund_profiles_available": false,
  "fund_holdings_available": false,
  "benchmark_available": false
}
```

## News Factors

```json
{
  "total_news_items": 80,
  "news_count_by_entity": {...},
  "news_count_by_topic": {...},
  "news_count_by_query_type": {
    "holding_company": 20,
    "benchmark": 5,
    "theme_fallback": 55
  },
  "fallback_query_news_count": 55,
  "specific_query_news_count": 25,
  "stale_news_by_topic": {...},
  "provider_coverage_score": 0.25,
  "negative_risk_signal_count": 3,
  "positive_catalyst_count": 12
}
```

## Data Quality

```json
{
  "cost_basis_partial": false,
  "cost_basis_missing_count": 15,
  "units_missing_count": 15,
  "nav_missing_count": 15,
  "current_value_missing_count": 15,
  "news_snapshot_missing": false,
  "provider_snapshot_missing": true,
  "factor_confidence": "low",
  "value_factors_available": false,
  "uncertainty_note": "市值权重/收益率/仓位贡献无法计算，因为当前市值数据缺失"
}
```

## Uncertainty Note

When `total_current_value` is missing, the `uncertainty_note` field provides a human-readable explanation:

```
"市值权重/收益率/仓位贡献无法计算，因为当前市值数据缺失"
```

(Translation: "Market value weights/return/contribution cannot be calculated because current market value data is missing")

## Rules

1. **No fabricated values**: Do not calculate unknown cost_basis, units, or NAV
2. **Missing = null**: Use `null` for missing values, not `0`
3. **Uncertainty disclosure**: Always provide uncertainty_note when data is missing
4. **Non-value factors**: Always compute data completeness and profile coverage factors
5. **Value-dependent factors**: Mark as null when current_value is unavailable