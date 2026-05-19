# 基金分析系统增强设计

> 目标：标准化输入、模块化重构、新增持仓分析与新闻推荐功能。

---

## 变更概览

| 变更项 | 当前状态 | 目标状态 |
|--------|---------|---------|
| 持仓输入 | `fund-info.txt` 自由文本 → `seed_fund_info.py` 正则解析 | `fund-portfolio.yaml` → `config/loader.py` Pydantic 校验 |
| 代码结构 | `src/analyze.py` 984行单体 + `src/seed_fund_info.py` | 按职责拆分为 `config/` `data/` `analysis/` `news/` `recommend/` `output/` |
| 持仓分析 | 无 | 新增：收益计算、趋势分析、定投明细、组合汇总 |
| 新闻资讯 | 无 | 新增：AKShare采集 → SnowNLP情绪 → 相关性 → agent 自主研判 |
| 基金推荐 | 无 | 新增：新闻驱动 + 因子筛选 + 相关性过滤 |

---

## 一、模块架构

```
src/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── schema.py          # Pydantic 模型：PortfolioConfig、FundHolding、DCAStrategy 等
│   ├── loader.py          # YAML 加载 + 校验 + 默认值填充
│   └── defaults.py        # 策略默认参数（与 SKILL.md 保持一致）
├── data/
│   ├── __init__.py
│   ├── fetcher.py         # AKShare 统一封装（复用现有 fetch_* 函数逻辑）
│   ├── news_fetcher.py    # AKShare 新闻接口封装
│   └── cache.py           # 内存缓存，避免同一次运行中重复拉取
├── analysis/
│   ├── __init__.py
│   ├── scorer.py          # 三层评分引擎（从 analyze.py 提取 FundAnalyzer）
│   ├── correlation.py     # Pearson 相关性矩阵
│   ├── stress.py          # 情景压力测试
│   └── holdings.py        # 【新增】持仓分析：收益/趋势/定投/组合汇总
├── news/
│   ├── __init__.py
│   ├── sentiment.py       # SnowNLP 情绪分析 + 关键词提取
│   ├── agent_context.py   # agent 判断上下文（新闻、评分、推荐证据包）
│   └── correlate.py       # 新闻情绪与净值变化的相关性分析
├── recommend/
│   ├── __init__.py
│   └── engine.py          # 新闻驱动 + 因子筛选的基金推荐引擎
├── output/
│   ├── __init__.py
│   ├── report.py          # Markdown 报告生成（提取自 analyze.py generate_report）
│   └── templates.py       # 报告模板片段管理
├── db/                    # 现有模块，保持不变
│   ├── __init__.py
│   ├── models.py
│   ├── database.py
│   └── storage.py
└── cli.py                 # 统一 CLI 入口

废弃文件：
  src/seed_fund_info.py    → 功能迁移至 config/loader.py
  src/analyze.py           → 功能迁移至各子模块，保留为薄 wrapper
```

### 模块依赖关系

```
config ──→ data ──→ analysis ──→ output
                │
                ├──→ news ──→ recommend ──→ output
                │
                └──→ db
```

各模块之间通过明确定义的函数签名通信，不直接访问对方的内部状态。

---

## 二、YAML 配置 Schema

### 2.1 完整结构

```yaml
# fund-portfolio.yaml

# === 用户画像 ===
profile:
  risk_tolerance: moderate       # conservative | moderate | aggressive
  investment_horizon: 3-5年
  target_return: 0.10           # 年化目标收益(小数)
  max_drawdown_tolerance: 0.20  # 最大可承受回撤(小数)

# === 持仓基金 ===
holdings:
  - code: "008253"
    name: 华宝致远混合(QDII)A
    type: qdii                  # domestic | qdii | etf | index
    currency: CNY
    purchases:
      - date: "2025-12-08"
        amount: 2500
    dca:
      enabled: true
      frequency: weekly         # daily | weekly | biweekly | monthly
      amount: 100
      day_of_week: wed
      start_date: "2025-12-08"

# === 策略参数覆写（可选）===
strategy:
  scoring:
    macro_weight: 0.20
    meso_weight: 0.30
    micro_weight: 0.50
  stop_profit_loss:
    profit_multiplier: 2.0
    loss_multiplier: 1.5
  rebalance:
    max_single_position: 0.30
    correlation_alert: 0.75

# === 自选池 ===
watchlist: []
```

