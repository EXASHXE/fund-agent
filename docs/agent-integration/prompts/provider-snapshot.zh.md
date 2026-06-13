# Provider 快照模式提示词

## 主机职责

1. 运行 provider adapter 获取数据
2. 构建 provider_data_snapshot
3. 传递给 fund-agent 工作流

## 调用方式

```bash
# AkShare NAV 历史
python examples/host_data_adapters/provider_smoke.py --provider akshare --capability FUND_NAV_HISTORY --fund-code 000001

# 构建 snapshot
# (主机自行构建，参考 schemas/provider_data_snapshot.schema.json)
```

## 禁止

- 不在 core runtime 中获取数据
- 不提交真实 provider 数据
- 不提交 provider 凭证
