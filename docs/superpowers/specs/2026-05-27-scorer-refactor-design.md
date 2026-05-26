# Step 1: 拆分 FundAnalyzer

## 目标

将 `src/analysis/scorer.py` (784行) 中的 `FundAnalyzer` 拆分为多个职责单一的模块，
不改变返回接口结构，不改变测试断言。

## 拆分方案

```
src/analysis/
├── scorer.py              # 保留: FundAnalyzer Facade (~50行), 委托给各子模块
├── loader.py              # 新增: FundDataLoader - 数据采集 + 完整度评估
├── scoring/
│   ├── __init__.py
│   ├── macro.py           # MacroScorer - 宏观评分 (硬编码规则原样搬入)
│   ├── meso.py            # MesoScorer - 中观评分
│   └── micro.py           # MicroScorer - 微观评分
├── factors.py             # 新增: FactorMatrixBuilder + 置信度计算
└── metrics.py             # 新增: Sortino/HHI/高级指标 计算
```

## 接口契约

- `FundAnalyzer.load_fund(code)` → 委托给 `FundDataLoader`
- `FundAnalyzer.score_fund(code)` → 委托给各 scorer + factors + metrics
- 返回 dict 结构完全不变
- `FundAnalyzer.funds` dict 结构完全不变
- 所有公共方法签名不变

## 不改变

- 硬编码评分逻辑 (首期只搬家，二期配置化)
- 测试文件
- `score_fund()` 返回 dict
- 外部模块对 `FundAnalyzer` 的 import

## 验收标准

- `python3 -m src.cli diagnose 008253` 输出不变
- 所有现有测试通过
- `FundAnalyzer` 公开接口不变