### 2.2 Pydantic Schema 定义

```python
# config/schema.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import date

class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"

class FundType(str, Enum):
    DOMESTIC = "domestic"
    QDII = "qdii"
    ETF = "etf"
    INDEX = "index"

class DCAFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"

class DayOfWeek(str, Enum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"

class Purchase(BaseModel):
    date: date
    amount: float = Field(gt=0)
    nav: Optional[float] = None  # null 时自动从 AKShare 获取

class DCAStrategy(BaseModel):
    enabled: bool = False
    frequency: DCAFrequency = DCAFrequency.WEEKLY
    amount: float = Field(gt=0)
    day_of_week: Optional[DayOfWeek] = None
    start_date: Optional[date] = None

class FundHolding(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str = ""
    type: FundType = FundType.DOMESTIC
    currency: str = "CNY"
    purchases: list[Purchase] = []
    dca: Optional[DCAStrategy] = None

class ScoringParams(BaseModel):
    macro_weight: float = Field(default=0.20, ge=0, le=1)
    meso_weight: float = Field(default=0.30, ge=0, le=1)
    micro_weight: float = Field(default=0.50, ge=0, le=1)

class StopProfitLossParams(BaseModel):
    profit_multiplier: float = Field(default=2.0, gt=0)
    loss_multiplier: float = Field(default=1.5, gt=0)

class RebalanceParams(BaseModel):
    max_single_position: float = Field(default=0.30, ge=0, le=1)
    correlation_alert: float = Field(default=0.75, ge=0, le=1)

class StrategyParams(BaseModel):
    scoring: ScoringParams = ScoringParams()
    stop_profit_loss: StopProfitLossParams = StopProfitLossParams()
    rebalance: RebalanceParams = RebalanceParams()

class UserProfile(BaseModel):
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_horizon: str = "3-5年"
    target_return: float = Field(default=0.10, gt=0)
    max_drawdown_tolerance: float = Field(default=0.20, gt=0)

class PortfolioConfig(BaseModel):
    profile: UserProfile = UserProfile()
    holdings: list[FundHolding]
    strategy: StrategyParams = StrategyParams()
    watchlist: list[str] = []
```

### 2.3 默认值填充策略

配置中缺失的字段按以下优先级填充：

1. YAML 中显式指定的值
2. `strategy` 区块中覆写的值
3. `config/defaults.py` 中的全局默认值（与 `skills/fund-analyst/SKILL.md` 保持一致）
4. `FundHolding.name` 缺失时，自动通过 AKShare 查询填充

---

## 三、CLI 入口设计

```bash
# 从 YAML 导入持仓到数据库
python -m src.cli import -c fund-portfolio.yaml

# 完整分析流程
python -m src.cli analyze -c fund-portfolio.yaml -o report.md

# 仅拉取数据（不分析）
python -m src.cli fetch -c fund-portfolio.yaml

# 对已有持仓做分析（复用数据库数据）
python -m src.cli score -o report.md

# 新闻采集与分析
python -m src.cli news -c fund-portfolio.yaml --days 7

# 基金推荐
python -m src.cli recommend -c fund-portfolio.yaml --top 5

# 单基金快速诊断
python -m src.cli diagnose 008253
```

子命令映射：
- `import` → `config/loader.py` 读取 YAML → `db/storage.py` 写入
- `analyze` → `import` + `data/` 采集 + `analysis/` 评分 + `news/` 分析 + `recommend/` 推荐 + `output/` 生成报告
- `fetch` → `config/loader.py` + `data/` 单次采集
- `score` → `analysis/` 评分 + `output/` 生成报告
- `news` → `news/` 全流程
- `recommend` → `recommend/` 全流程
- `diagnose` → `data/` + `analysis/` 单基金评分

---

## 四、持仓分析模块 (`analysis/holdings.py`)

### 4.1 输入输出

**输入**：数据库中某基金的全部买入记录（FundHolding）+ 最新净值序列（FundNAV）

**输出**：结构化分析结果

### 4.2 单基金分析项

