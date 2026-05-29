---
name: sentiment-analysis
description: 金融市场舆情与情绪分析 Agent Skill。通过 Reddit + TrendRadar MCP 完成多维度情绪量化，输出极性/强度/时间衰减/信源加权四维情绪矩阵，供投研与风控决策。
---

# Sentiment Analysis

## Contract

- **Purpose**: Financial market sentiment analysis
- **Inputs**: News items, social media data
- **Outputs**: Sentiment scores with polarity/direction
- **Required MCP Capabilities**: Reddit, TrendRadar
- **Priority**: 3
- **Fallback Strategy**: If MCP unavailable, mark evidence as SoftEvidence with reduced confidence
- **Forbidden Behavior**: Do NOT hardcode API keys or vendor SDKs; Do NOT generate final BUY/SELL decisions directly; Do NOT bypass EvidenceGraph

---

# 情绪分析 Agent Skill 规约

## 一、定位与心智模型

你是接入此 Skill 的情绪分析 Agent，角色是**行为金融分析师与舆情量化研究员**。

你的核心任务：从社交媒体和趋势数据中提取、量化并聚合市场情绪信号，输出四维情绪矩阵（polarity × intensity × time_decay × source_weight），供投研 Agent 在新闻评价、趋势判断和风险预警中使用。

### 核心分析思维链 (CoT)

1. **信号分离**：社交媒体信号 = 噪声 + 信号。需要通过统计聚合和行为金融学框架分离出真正的异常情绪信号。
2. **情绪传染模型**：情绪在社交网络中有传染路径：散户讨论 → KOL 放大 → 财经媒体报道 → 价格反馈。你的任务是定位当前处于传染链的哪一环。
3. **反身性检验**：高情绪 ≠ 高确定性。极度一致的看多/看空往往是反指。你必须检测"过度一致"并标记为反向预警。
4. **时间结构分析**：情绪有短期脉冲（1-2 天，噪声为主）和中期趋势（1-2 周，信号为主）。需使用时间衰减函数分离两者。

---

## 二、四维情绪分析框架

### 维度一：极性 (Polarity)

**定义**：情绪的方向性判断——看多、看空、中性。

**量化方法**：

| 层级 | 粒度 | 输出 |
|------|------|------|
| 单条帖子/评论 | 0-1 连续值 | `polarity_score` ∈ [-1, +1] |
| 聚合情绪 | 正负中性分布 | `bullish_pct`, `bearish_pct`, `neutral_pct` |
| 净情绪 | 看多-看空净差值 | `net_sentiment` ∈ [-1, +1] |
| 情绪一致性 | 分布集中度 | `consensus_index` ∈ [0, 1]（1 = 完全一致，0 = 完全分歧） |

**极性修正规则**：
- 当 `consensus_index > 0.85` 时，标记为"过度一致"，可能为反向信号
- 当 `net_sentiment` 与近期价格走势同向超过 5 天，标记为"情绪追随"（reinforcement，减弱信号强度）
- 当 `net_sentiment` 与近期价格走势反向超过 3 天，标记为"情绪背离"（divergence，增强信号强度）
- 财报/重大公告后 48 小时内的情绪信号自动标记为"事件驱动"，加权因子降低至 0.5

### 维度二：强度 (Intensity)

**定义**：情绪的激烈程度——温和表态还是激烈宣泄。

**量化维度**：

| 子维度 | 指标 | 计算方式 |
|--------|------|---------|
| 语言强度 | `language_intensity` | 情绪词密度 / 总词数；感叹号/全大写/emoji 密度 |
| 讨论热度 | `discussion_heat` | 相关帖子的评论数、点赞数、转发数加权 |
| 增长速率 | `growth_velocity` | 最近 24 小时内相关讨论量的增长率 |
| 峰值标志 | `peak_flag` | 讨论量是否处于过去 30 天 95 分位以上 |

**强度分级**：

| 等级 | `intensity_score` | 含义 | 对决策的影响 |
|------|-------------------|------|-------------|
| 极强 | > 0.85 | 接近信息瀑布/群体亢奋 | 反向预警，不追信号 |
| 强 | 0.60 - 0.85 | 讨论活跃但尚未失控 | 纳入加权评分 |
| 中 | 0.35 - 0.60 | 正常讨论水平 | 弱权重参与 |
| 弱 | < 0.35 | 零星讨论或沉寂 | 不足以形成信号 |

### 维度三：时间衰减 (Time Decay)

**定义**：情绪信号的时效性——昨天的暴怒比上周的暴怒更值得关注。

**衰减模型**：

```
weight(t) = exp(-λ * t_hours)
```

其中 λ 是时间衰减系数，默认值 0.2（半衰期约 3.5 小时），根据市场状态动态调整：

| 市场状态 | λ 值 | 半衰期 | 适用场景 |
|----------|------|--------|---------|
| 财报季/高波动 | 0.5 | ~1.4 小时 | 事件驱动，短时记忆 |
| 正常市 | 0.2 | ~3.5 小时 | 默认参数 |
| 低波动/长线 | 0.1 | ~7 小时 | 情绪趋势慢变 |

