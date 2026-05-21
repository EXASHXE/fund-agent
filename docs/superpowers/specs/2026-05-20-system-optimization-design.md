# Fund Agent 系统架构升级设计文档

> 基于 `0520_plan.txt`，2026-05-20

## 设计决策汇总

| 决定 | 方案 | 原因 |
|------|------|------|
| 新闻匹配 | 重写 `_matches_terms` | 统一字符级匹配，移除 `\b`/`isascii` 边界问题 |
| 关键词降级 | 保留默认词兜底 | 纯 CLI 环境需可用 |
| 缓存周期 | 90→14 天 | 提高新闻时效性 |
| 量化指标 | HHI + IR + Alpha + Treynor | 增强 evidence.json 数学比重 |
| 报告校验 | 新建 validator.py | 机械化检查从 Prompt 剥离 |

## 任务一：新闻采集引擎

### 1.1 重写 `_matches_terms`

**当前问题**：混合中英文时 `\b` 和 `isascii()` 判断边界模糊。

**新实现**：将文本和关键词分别按语言分词（中文单字 trigram、英文 word boundary），交集匹配。移除所有 `\b`/`isascii` 特殊分支。

### 1.2 新增数据源

在 `_fetch_market_news_frames` 追加：
- `ak.stock_telegraph_cls()` — 电报全量流
- `ak.stock_info_global_cls(symbol="行业")` — 行业新闻兜底

### 1.3 关键词降级匹配

在 `fetch_fund_news` 增加二次扫描：首次 `search_terms` 全量命中为零时，按优先级降级：
1. 股票名/关键词截取前 2 字重试
2. `_fallback_fund_keywords` 兜底词组

---

## 任务二：内存闭环流转

### 2.1 缓存周期

`keyword_cache.py`: `MAX_CACHE_AGE_DAYS = 90` → `14`

### 2.2 Agent 关键词接口

在 `cli.py` 的 `cmd_analyze` 中，缓存失效时：
1. 尝试调 `request_agent_keywords_inline()` 回调获取实时关键词
2. Agent 不可用 → 降级到 `extract_holding_keywords()` + `_fallback_fund_keywords()`
3. 全程内存操作，不写中间文件、不中断进程

### 2.3 回调签名

```python
def request_agent_keywords_inline(
    holding_codes: List[str],
    fund_profiles: List[Dict]
) -> Optional[Dict[str, List[str]]]:
```

---

## 任务三：量化指标增强

### 3.1 HHI 指数 (`holdings.py`)

```python
def compute_hhi(holdings_df: pd.DataFrame) -> float:
    # HHI = sum((weight_i * 100)^2) for top 10 holdings
```

输出到 `FundAnalyzer.funds[code]["quant_seeds"]["hhi"]`

### 3.2 风险调整指标 (`scorer.py`)

在 `_compute_perf_from_nav` 扩展计算：
- **信息比率 (IR)** = 超额收益均值 / 跟踪误差，需指数基准（沪深300/纳斯达克100）
- **詹森 Alpha** = 实际收益 - [无风险利率 + Beta × (市场收益 - 无风险利率)]
- **特雷诺比率** = (收益 - 无风险利率) / Beta

新增 `_compute_advanced_metrics()` 方法，结果存储在 `funds[code]["quant_seeds"]`

---

## 任务四：后置校验器

### 4.1 新建 `src/output/validator.py`

```python
def post_process_report(raw_markdown: str, analytics_evidence: dict) -> str:
```

两步处理：
1. **止盈止损线校准**：从 evidence 提取年化波动率，计算 `止盈=vol*2.0, 止损=vol*1.5`（上限60%/下限40%），替换报告中占位符或冲突值
2. **合规声明追加**：在报告末尾硬编码追加 6 条标准风险提示

### 4.2 集成点

在 `cli.py` 报告生成最后一步调用 `post_process_report()`。

---

## 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/news/news_fetcher.py` | 重写 | `_matches_terms` + 新增源 + 降级匹配 |
| `src/news/keyword_cache.py` | 修改 | `MAX_CACHE_AGE_DAYS` 90→14 |
| `src/cli.py` | 修改 | Agent inline 回调 + validator 集成 |
| `src/analysis/holdings.py` | 新增 | `compute_hhi()` |
| `src/analysis/scorer.py` | 新增 | `_compute_advanced_metrics()` |
| `src/output/validator.py` | **新建** | 后置校验与合规追加 |
| `tests/` | 新增/修改 | 各模块对应测试 |