| 分析项 | 计算方式 | 输出格式 |
|--------|---------|---------|
| 累计投入 | Σ(所有买入金额 + DCA 累计金额) | ¥X,XXX |
| 当前份额 | Σ(每次买入金额÷买入净值) + Σ(DCA 金额÷定投日净值) | X.XX 份 |
| 当前市值 | 当前份额 × 最新单位净值 | ¥X,XXX |
| 累计收益 | 当前市值 - 累计投入 | ±¥X,XXX |
| 累计收益率 | 累计收益 / 累计投入 × 100% | ±XX.XX% |
| 年化收益率 | XIRR 算法（考虑每笔现金流时间） | ±XX.XX% |
| 净值走势 | 买入至今的净值序列 | ASCII 折线图 |
| 价值趋势 | 每日 (份额×净值) 序列 | ASCII 折线图 |
| 定投明细表 | 每期定投的日期/金额/净值/份额/累计/该期收益 | 表格 |
| 定投成本均线 | 定投总投入 / 定投总份额 vs 当前净值 | ¥X.XX vs ¥X.XX |

### 4.3 组合汇总表

| 列 | 说明 |
|----|------|
| 基金代码 | 六位代码 |
| 基金名称 | 完整名称 |
| 持有市值 | 当前份额 × 最新净值 |
| 市值占比 | 单只市值 / 组合总市值 |
| 累计收益率 | 见上方公式 |
| 贡献度 | (单只收益 / 组合总收益) × 组合收益率 |
| 定投状态 | 启用中 / 暂停 / 未设置 |

### 4.4 XIRR 实现要点

```python
def calc_xirr(cashflows: list[tuple[date, float]], current_value: float, current_date: date) -> float:
    """
    cashflows: [(日期, 现金流)]  负值为投入，正值为赎回
    current_value: 当前持仓市值（作为最后一笔正现金流）
    
    使用牛顿迭代法求解 IRR，再年化。
    若迭代不收敛或现金流不足，降级为简单收益率。
    """
```

---

## 五、新闻模块 (`news/`)

### 5.1 数据流

```
AKShare stock_news_em / fund_news 接口
        │
        ▼
news_fetcher.py: 获取近 N 天基金相关新闻
   ├─ 关键词构造：基金简称核心词 + 重仓行业名 + 基金经理名
   ├─ 按基金代码/名称过滤
   ├─ 去重（标题相似度 > 0.8 视为重复）
   └─ 时间排序输出
        │
        ▼
sentiment.py: SnowNLP 逐条情绪打分
   ├─ SnowNLP(sentence).sentiments → 0-1 得分
   ├─ 分类：>0.6 正面 | 0.4-0.6 中性 | <0.4 负面
   ├─ 按日聚合：正面率、负面率、情绪均值、新闻条数
   └─ jieba 分词提取 Top-10 高频关键词
        │
        ▼
correlate.py: 新闻情绪 vs 净值变化 相关性分析
   ├─ 时间对齐（QDII 净值延迟自动补偿）
   ├─ Spearman 秩相关系数
   ├─ 领先分析：T日情绪 vs T+1/3/5 日净值变化
   └─ 输出："新闻情绪对 T+1 净值的解释力 r=0.XX, p=0.XX"
        │
        ▼
agent_context.py: agent 综合研判上下文
   ├─ 输入：情绪分数序列 + Top关键词 + 净值走势摘要 + 基金基础信息
   ├─ Prompt 模板注入 SKILL.md 分析约束
   ├─ 要求结构化 JSON 输出：
   │   {summary, sentiment_trend, key_events, short_term_view,
   │    mid_term_view, risk_factors, confidence}
   └─ 输出整合到最终报告
```

### 5.2 AKShare 新闻接口选择

优先级从高到低：

| 接口 | 覆盖范围 | 备注 |
|------|---------|------|
| `ak.stock_news_em(symbol="基金代码")` | 东方财富个股新闻 | 直接按代码搜，最精准 |
| `ak.stock_news_em(symbol="基金简称关键词")` | 东方财富主题新闻 | 扩大搜索面，需去噪 |
| `ak.fund_announcement_em()` | 基金公告 | 分红/限购/经理变更等 |

容错策略：单个接口失败不中断，合并多个来源的去重结果。

### 5.3 情绪分析实现

```python
# news/sentiment.py

from snownlp import SnowNLP
import jieba
import jieba.analyse

class NewsSentiment:
    def analyze(self, texts: list[str]) -> list[dict]:
        results = []
        for text in texts:
            s = SnowNLP(text)
            score = s.sentiments  # 0-1, >0.5偏正面
            label = "positive" if score > 0.6 else ("negative" if score < 0.4 else "neutral")
            keywords = jieba.analyse.extract_tags(text, topK=10)
            results.append({"score": score, "label": label, "keywords": keywords})
        return results

    def daily_aggregate(self, daily_news: dict[date, list[dict]]) -> list[dict]:
        """按日聚合情绪指标"""
        ...
```

