# 新闻相关性双层过滤优化 — 设计文档

> 日期: 2026-05-25 | 状态: 待评审

## 1. 问题背景

当前新闻模块对 008253（华宝致远混合QDII-A，重仓英伟达/美光/博通/台积电等美国半导体股）返回的新闻包含"雷军谈手机涨价"等无关内容。根因是关键词匹配和行业拉取过于宽泛，缺乏深度相关性判断。

## 2. 方案概述

**规则层（Python代码）缩窄抓取口径 + Agent层（Skill执行中）对抓回新闻做持仓相关性判断**。

Pipeline 仍然全量处理抓回的新闻（sentiment/catalyst），但在 `report.evidence.json`
中附加一份结构化的 **新闻相关性判断任务**。Agent 在运行 fund-analyst skill 时，
对每条候选新闻判断是否与其持仓有实质性投资关联，并在 `agent_decisions.json` 的
`news` 段指出真正的关键新闻、调整影响力评级。最终报告依据 Agent 判断结果呈现。

```
fetch (规则层缩窄) → dedup → sentiment → catalyst → evaluate → evidence.json
                                                                    │
                                          Agent (fund-analyst skill) │
                                          读取 evidence.json          │
                                          判断每条新闻与持仓的相关性    │
                                          输出 agent_decisions.json   │
                                          仅关键新闻进入最终报告       │
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

## 4. Layer 2 — Agent 持仓相关性判断

### 4.1 设计理念

不在 Python 代码（pipeline）中直接调用 LLM API 做新闻过滤。
而是将相关性判断任务建模为 Agent 输入上下文的一部分——Agent 在执行
`fund-analyst` skill 时，自然地对每条新闻做持仓相关性评估，
并将真正相关的新闻写入 `agent_decisions.json` 的 `key_news` 中。

这样复用了 Agent 已有的决策上下文（持仓数据、净值走势、行业格局），
无需在代码中注入新的 API 调用。

### 4.2 evidence.json 扩展

在 `report.evidence.json` 中，为每只基金的 `news_evidence` 追加以下字段：

```json
{
  "news_evidence": {
    "existing fields...": "...",
    "relevance_task": {
      "instruction": "逐条判断以下新闻与基金持仓是否有实质性投资关联（非泛泛关联）。仅标记能够影响所持股票基本面、估值或行业前景的新闻为 relevant。",
      "holdings": [
        {"name": "英伟达", "code": "NVDA", "weight_pct": 7.79},
        {"name": "美光科技", "code": "MU", "weight_pct": 4.53}
      ],
      "candidate_news": [
        {
          "id": 1,
          "title": "雷军回应重新发布YU7标准版...",
          "content": "简短摘要",
          "matched_terms": ["AI", "科技"],
          "rule_relevance": 0.35
        }
      ]
    },
    "expected_agent_relevance_output": {
      "relevant_news_ids": [1, 3, 5],
      "per_news_reasons": {
        "2": "小米手机新闻与基金持有的美股半导体无关",
        "4": "YU7汽车发布与基金持仓无交集"
      }
    }
  }
}
```

### 4.3 Agent 输出（agent_decisions.json）

Agent 的 `news.{code}.key_news` 字段已存在，本次确保：

- `key_news` 仅包含 Agent 判断为 **高度相关** 的新闻
- 对无关新闻，Agent 在 `impact` 中降级为 `insufficient_evidence` 或 `neutral`
- `relevance` 字段如实反映持仓覆盖度（`low` if most news irrelevant）
- 增设 `noise_discarded` 字段记录被过滤掉的无关新闻数量

```json
{
  "news": {
    "008253": {
      "summary": "英伟达Q1财报超预期、台积电扩产等关键事件正面推动持仓",
      "impact": "positive",
      "relevance": "high",
      "confidence": 0.85,
      "noise_discarded": 8,
      "watch": ["关注美光科技后续订单指引"],
      "key_news": [
        {
          "title": "英伟达公司 2027财年Q1业绩电话会",
          "reason": "基金第一重仓股(7.79%)，财报超预期直接利好"
        }
      ]
    }
  }
}
```

### 4.4 Agent Skill 指令补充

在 `skills/fund-analyst/SKILL.md` 的新闻证据审核环节补充规则：

- 逐条读出 evidence 中的新闻，对照该基金重仓股清单
- 仅将**直接影响持仓股基本面/行业前景/市场情绪**的新闻视为 `key_news`
- 手机发布、汽车发布、泛消费电子新闻若与持仓无直接产业链关联，主动标记为噪声
- 新闻样本整体质量低时，在 `impact` 和 `confidence` 中体现，不对噪声样本强行打分

## 5. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/news/news_fetcher.py` | **修改** | `_matched_terms()` 词边界匹配、`_fund_industries()` 移除"科技"、`build_news_search_profile()` fallback禁用条件、`fetch_fund_news()` 权重预算分配 |
| `src/news/entity_mapper.py` | **修改** | `_SECTOR_KEYWORD_MAP` 中"科技"→精确关键词 |
| `src/news/pipeline.py` | **修改** | `report.evidence.json` 追加 `relevance_task` 上下文 |
| `src/news/agent_context.py` | **修改** | 新增 `build_news_relevance_task()` 构造 Agent 相关性判断输入 |
| `src/output/report.py` | **修改** | 最终报告渲染从 Agent 的 `key_news` 取相关新闻 |
| `skills/fund-analyst/SKILL.md` | **修改** | 补充新闻相关性判断规则 |
| `tests/` | **新增/修改** | 规则层改动对应的单元测试 |

## 6. 非目标

- 不替换现有 sentiment 和 catalyst 模块（仅在源头减少噪音输入）
- 不改变 AKShare 数据源选择
- 不改变对外 API/CLI 接口

## 7. 验收标准

- 008253 基金经 Agent 判断后，`key_news` 不再包含"雷军谈手机涨价"、"雷军回应YU7"等与持仓无关的新闻
- 持仓股相关的新闻（如"英伟达Q1财报"、"台积电扩产"等）仍被 Agent 标记为 `key_news`
- Agent 对无关新闻主导的基金，会在 `relevance` 降级并在 `noise_discarded` 中体现
- Layer 1 规则改动后，抓取的原始新闻中无关比例显著下降（"AI"不再匹配 "DAILY" 等）
- `report.evidence.json` 包含结构化的 `relevance_task` 供 Agent 使用
- 现有单元测试保持通过
- Agent 在不改变现有 `agent_decisions.json` schema 的前提下完成相关性判断

## 8. 自评审

- [x] 无 TBD/占位符
- [x] 架构与功能描述一致
- [x] 范围聚焦单次实现（无子项目拆分需求）
- [x] 降级策略覆盖
- [x] 验收标准可验证
