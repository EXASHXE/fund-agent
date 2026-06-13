# Provider Snapshot Prompt Example

## User Request

"帮我获取华夏成长混合的NAV历史数据"

## Host Responsibilities

1. Run AkShare adapter to fetch NAV history
2. Build provider_data_snapshot
3. Save snapshot for fund-agent consumption

## Commands

```bash
# Fetch NAV history
python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001

# Build snapshot (host-side)
# Reference schemas/provider_data_snapshot.schema.json
```

## Expected Output

- ProviderResult with NAV history data
- Snapshot JSON conforming to schema

## Safety Boundary

- Provider adapters are host-layer, not core runtime
- Do not commit real provider data
- Do not commit credentials