### 5.4 相关性分析实现

```python
# news/correlate.py

from scipy.stats import spearmanr

def news_nav_correlation(
    sentiment_series: list[tuple[date, float]],   # (日期, 当日情绪均值)
    nav_series: list[tuple[date, float]],          # (日期, 当日净值变化%)
    lag_days: list[int] = [0, 1, 3, 5]
) -> dict:
    """
    计算新闻情绪与净值变化在不同领先/滞后窗口下的 Spearman 相关。
    返回 {lag_days: (r, p_value)}。
    """
```

### 5.5 Agent 判断上下文设计

```python
# news/agent_context.py

def build_news_judgment_context(...): ...
def build_score_judgment_context(...): ...
def build_recommendation_judgment_context(...): ...
```

Python 不调用模型 API；接入 skill 的 agent 读取上下文后直接完成综合研判。

---

## 六、推荐模块 (`recommend/engine.py`)

### 6.1 推荐流程

```
新闻热点行业识别
   ├─ 聚合所有基金相关新闻的关键词
   └─ 按行业标签归类，计算各行业热度得分
        │
        ▼
全市场基金筛选 (AKShare fund_ranking_em)
   ├─ 近1月/3月/6月收益 Top 20%
   ├─ 基金规模 > 1亿
   └─ 申购状态开放
        │
        ▼
相关性过滤
   ├─ 逐一计算推荐候选与现有持仓的 Pearson r
   ├─ 排除 r > strategy.rebalance.correlation_alert 的高相关基金
   └─ 保留低相关基金作为备选
        │
        ▼
综合排序
   ├─ 因子权重：收益动量(40%) + 行业新闻热度(30%) + 与持仓低相关(30%)
   └─ 输出 Top-N
        │
        ▼
agent 基于候选证据生成最终推荐理由
   └─ 每个推荐基金附带 2-3 句自然语言推荐理由
```

### 6.2 输出格式

```markdown
## 新闻驱动基金推荐

### 近期热点行业
| 行业 | 新闻热度 | 情绪偏向 |
|------|---------|---------|
| 半导体 | ★★★★★ | 正面 |
| 新能源 | ★★★★☆ | 中性偏正 |

### 推荐基金 Top-5

| 排名 | 代码 | 名称 | 类型 | 综合得分 | 与持仓平均相关 | 推荐理由 |
|------|------|------|------|---------|---------------|---------|
| 1 | XXXXXX | XXX | 混合型 | 85 | 0.32 | ... |
| ... | ... | ... | ... | ... | ... | ... |
```

---

## 七、报告输出变更

### 7.1 章节顺序（新）

```
1. 持仓总览              【新增】组合汇总表 + 总收益
2. 单基金诊断 (×N)
   2.1 数据完整度
   2.2 评分明细
   2.3 操作建议
   2.4 持仓趋势分析        【新增】净值走势 + 定投明细 + 收益图表
3. 组合分析
   3.1 相关性矩阵
   3.2 情景压力测试
4. 新闻资讯分析           【新增】
   4.1 近期相关新闻摘要
   4.2 情绪趋势分析
   4.3 新闻-净值相关性
   4.4 agent 趋势判断
5. 推荐基金               【新增】
   5.1 新闻热点行业
   5.2 推荐列表
6. 再平衡方案
7. 风险提示               【保留，固定内容】
```

### 7.2 持仓总览模板

```markdown
## 一、持仓总览

> 评估日期：YYYY-MM-DD

| 基金代码 | 基金名称 | 持有市值(¥) | 占比 | 累计收益(¥) | 累计收益率 | 年化收益率 | 定投状态 |
|----------|---------|-----------|------|-----------|----------|-----------|---------|
| 008253 | 华宝致远混合 | 2,XXX | 35% | +XXX | +X.X% | +X.X% | 启用中 |
| ... | ... | ... | ... | ... | ... | ... | ... |

**组合汇总**
- 总投入：¥XX,XXX
- 总市值：¥XX,XXX
- 总收益：±¥X,XXX
- 总收益率：±XX.XX%
- 持有基金数：X 只
```

### 7.3 持仓趋势分析模板（每只基金）