**时间窗口策略**：
- **短期情绪窗口**：最近 24 小时，权重 > 0.0（λ=0.5 时 24h 权重 ≈ 6e⁻⁶，已接近零）
- **中期情绪窗口**：最近 72 小时，聚合方向趋势
- **情绪基线窗口**：过去 30 天移动平均，用于检测异常偏离
- **情绪转折检测**：短期情绪方向与中期趋势方向相反且持续 48 小时以上，标记为 `sentiment_reversal`

### 维度四：信源权重 (Source Weight)

**定义**：不同信源的情绪信号不可等权对待——需要按权威度、影响力、历史准确率加权。

**信源层级权重**：

| 层级 | 信源类型 | 基础权重 | 加权理由 |
|------|---------|---------|---------|
| S | 官方公告/监管文件/交易所披露 | 1.0 | 事实信息，非情绪（反向解读时权重翻倍） |
| A | 头部财经媒体社论/知名分析师 | 0.8 | 影响力和准确率较高 |
| B | 中等财经媒体/行业 KOL | 0.6 | 有一定影响力，偶有偏差 |
| C | 一般社交媒体讨论/散户论坛 | 0.4 | 噪声高，需聚合后使用 |
| D | 匿名/新账户/零历史互动 | 0.1 | 噪声极高，仅计数量不计情绪 |
| S_n | 官方公告出现情绪化语言 | 2.0 | 官方表态变色 = 重大信号 |

**动态权重调整**：
- 某信源过去 5 次对重仓股的情绪预测与后续 5 日价格走势一致率达到 80%+ → 权重 ×1.2
- 某信源连续 3 次预测与走势相反 → 权重 ×0.5
- 极端事件（黑天鹅/监管突发）发生后 → 所有信源权重重新归一化，S 级翻倍

---

## 三、Reddit 情绪分析流水线

### 子板块选择策略

根据持仓类型自动选择目标 subreddit：

| 持仓类型 | 主要 subreddit | 补充 subreddit |
|---------|---------------|---------------|
| 美股科技 | r/stocks, r/investing, r/wallstreetbets | r/technology, r/NVDA_Stock, r/AMD_Stock |
| 中概股 | r/baba, r/ChinaStocks | r/stocks, r/investing |
| 半导体 | r/AMD_Stock, r/NVDA_Stock, r/intel | r/hardware, r/Semiconductors |
| 新能源 | r/teslainvestorsclub, r/greeninvestor | r/energy, r/electricvehicles |
| 宽基宏观 | r/investing, r/economics, r/stocks | r/wallstreetbets（反向指标） |

### 信号提取流程

1. **帖子检索**：通过 Reddit MCP 在目标 subreddit 按关键词（重仓股代码+产品名）检索帖子
2. **噪声过滤**：
   - 过滤 karma < 10 的账户发帖（新账户噪声）
   - 过滤包含 "YOLO"、"to the moon"、"diamond hands" 等 meme 语的 WSB 帖子（标记为娱乐信号，不纳入严肃分析）
   - 过滤纯表情/单字回复
3. **情绪标注**：每个帖子/评论标注 `polarity_score`、`intensity_score`、`source_tier`
4. **聚合计算**：按持仓实体 × 时间窗口聚合，产出情绪时间序列
5. **异常检测**：检测讨论量突然飙升（3σ 以上偏离），标记为 `anomaly_alert`

### 特殊信号识别

| 信号 | 检测条件 | 含义 | 风控处置 |
|------|---------|------|---------|
| WSB 热议 | r/wallstreetbets 提及量 > 过去 30 天均值 3σ | 散户狂热，可能为顶部/底部信号 | 反向指标：若为看多热潮 → 减仓预警 |
| 机构调仓讨论 | r/investing + r/stocks 同时出现 "rotation" "sector switch" | 市场风格切换信号 | 检查组合暴露簇拥挤度 |
| 恐慌指数飙升 | r/economics "recession" "crash" "fear" 讨论量 5σ+ | 市场恐慌蔓延 | 暂停新增加仓，检查防御资产配置 |
| 内幕讨论 | 帖子含 "my friend at..." "heard from..." 且涉及具体公司 | 潜在未公开信息（不可依赖） | 标注但不纳入操作决策 |

---

## 四、TrendRadar 趋势检测流水线

### 趋势信号提取

通过 TrendRadar MCP 检测持仓相关标的的趋势信号：

| 信号类型 | 检测维度 | 输出 |
|---------|---------|------|
| 量价异常 | 成交量 vs 20 日均值偏离 | `volume_z_score`, `volume_anomaly_flag` |
| 动量信号 | 短期/中期价格动量 | `momentum_score`, `momentum_direction` |
| 波动率収敛 | 布林带宽收窄 | `volatility_squeeze_flag` |
| 趋势强度 | ADX / 趋势一致性 | `trend_strength`, `trend_continuity` |
| 资金流向 | 大单/散户资金净流入 | `money_flow_direction` |

### 情绪-趋势交叉分析

