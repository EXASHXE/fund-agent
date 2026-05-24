# 新闻相关性双层过滤优化 — 设计文档

> 日期: 2026-05-25 | 状态: 待评审

## 1. 问题背景

当前新闻模块对 008253（华宝致远混合QDII-A，重仓英伟达/美光/博通/台积电等美国半导体股）返回的新闻包含"雷军谈手机涨价"等无关内容。根因是关键词匹配和行业拉取过于宽泛，缺乏深度相关性判断。

## 2. 方案概述

**规则粗筛 + LLM 精筛 双层过滤**：规则层低成本消除明显噪音，LLM 层仅对低置信度候选做深度判断。

架构变更：在现有 pipeline 的 Step 2→Step 3 之间插入 `LLM relevance gate`：

```
fetch → dedup → [NEW: LLM relevance gate] → sentiment → catalyst → evaluate
```

## 3. Layer 1 — 规则层优化

### 3.1 短关键词白名单

- **文件**: `src/news/entity_mapper.py`, `src/news/news_fetcher.py`
- **改动**: 建立 `_EXACT_MATCH_TERMS` 集合，长度<3 的中文或英文关键词必须全词匹配（非子串）
- "AI" 限定为专业金融语境：标题含"AI芯片/AI算力/AI模型/AI数据中心"等才视为匹配
- "科技" 移除出行业关键词白名单，改用 "半导体"、"算力"、"芯片" 等精确词

### 3.2 CJK 词边界匹配

- **文件**: `src/news/news_fetcher.py:_matched_terms()`
- **改动**: 
  - 中文关键词 ≥2 字启用词边界：关键词前后必须有非中文字符或行边界
  - 英文关键词启用 `\b` 词边界 regex
  - 示例：`"AI"` 不匹配 `"DAILY"`, `"RAIL"`, `"BAIC"`；匹配 `"AI 芯片"`, `"AI,"`, `"NVIDIA AI"`

### 3.3 按持仓权重分配搜索预算

- **文件**: `src/news/news_fetcher.py:fetch_fund_news()`
- **改动**: 
  - 重仓股（weight ≥ 5%）：个股新闻接口 `stock_news_em()` + 关键词搜索
  - 中仓股（weight 2-5%）：仅关键词搜索
  - 轻仓股（weight < 2%）：跳过独立搜索，仅依赖市场新闻的关键词命中

### 3.4 行业拉取精准化

- **文件**: `src/news/news_fetcher.py:_fund_industries()`
- **改动**: `_INDUSTRY_THEME_MAP` 中移除 "科技" 映射，行业新闻拉取仅使用确定的申万行业名（"半导体"、"新能源"、"医药"等）

### 3.5 Fallback 关键词禁用条件

- **文件**: `src/news/news_fetcher.py:build_news_search_profile()`
- **改动**: 当 `holding_keywords + agent_keywords ≥ 5` 时，跳过 `fallback_keywords`

## 4. Layer 2 — LLM 相关性门控

### 4.1 触发逻辑

- **新增文件**: `src/news/relevance_gate.py`
- 在 dedup 之后，对每条新闻计算 `compute_relevance()`
  - `relevance ≥ 0.6`：直接通过（规则层高置信）
  - `relevance < 0.3`：直接丢弃（明显无关）
  - `0.3 ≤ relevance < 0.6`：送入 LLM 判断
- LLM 返回 `relevant=true` 则通过，否则丢弃

### 4.2 LLM Prompt 设计

批量模式，每批 5-10 条新闻：

```
请判断以下新闻是否与基金"{fund_name}"的持仓有实质性投资关联。
实质性关联指：新闻内容直接影响该基金所持股票的基本面、估值或市场情绪。

基金重仓股（按权重降序）：
- {stock_name} ({stock_code}, 权重{weight}%)
...

新闻列表：
1. 标题:{title} 内容:{content[:200]}
2. ...

返回严格JSON: [{"id": 1, "relevant": true/false, "reason": "简短理由"}]
```

### 4.3 缓存策略

- 以 `(fund_code, news_title_hash)` 为 key，缓存 LLM 判断结果
- TTL: 7 天（新闻时效内不会重复判断）
- 存储到 `data/cache/news_relevance_cache.json`

### 4.4 降级策略

LLM API 不可用时，降级为 `relevance >= 0.4` 即可通过（保守放行，不阻塞主流程）。

## 5. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/news/relevance_gate.py` | **新增** | LLM 相关性门控核心逻辑 |
| `src/news/news_fetcher.py` | **修改** | `_matched_terms()` 词边界匹配、`_fund_industries()` 移除"科技"、`build_news_search_profile()` fallback禁用条件、`fetch_fund_news()` 权重预算分配 |
| `src/news/entity_mapper.py` | **修改** | `_SECTOR_KEYWORD_MAP` 中"科技"→精确关键词 |
| `src/news/pipeline.py` | **修改** | 在 dedup 后插入 `filter_by_relevance()` 调用 |
| `src/news/config.py` | **可能修改** | 如需新增 relevance LLM 配置参数 |
| `tests/` | **新增** | 相关性过滤的单测和集成测试 |

## 6. 非目标

- 不替换现有 sentiment 和 catalyst 模块（仅在源头减少噪音输入）
- 不改变 AKShare 数据源选择
- 不改变对外 API/CLI 接口

## 7. 验收标准

- 008253 基金返回的新闻中不再包含"雷军谈手机涨价"、"雷军回应YU7"等与持仓无关的新闻
- 持仓股相关的新闻（如"英伟达Q1财报"、"台积电扩产"等）正常保留
- 单次报告生成的 LLM 调用量 ≤30 次（6 只基金）
- LLM 不可用时系统可正常降级运行，不报错阻塞
- 现有单元测试保持通过

## 8. 自评审

- [x] 无 TBD/占位符
- [x] 架构与功能描述一致
- [x] 范围聚焦单次实现（无子项目拆分需求）
- [x] 降级策略覆盖
- [x] 验收标准可验证