```markdown
### 2.X 持仓趋势分析

**收益概览**
- 累计投入：¥X,XXX | 当前市值：¥X,XXX | 浮动盈亏：±¥XXX (±XX%)
- 年化收益率：±XX% (XIRR)

**净值走势**（YYYY-MM-DD ~ YYYY-MM-DD）
```
 ¥1.50 ┤                    ╭─╮
 ¥1.40 ┤    ╭──╮    ╭──────╯  ╰──
 ¥1.30 ┤  ╭╯  ╰──╮╭╯
 ¥1.20 ┤──╯      ╰╯
```
当前净值：¥X.XXX | 定投成本均线：¥X.XXX

**定投明细**
| 期数 | 日期 | 金额 | 买入净值 | 获得份额 | 累计份额 | 该期收益率 |
|------|------|------|---------|---------|---------|----------|
| 1 | 2025-12-15 | ¥100 | 1.234 | 81.04 | 81.04 | +2.1% |
| 2 | 2025-12-22 | ¥100 | 1.256 | 79.62 | 160.66 | -0.3% |
| ... | ... | ... | ... | ... | ... | ... |
```

---

## 八、依赖变更

### requirements.txt 新增

```
pyyaml>=6.0
pydantic>=2.0
snownlp>=0.12.3
jieba>=0.42.1
scipy>=1.10.0          # Spearman 相关系数
```

### requirements.txt 终版

```
sqlalchemy>=2.0
akshare>=1.14.0
pyyaml>=6.0
pydantic>=2.0
snownlp>=0.12.3
jieba>=0.42.1
scipy>=1.10.0
```

---

## 九、迁移计划

| Phase | 内容 | 产出 | 顺序依赖 |
|-------|------|------|---------|
| 1 | 创建 `config/schema.py` + `loader.py` + `defaults.py` | YAML 加载校验可用 | 无 |
| 2 | 迁移 `analyze.py` → `data/` + `analysis/` + `output/` 子模块 | 现有功能无退化 | Phase 1 |
| 3 | 新增 `analysis/holdings.py` 持仓分析 | 收益/趋势/定投分析 | Phase 2 |
| 4 | 新增 `news/` 模块（fetcher + sentiment + correlate + agent_context） | 新闻采集与分析 | Phase 2 |
| 5 | 新增 `recommend/engine.py` | 基金推荐 | Phase 4 |
| 6 | 集成 `cli.py` 入口 + 报告生成全链路打通 | 整合 | Phase 3+4+5 |
| 7 | 删除 `seed_fund_info.py`，清理 `analyze.py` | 代码清理 | Phase 6 |
| 8 | 更新 `skills/fund-analyst/` 文档、更新 `requirements.txt` | 文档同步 | Phase 6 |

当前实现补充：`analyze` 会同时生成 `report.md` 与 `report.md.context.json`，Markdown 负责阅读，JSON context 负责 agent 继续推理和 UI/ViewModel 消费。

### Phase 2 拆分细节

`analyze.py` (984行) → 拆分为：

| 原位置 | 目标模块 | 内容 |
|--------|---------|------|
| `fetch_fund_*` 5个函数 | `data/fetcher.py` | AKShare 数据采集 |
| `FundAnalyzer` 类 + `_score_*` | `analysis/scorer.py` | 评分引擎 |
| `compute_correlations()` | `analysis/correlation.py` | 相关性矩阵 |
| `stress_test()` | `analysis/stress.py` | 压力测试 |
| `generate_report()` | `output/report.py` | 报告生成 |
| `main()` | `cli.py` | CLI 入口 |

---

## 十、风险与注意事项

1. **SnowNLP 中文情绪模型精度有限**，金融领域文本可能有偏差。需要标注"情绪分析结果仅供参考"
2. **模型推理不在脚本内通过外部 API 完成**。脚本只生成证据包；接入 skill 的 agent 负责最终判断
3. **AKShare 新闻接口稳定性**，需做好超时重试 + 降级策略
4. **XIRR 计算**依赖至少 2 笔现金流，单笔买入降级为简单收益率
5. **全市场基金推荐**可能返回大量数据，需要分页 + 缓存策略
6. 所有新增功能遵循现有容错原则：子模块失败不中断主流程

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-06 | v1.0 | 初始设计：YAML 标准化输入、模块化重构、持仓分析、新闻推荐 |