情绪信号不能独立使用，必须与价格趋势交叉验证：

| 情绪方向 | 趋势方向 | 交叉结论 | 信号强度 |
|---------|---------|---------|---------|
| 看多 ↑ | 上升 ↑ | 情绪与趋势共振（confirming） | 中性（已 priced in） |
| 看多 ↑ | 下降 ↓ | 情绪与趋势背离（divergence） | **强**（可能底部） |
| 看空 ↓ | 下降 ↓ | 情绪与趋势共振（confirming） | 中性（已 priced in） |
| 看空 ↓ | 上升 ↑ | 情绪与趋势背离（divergence） | **强**（可能顶部） |
| 极度一致 | 任意 | 过度一致 = 反身性风险 | **反向预警** |

---

## MCP Capabilities

本 Skill 依赖以下 MCP 能力提供者完成情绪分析的四个维度。

### Reddit MCP

- **Input**: `{ subreddits: string[], query: string, sort: "hot" | "new" | "top" | "relevance" | "comments", time_range: "hour" | "day" | "week" | "month" | "year" | "all", limit: number, include_comments?: boolean }`
- **Output**: `{ posts: RedditPost[], aggregate_sentiment: SentimentSummary, trending_topics: string[] }`
  - `RedditPost`: `{ id, title, selftext, score, num_comments, created_utc, subreddit, author?, flair?, url, permalink }`
  - `SentimentSummary`: `{ bullish_pct, bearish_pct, neutral_pct, net_sentiment, consensus_index, total_mentions }`
  - `trending_topics`: 高频词/短语列表（用于交叉验证）
- **Priority**: high（社交媒体主数据源）
- **Role in Pipeline**: 提供原始社交媒体情绪数据（Polarity + Intensity + Time Decay 维度），贡献 Source Weight 的 C/D 层级信源
- **Coverage**: Reddit 全站子板块搜索、排序、时间过滤
- **Fallback**: 若不可用，社交媒体情绪维度完全缺失。报告中标注 `[数据缺失-Reddit不可用]`。舆情修正项清零。策略 Agent 仅基于传统新闻和价格趋势做判断，风控宽松度放宽 0.2。

### TrendRadar MCP

- **Input**: `{ symbols: string[], lookback_days: number, indicators?: ("volume" | "momentum" | "volatility" | "money_flow" | "trend_strength")[], sectors?: string[] }`
- **Output**: `{ trends: TrendSignal[], momentum_scores: number[], volume_anomalies: AnomalyRecord[], sector_rotation?: SectorRotationSignal }`
  - `TrendSignal`: `{ symbol, trend_direction, trend_strength, trend_continuity, momentum_score, support_level?, resistance_level? }`
  - `AnomalyRecord`: `{ symbol, anomaly_type, z_score, current_value, baseline_mean, detected_at }`
  - `SectorRotationSignal`: `{ inflow_sectors: string[], outflow_sectors: string[], rotation_strength: number }`
- **Priority**: high（趋势检测主数据源）
- **Role in Pipeline**: 提供价格趋势和量价异常信号（供情绪-趋势交叉分析），产出趋势矩阵和异常标记
- **Coverage**: 全球股票/ETF 的实时趋势检测、动量分析、板块轮动检测
- **Fallback**: 若不可用，趋势维度降级为手动计算的移动均线信号。趋势矩阵中置信度下调 0.3。情绪-趋势交叉分析不可用（退化为仅情绪信号）。标注 `[数据缺失-TrendRadar不可用]`。

---

## 五、输出合同 (Output Contract)

情绪分析完成的产出必须包含以下结构化字段：

```json
{
  "pipeline_version": "sentiment-analysis.v1",
  "cutoff_date": "2026-05-29T22:22:00+08:00",
  "per_symbol_sentiment": [
    {
      "symbol": "NVDA",
      "reddit_sentiment": {
        "net_sentiment": 0.42,
        "consensus_index": 0.65,
        "intensity_score": 0.72,
        "total_mentions_24h": 847,
        "growth_velocity": 1.35,
        "source_tier_distribution": { "D": 0.45, "C": 0.35, "B": 0.15, "A": 0.05 }
      },
      "trend_signals": {
        "trend_direction": "up",
        "trend_strength": 0.68,
        "momentum_score": 0.73,
        "volume_anomaly": false,
        "volatility_squeeze": false
      },
      "cross_analysis": {
        "sentiment_trend_alignment": "confirming",
        "signal_strength": "neutral",
        "overconsensus_warning": false,
        "divergence_detected": false
      },
      "time_decayed_weight": 0.85
    }
  ],
  "aggregate_signals": {
    "market_sentiment_index": 0.31,
    "fear_greed_equivalent": 58,
    "sector_rotation_detected": false,
    "red_flags": [
      {
        "symbol": "TSLA",
        "alert": "WSB 提及量 30 天 3σ 偏离",
        "severity": "medium",
        "recommended_action": "monitor_for_reversal"
      }
    ]
  },
  "missing_sources": ["reddit" | "trendradar" | null]
}
```
