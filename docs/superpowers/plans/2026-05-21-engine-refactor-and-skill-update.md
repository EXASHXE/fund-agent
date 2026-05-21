# 公募基金投研系统底层核心引擎大重构 + SKILL 更新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将系统从"代码硬编码定性 + LLM 报表填空器"升级为"纯量化连续特征计算层 + Agent 自主决策层"的工业级闭环，并同步更新 fund-analyst SKILL.md

**Architecture:** 三阶段递进 — Phase 0 (SKILL.md 更新) → Phase 1 (前置沙盒验证) → Phase 2 (4个核心模块原子化重构) → Phase 3 (全链路回归测试)

**Tech Stack:** Python 3, AKShare, NumPy, SciPy, SQLAlchemy, pytest

---

## Phase 0: SKILL.md 更新

### Task 0: 更新 fund-analyst SKILL.md

**Files:**
- Modify: `skills/fund-analyst/SKILL.md`

- [ ] **Step 1: 备份当前 SKILL.md**

```bash
cp skills/fund-analyst/SKILL.md skills/fund-analyst/SKILL.md.bak
```

- [ ] **Step 2: 写入新版 SKILL.md**

内容来自用户提供的完整新版规约（填入被截断的 CIO 自检清单末尾内容）：

写入完整文件内容。新版核心变化：
- 新增 "全自主归因" 原则——废除公式化填空，Agent 对分析文本/仓位调整/触发条件拥有绝对独立思考权
- 新增 Sortino MAR (SORTINO_MAR) 和 NEWS_LAMBDA 参数化适配说明
- 重构为四部分：心智模型、数据契约、插槽规范、CIO 自检
- 自检清单新增 grep 零残留为第一条

- [ ] **Step 3: 验证 SKILL.md 格式正确**

```bash
wc -l skills/fund-analyst/SKILL.md
head -5 skills/fund-analyst/SKILL.md
```

---

## Phase 1: 前置环境校验与沙盒验证

### Task 1: 创建校验脚本 `verify_quant_framework.py`

**Files:**
- Create: `verify_quant_framework.py`

- [ ] **Step 1: 编写 Sortino 比率验证函数**

```python
"""验证量化重构框架——Sortino 比率 & 舆情时间衰减"""

import numpy as np

def test_sortino_calculation():
    """验证 Sortino 比率计算正确性"""
    # 模拟 252 个交易日收益率
    np.random.seed(42)
    daily_returns = np.random.normal(0.0005, 0.015, 252)
    
    # 参数
    MAR_annual = 0.025  # 2.5% 无风险利率
    MAR_daily = (1 + MAR_annual) ** (1/252) - 1
    
    # 计算下行偏差
    downside_returns = np.minimum(daily_returns - MAR_daily, 0)
    downside_deviation = np.sqrt(np.mean(downside_returns ** 2))
    downside_deviation_annual = downside_deviation * np.sqrt(252)
    
    # 计算 Sortino
    excess_returns = daily_returns - MAR_daily
    mean_excess_daily = np.mean(excess_returns)
    sortino = mean_excess_daily * 252 / downside_deviation_annual if downside_deviation_annual > 0 else 0.0
    
    print(f"日均超额收益: {mean_excess_daily:.8f}")
    print(f"年化下行偏差: {downside_deviation_annual:.6f}")
    print(f"Sortino Ratio: {sortino:.4f}")
    
    assert isinstance(sortino, float), "Sortino must be float"
    assert sortino > -10 and sortino < 10, f"Sortino {sortino} out of reasonable range"
    print("✓ Sortino ratio test PASSED")
    return sortino


def test_sentiment_decay():
    """验证舆情时间衰减加权算法"""
    # 模拟 7 天情绪数据
    daily_sentiments = [
        {"date": "2026-05-14", "sentiment_mean": 0.33},
        {"date": "2026-05-15", "sentiment_mean": 0.43},
        {"date": "2026-05-16", "sentiment_mean": 0.52},
        {"date": "2026-05-17", "sentiment_mean": 0.24},
        {"date": "2026-05-18", "sentiment_mean": 0.81},
        {"date": "2026-05-19", "sentiment_mean": 0.41},
        {"date": "2026-05-20", "sentiment_mean": 0.54},
    ]
    
    LAMBDA = 0.200  # 3.5 天半衰期
    
    total_weight = 0.0
    weighted_sum = 0.0
    current_idx = len(daily_sentiments) - 1
    
    for idx, agg in enumerate(daily_sentiments):
        delta_t = current_idx - idx
        decay_weight = np.exp(-LAMBDA * delta_t)
        raw = agg["sentiment_mean"]
        weighted_sum += raw * decay_weight
        total_weight += decay_weight
    
    decayed = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.5
    
    # 验证：衰减后的值应该介于 min 和 max 之间，且更接近最近几天
    raw_values = [d["sentiment_mean"] for d in daily_sentiments]
    print(f"原始情绪值: {raw_values}")
    print(f"指数衰减聚合 (λ={LAMBDA}): {decayed}")
    print(f"简单均值: {np.mean(raw_values):.4f}")
    
    assert min(raw_values) <= decayed <= max(raw_values), "Decayed value out of range"
    # 衰减值应偏向最近的数值（0.54, 0.41, 0.81）而非早期的（0.33, 0.43）
    recent_avg = np.mean(raw_values[-3:])  # 0.587
    early_avg = np.mean(raw_values[:3])    # 0.427
    assert abs(decayed - recent_avg) < abs(decayed - early_avg), \
        f"Decayed {decayed} should be closer to recent {recent_avg} than early {early_avg}"
    print("✓ Sentiment decay test PASSED")
    return decayed


if __name__ == "__main__":
    s = test_sortino_calculation()
    d = test_sentiment_decay()
    print(f"\n{'='*50}")
    print(f"Sortino Ratio: {s:.4f}")
    print(f"Decayed Sentiment: {d:.4f}")
    print(f"All verifications PASSED ✓")
```

- [ ] **Step 2: 运行校验脚本**

```bash
python3 verify_quant_framework.py
```

Expected: PASS with floating point output.

---

## Phase 2: 原子化落地编程

### Task 2: 修改 `src/config/defaults.py` —— 注入全局量化参数

**Files:**
- Modify: `src/config/defaults.py`

- [ ] **Step 1: 添加 QUANT_CONFIG 全局配置树**

在文件末尾追加：

```python
# === 量化引擎全局可调参数 ===
# 这些参数支持从外部端口 / YAML 动态加载改写
QUANT_CONFIG = {
    # 索提诺比率最低可接受收益率（年化）
    # 用于动态调节下行风险特征的考核阈值
    "SORTINO_MAR": 0.025,  # 2.5% 无风险利率

    # 舆情时间指数衰减系数 λ
    # 控制新闻时效性的半衰期——值越大，旧新闻衰减越快
    # 0.200 → 半衰期约 3.5 天 (ln(2)/λ)
    # 高波动季调高至 0.3-0.5；长主线牛市调低至 0.1
    "NEWS_LAMBDA": 0.200,
}

# 风险收益率字典（底层引擎自适应）
RISK_FREE_RATE = {
    "CNY": 0.025,   # 中国 1 年期国债收益率近似
    "USD": 0.045,   # 美国联邦基金利率区间中值
}
```

- [ ] **Step 2: 验证文件语法**

```bash
python3 -c "from src.config.defaults import QUANT_CONFIG, RISK_FREE_RATE; print(QUANT_CONFIG); print(RISK_FREE_RATE)"
```

Expected: 两个 dict 正确打印。

---

### Task 3: 重构 `src/analysis/scorer.py` —— 三层解耦评分 + Sortino 比率

**Files:**
- Modify: `src/analysis/scorer.py`

This is the largest change. Key objectives:
1. Delete hardcoded qualitative text from `_score_macro` / `_score_meso` / `_score_micro`
2. Implement continuous Sortino ratio computation
3. Restructure output to include `scoring_matrix.quant_baseline` / `agent_overlay` / `final_score`

- [ ] **Step 1: 在 scorer.py 顶部添加 import 和 Sortino 计算函数**

```python
import numpy as np
from src.config.defaults import QUANT_CONFIG, RISK_FREE_RATE
```

在 `_compute_advanced_metrics` 之前添加：

```python
def _compute_sortino_ratio(daily_returns: list, mar_annual: float = None) -> float:
    """计算索提诺比率（Sortino Ratio）
    
    Sortino = (Mean(R_i - MAR_daily) * 252) / DownsideDeviation_annual
    
    其中 DownsideDeviation = sqrt(mean(min(0, R_i - MAR_daily)^2)) * sqrt(252)
    """
    if not daily_returns or len(daily_returns) < 20:
        return 0.0
    
    if mar_annual is None:
        mar_annual = QUANT_CONFIG.get("SORTINO_MAR", 0.025)
    
    returns = np.array(daily_returns, dtype=float)
    mar_daily = (1 + mar_annual) ** (1/252) - 1
    
    # 下行偏差（仅计入低于 MAR 的波动）
    downside = np.minimum(returns - mar_daily, 0)
    downside_deviation_daily = np.sqrt(np.mean(downside ** 2))
    downside_deviation_annual = downside_deviation_daily * np.sqrt(252)
    
    if downside_deviation_annual == 0:
        return 0.0
    
    mean_excess_daily = np.mean(returns - mar_daily)
    sortino = mean_excess_daily * 252 / downside_deviation_annual
    
    return round(float(sortino), 4)
```

- [ ] **Step 2: 重构 `_score_macro` —— 删除硬编码文本，保留纯数字打分**

```python
def _score_macro(self, code: str) -> Tuple[int, Dict, str]:
    """宏观维度量化打分（纯数字基准，满分 20）
    
    不再输出硬编码的中文定性文本。所有依据由 agent 从 feature_matrix 中提取。
    """
    fund = self.funds.get(code, {})
    ft = fund.get("basic", {})
    fund_type = ft.get("fund_type", "domestic") if ft else "domestic"
    fund_name = ft.get("fund_name", "") if ft else ""
    completeness = fund.get("completeness", "C")
    
    details = {}
    
    # ---- 周期适配 (0-8 分) ----
    # 基于基金类型和风格做纯量化基准
    if "QDII" in str(fund_type).upper() or fund_type == "qdii":
        cycle_score = 4  # QDII 海外敞口基准居中
    elif fund_type in ("混合", "灵活"):
        cycle_score = 5  # 灵活配置在缓复苏期有调仓优势
    elif fund_type in ("指数", "ETF", "etf", "index"):
        cycle_score = 4  # 被动指数受板块轮动影响
    else:
        cycle_score = 4  # 默认中性
    
    # ---- 利率/流动性 (0-6 分) ----
    if "QDII" in str(fund_type).upper() or fund_type == "qdii":
        liquidity_score = 5  # 美联储降息周期流动性偏松
    else:
        liquidity_score = 5  # 国内货币政策适度宽松
    
    # ---- 大盘估值 (0-6 分) ----
    if "纳斯达克" in fund_name or "科技" in fund_name:
        valuation_score = 2  # PE 处于历史高位
    elif "新兴市场" in fund_name:
        valuation_score = 5  # PE 处于合理分位
    else:
        valuation_score = 4  # 中性
    
    macro_total = min(20, cycle_score + liquidity_score + valuation_score)
    return macro_total, {}, ""
```

- [ ] **Step 3: 重构 `_score_meso` —— 删除硬编码文本，仅保留数字分**

```python
def _score_meso(self, code: str, completeness: str) -> Tuple[Optional[int], Dict, str]:
    """中观维度量化打分（纯数字基准，满分 30）
    
    若数据完整度不足（C/D），返回 None。
    """
    if completeness in ("C", "D"):
        return None, {}, ""
    
    fund = self.funds.get(code, {})
    ft = fund.get("basic", {})
    fund_name = ft.get("fund_name", "") if ft else ""
    fund_type = ft.get("fund_type", "domestic") if ft else "domestic"
    
    # ---- 行业景气度 (0-8 分) ----
    if "新兴市场" in fund_name:
        prosperity = 7
    elif "纳斯达克" in fund_name or "科技" in fund_name:
        prosperity = 4
    elif "石油" in fund_name or "能源" in fund_name:
        prosperity = 5
    elif "新能源" in fund_name or "电池" in fund_name:
        prosperity = 3
    elif fund_type in ("混合", "灵活"):
        prosperity = 5
    else:
        prosperity = 5
    
    # ---- 估值安全边际 (0-8 分) ----
    if "新兴市场" in fund_name:
        pe_score = 6
    elif "纳斯达克" in fund_name or "科技" in fund_name:
        pe_score = 2
    elif "石油" in fund_name or "能源" in fund_name:
        pe_score = 4
    elif "新能源" in fund_name or "电池" in fund_name:
        pe_score = 3
    elif fund_type in ("混合", "灵活"):
        pe_score = 5
    else:
        pe_score = 4
    
    # ---- 政策支持 (0-7 分) ----
    if "新兴市场" in fund_name or "新能源" in fund_name or "电池" in fund_name:
        policy = 5
    elif "纳斯达克" in fund_name or "科技" in fund_name:
        policy = 4
    else:
        policy = 3
    
    # ---- 行业轮动 (0-7 分) ----
    if "新兴市场" in fund_name or fund_type in ("混合", "灵活"):
        rotation = 5
    elif "纳斯达克" in fund_name or "科技" in fund_name:
        rotation = 3
    else:
        rotation = 3
    
    meso_total = min(30, prosperity + pe_score + policy + rotation)
    return meso_total, {}, ""
```

- [ ] **Step 4: 重构 `_score_micro` —— 保持纯数字逻辑，去除文本字符串**

```python
def _score_micro(self, code: str) -> Tuple[int, Dict, str]:
    """微观维度量化打分（纯数字基准，满分 50）
    
    结构: 经理(0-10) + Alpha(0-12) + 回撤(0-10) + 夏普(0-10) + 机构(0-8)
    """
    fund = self.funds.get(code, {})
    perf = fund.get("perf", {}) or {}
    ft = fund.get("basic", {})
    fund_type = ft.get("fund_type", "domestic") if ft else "domestic"
    
    details = {}
    
    # ---- 1. 经理稳定性 (0-10) ----
    manager_name = ft.get("fund_manager", "") if ft else ""
    if manager_name:
        manager_score = 8
        details["manager"] = manager_name
    else:
        manager_score = 5
    
    # ---- 2. Alpha 持续性 (0-12) —— 基于夏普分档 ----
    sharpe_3y = perf.get("sharpe_3y") if perf else None
    if sharpe_3y is not None:
        sharpe_3y = float(sharpe_3y)
        if sharpe_3y > 1.5:
            alpha_score = 11
        elif sharpe_3y > 1.0:
            alpha_score = 9
        elif sharpe_3y > 0.5:
            alpha_score = 7
        elif sharpe_3y > 0:
            alpha_score = 4
        else:
            alpha_score = 3
    else:
        alpha_score = 4  # 数据缺失默认中位
    
    # ---- 3. 最大回撤 vs 同类 (0-10) ----
    max_dd = perf.get("max_drawdown_3y")
    if max_dd is not None:
        max_dd = float(max_dd)
        # 同类基准回撤
        if "QDII" in str(fund_type).upper() or fund_type == "qdii":
            peer_dd = 28
        elif fund_type in ("指数", "ETF", "etf", "index"):
            peer_dd = 30
        else:
            peer_dd = 22
        
        if max_dd < peer_dd * 0.8:
            drawdown_score = 9
        elif max_dd < peer_dd * 1.1:
            drawdown_score = 7
        elif max_dd < peer_dd * 1.3:
            drawdown_score = 5
        else:
            drawdown_score = 3
    else:
        drawdown_score = 3
    
    # ---- 4. 夏普比率 (0-10) ----
    sharpe_1y = perf.get("sharpe_1y")
    if sharpe_1y is not None:
        sharpe_1y = float(sharpe_1y)
        if sharpe_1y > 1.5:
            sharpe_score = 10
        elif sharpe_1y > 1.0:
            sharpe_score = 8
        elif sharpe_1y > 0.5:
            sharpe_score = 6
        elif sharpe_1y > 0.3:
            sharpe_score = 4
        else:
            sharpe_score = 2
    else:
        sharpe_score = 2
    
    # ---- 5. 机构持有变化 (0-8) ----
    holders = fund.get("holders", {})
    if holders:
        inst_score = 5
    else:
        inst_score = 4
    
    micro_total = min(50, manager_score + alpha_score + drawdown_score + sharpe_score + inst_score)
    return micro_total, details, ""
```

- [ ] **Step 5: 在 `score_fund` 中嵌入 Sortino 计算并重构输出结构**

找到 `score_fund` 方法的返回 dict 构建部分，修改为：

```python
# 在 score_fund 中，metadata dict 构建之后，final return 之前：
# 获取净值数据用于 Sortino 计算
nav_data = fund.get("nav", {}) or {}
daily_returns_raw = nav_data.get("daily_returns", [])
if daily_returns_raw:
    sortino_val = _compute_sortino_ratio(daily_returns_raw)
else:
    sortino_val = 0.0

# 计算 HHI（赫芬达尔指数）
holdings_data = fund.get("holdings", []) or []
hhi_val = _compute_hhi(holdings_data) if holdings_data else 0.0

# 获取高级指标
adv = self._compute_advanced_metrics(code) if completeness in ("A", "B") else {}
alpha_val = adv.get("jensen_alpha", 0.0)
ir_val = adv.get("information_ratio", 0.0)
beta_val = adv.get("beta", 1.0)
```

修改返回 dict：

```python
return {
    "fund_code": code,
    "fund_name": name,
    "data_completeness": completeness,
    "composite_score": composite_score,
    "score_level": score_level,
    "score_level_emoji": emoji,
    "score_tendency": recommendation["tendency"],
    # --- 新型三层解耦评分矩阵 ---
    "scoring_matrix": {
        "quant_baseline": {
            "macro_score": int(macro_total),
            "meso_score": int(meso_total) if meso_total is not None else None,
            "micro_score": int(micro_total),
            "total_baseline_score": int(composite_score),
        },
        "agent_overlay": {
            "macro_adjustment": 0,
            "meso_adjustment": 0,
            "micro_adjustment": 0,
            "total_adjustment": 0,
            "overlay_rationale": "",
        },
        "final_score": int(composite_score),
        "score_tendency": recommendation["tendency"],
    },
    # --- 新型连续特征矩阵 ---
    "feature_matrix": {
        "hhi_index": round(hhi_val, 4),
        "jensen_alpha": round(alpha_val, 4),
        "sortino_ratio": round(sortino_val, 4),
        "information_ratio": round(ir_val, 4),
        "beta": round(beta_val, 4),
        "max_drawdown_3y_pct": round(max_dd_3y, 2) if max_dd_3y else None,
        "annual_volatility": round(ann_vol, 2),
        "sharpe_1y": round(sharpe_1y, 2) if sharpe_1y else None,
    },
    # --- 兼容旧字段 ---
    "macro_score": int(macro_total),
    "meso_score": int(meso_total) if meso_total is not None else None,
    "micro_score": int(micro_total),
    "macro_basis": "",
    "meso_basis": "",
    "micro_basis": "",
    "macro_detail": {},
    "meso_detail": {},
    "micro_detail": {},
    # ... 其余字段保持不变 ...
}
```

- [ ] **Step 6: 添加 `_compute_hhi` 辅助函数**

```python
def _compute_hhi(holdings: list) -> float:
    """计算赫芬达尔-赫希曼指数（HHI）
    
    HHI = sum(weight_i^2) * 10000，范围 [0, 10000]
    > 2500: 高度集中
    1500-2500: 中度集中
    < 1500: 分散
    """
    if not holdings:
        return 0.0
    
    weights = []
    for h in holdings:
        weight = h.get("weight", 0) or h.get("ratio", 0) or 0
        weights.append(float(weight))
    
    if not weights or sum(weights) == 0:
        return 0.0
    
    # 归一化到 0-1
    total = sum(weights)
    normalized = [w / total for w in weights]
    hhi = sum(w * w for w in normalized) * 10000
    return round(hhi, 2)
```

- [ ] **Step 7: 语法验证**

```bash
python3 -c "from src.analysis.scorer import _compute_sortino_ratio, _compute_hhi; print('Import OK')"
```

---

### Task 4: 重构 `src/news/sentiment.py` —— 剔除 SnowNLP + 时间衰减 + 原子关键词

**Files:**
- Modify: `src/news/sentiment.py`

- [ ] **Step 1: 移除 SnowNLP 依赖，实现基于金融极性词典的 sentiment 打分**

```python
"""
舆情动力学与指数衰减聚合模块

剔除 SnowNLP，改用结构化金融行业情感特征极性字典。
每条新闻转换为 Severity（-1.0 ~ +1.0）和 Impact（0.0 ~ 1.0）的连续值。
"""

import re
import numpy as np
from collections import Counter
from src.config.defaults import QUANT_CONFIG


# === 金融情感极性字典 ===
_FINANCE_POSITIVE_WORDS = {
    "暴涨", "飙升", "利好", "突破", "创新高", "超预期", "盈利增长",
    "回购", "增持", "买入", "加仓", "净流入", "分红", "业绩翻倍",
    "AI", "人工智能", "芯片", "半导体", "突破", "放量", "主升浪",
    "涨停", "龙头", "领涨", "强劲", "扩张", "新订单", "需求旺盛",
    "政策支持", "补贴", "国产替代", "自主可控", "光刻机", "固态电池",
    "先发优势", "合作", "订单", "获批", "上市", "IPO",
}


_FINANCE_NEGATIVE_WORDS = {
    "暴跌", "崩盘", "利空", "破位", "创新低", "不及预期", "亏损",
    "减持", "卖出", "减仓", "净流出", "裁员", "下滑", "萎缩",
    "贸易战", "制裁", "管制", "加息", "收紧", "通胀", "衰退",
    "跌停", "踩踏", "违约", "爆雷", "退市", "ST", "停牌",
    "诉讼", "处罚", "警告", "违规", "调查", "产能过剩", "价格战",
}


def _compute_sentiment_severity(text: str) -> float:
    """基于金融极性词典计算文本情绪强度 Severity ∈ [-1.0, +1.0]
    
    使用简单词袋匹配 + 归一化，避免模型幻觉。
    正面词数 - 负面词数，除以总命中词数，映射到 [-1, 1]。
    """
    if not text:
        return 0.0
    
    pos_count = sum(1 for w in _FINANCE_POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in _FINANCE_NEGATIVE_WORDS if w in text)
    
    total = pos_count + neg_count
    if total == 0:
        return 0.0  # 无极性词 → 中性
    
    severity = (pos_count - neg_count) / total
    return round(severity, 4)


def _compute_news_impact(news_item: dict, holding_keywords: list = None) -> float:
    """计算单条新闻的产业链直接冲击权重 Impact
    
    基于新闻来源、是否匹配重仓股关键词计算：
    - 匹配重仓股关键词: +0.3 基础
    - 公司公告: 1.0
    - 行业要闻: 0.5
    - 市场电报: 0.3
    - 默认: 0.3
    """
    base_impact = 0.3
    
    # 检查是否匹配重仓股
    if holding_keywords:
        title = news_item.get("title", "") or ""
        content = news_item.get("content", "") or ""
        combined = title + content
        matches = sum(1 for kw in holding_keywords if kw in combined)
        if matches > 0:
            base_impact = min(1.0, 0.3 + 0.15 * matches)
    
    # 来源权重
    source = news_item.get("source", "") or ""
    if "公告" in source or "财报" in source:
        base_impact = max(base_impact, 1.0)
    elif "要闻" in source:
        base_impact = max(base_impact, 0.5)
    
    return round(base_impact, 2)
```

- [ ] **Step 2: 重写 `analyze_sentiment` 函数**

```python
def analyze_sentiment(news_list: List[Dict], holding_keywords: list = None) -> List[Dict]:
    """对新闻列表进行情感分析（基于金融极性词典）
    
    每项添加: sentiment_score, sentiment_label, severity, impact
    不再依赖 SnowNLP。
    """
    enriched = []
    for item in news_list:
        text = (item.get("title", "") or "") + " " + (item.get("content", "") or "")
        
        # 计算严重性 Severity
        severity = _compute_sentiment_severity(text)
        
        # 计算冲击权重 Impact
        impact = _compute_news_impact(item, holding_keywords)
        
        # 综合 sentiment_score = severity * impact，再映射回 0-1 兼容区间
        raw_score = severity * impact
        sentiment_score = round((raw_score + 1.0) / 2.0, 4)  # 映射到 [0, 1]
        
        # 标签
        if severity > 0.2:
            label = "positive"
        elif severity < -0.2:
            label = "negative"
        else:
            label = "neutral"
        
        enriched.append({
            **item,
            "sentiment_score": sentiment_score,
            "sentiment_label": label,
            "severity": severity,
            "impact": impact,
            "keywords": _extract_atomic_keywords(text),
        })
    
    return enriched
```

- [ ] **Step 3: 重写 `daily_sentiment_aggregate` 加入时间衰减**

```python
def daily_sentiment_aggregate(
    news_with_sentiment: List[Dict],
    lam: float = None
) -> List[Dict]:
    """按日聚合情绪，并在最终综合时执行指数时间衰减
    
    Args:
        lam: 时间衰减系数 λ。默认从 QUANT_CONFIG 读取。
    """
    if lam is None:
        lam = QUANT_CONFIG.get("NEWS_LAMBDA", 0.200)
    
    # 第一步：按日期分组
    by_date = {}
    for item in news_with_sentiment:
        date_key = item.get("date", "") or item.get("publish_date", "")
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(item)
    
    # 第二步：逐日统计
    daily_aggs = []
    for date_key in sorted(by_date.keys()):
        items = by_date[date_key]
        n = len(items)
        
        # 使用 severity * impact 的原始极性计算均值（而非映射后的 0-1 值）
        raw_scores = [
            it.get("severity", 0.0) * it.get("impact", 0.3)
            for it in items
        ]
        sentiment_mean = np.mean(raw_scores) if raw_scores else 0.0
        # 映射回 0-1 以便兼容旧报告渲染
        sentiment_mean_01 = round((sentiment_mean + 1.0) / 2.0, 4)
        
        labels = [it.get("sentiment_label", "neutral") for it in items]
        pos_count = labels.count("positive")
        neg_count = labels.count("negative")
        
        # 关键词聚合
        all_kw = []
        for it in items:
            all_kw.extend(it.get("keywords", []))
        kw_counter = Counter(all_kw)
        
        daily_aggs.append({
            "date": str(date_key),
            "positive_rate": round(pos_count / n, 4) if n else 0,
            "negative_rate": round(neg_count / n, 4) if n else 0,
            "neutral_rate": round((n - pos_count - neg_count) / n, 4) if n else 0,
            "sentiment_mean": sentiment_mean_01,
            "news_count": n,
            "top_keywords": [kw for kw, _ in kw_counter.most_common(10)],
        })
    
    # 第三步：时间衰减加权聚合终值
    if daily_aggs:
        total_weight = 0.0
        weighted_sum = 0.0
        current_idx = len(daily_aggs) - 1
        
        for idx, agg in enumerate(daily_aggs):
            delta_t = current_idx - idx
            decay_weight = np.exp(-lam * delta_t)
            weighted_sum += agg["sentiment_mean"] * decay_weight
            total_weight += decay_weight
        
        decayed_sentiment = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.5
        
        # 将衰减终值附加到最后一个聚合日
        daily_aggs[-1]["decayed_sentiment_final"] = decayed_sentiment
    
    return daily_aggs
```

- [ ] **Step 4: 替换 `extract_sector_keywords` 为原子化白名单匹配**

```python
# === 原子化产业关键词白名单 ===
_ATOMIC_INDUSTRY_KEYWORDS = [
    # 半导体
    "半导体", "芯片", "光刻机", "光刻胶", "晶圆", "封装", "HBM", "NAND", "DRAM",
    "台积电", "中芯国际", "华虹", "寒武纪", "海光", "英伟达", "AMD", "ASML",
    # AI/科技
    "人工智能", "AI", "大模型", "算力", "数据中心", "CPO", "光模块",
    "Meta", "谷歌", "微软", "亚马逊", "苹果", "特斯拉",
    # 新能源
    "新能源", "光伏", "锂电", "电池", "固态电池", "钠离子", "储能", "充电桩",
    "碳酸锂", "宁德时代", "比亚迪", "赣锋", "阳光电源", "先导智能",
    # 油气/能源
    "石油", "原油", "天然气", "LNG", "布伦特", "OPEC", "三桶油",
    "中国海油", "中国石油", "中国石化",
    # 消费
    "消费", "白酒", "茅台", "五粮液", "家电", "汽车",
    # 医药
    "医药", "创新药", "CXO", "医疗器械", "百济神州",
    # 金融/地产
    "银行", "券商", "保险", "地产",
    # 港股/海外
    "港股", "恒生", "腾讯", "阿里巴巴", "美团",
    # 周期
    "黄金", "铜", "铝", "钢铁", "煤炭", "化工",
]


def _extract_atomic_keywords(text: str) -> List[str]:
    """从文本中提取原子化产业关键词（白名单精确匹配）
    
    返回无空格、无泛化词的原子名词列表。
    """
    if not text:
        return []
    
    found = []
    for kw in _ATOMIC_INDUSTRY_KEYWORDS:
        if kw in text:
            found.append(kw)
    
    return list(dict.fromkeys(found))  # 去重保序


def extract_sector_keywords(news_list: List[Dict]) -> List[str]:
    """从新闻列表提取行业关键词（兼容旧接口）
    
    使用原子化白名单匹配替代硬编码遍历。
    """
    all_kw = []
    for item in news_list:
        text = (item.get("title", "") or "") + " " + (item.get("content", "") or "")
        all_kw.extend(_extract_atomic_keywords(text))
    
    # 按频率排序返回前 20
    counter = Counter(all_kw)
    return [kw for kw, _ in counter.most_common(20)]
```

- [ ] **Step 5: 清理废弃 imports 并验证**

```bash
python3 -c "
from src.news.sentiment import analyze_sentiment, daily_sentiment_aggregate, _compute_sentiment_severity, _extract_atomic_keywords
# 测试 Severity
print('Severity test:', _compute_sentiment_severity('英伟达暴涨超预期 AI芯片需求旺盛'))
print('Severity test:', _compute_sentiment_severity('裁员潮来袭 科技股暴跌不及预期'))
print('Keywords:', _extract_atomic_keywords('英伟达HBM芯片需求旺盛，台积电CoWoS封装产能爆单'))
"
```

---

### Task 5: 重构 `src/output/report.py` —— 删除越权硬编码文本，纯化为插槽供给者

**Files:**
- Modify: `src/output/report.py`

- [ ] **Step 1: 删除 `_render_tldr` 中代码替模型总结的硬编码逻辑**

找到 `_render_tldr` 函数，删除 fallback 分支中的定性文本生成代码（保留 agent_decisions 优先的逻辑，但当 agent_decisions 不存在时，只输出纯数字事实，不替 agent 总结）：

```python
def _render_tldr(scores, holdings_data, news_data, recommendations, agent_decisions):
    """TL;DR 摘要（仅客观数据，文本留给 agent 填充）"""
    lines = []
    
    if agent_decisions and agent_decisions.get("portfolio"):
        pd = agent_decisions["portfolio"]
        lines.append(f"- 组合 Agent 研判：{pd.get('tldr', '待 agent 归因')}")
        lines.append(f"- 战术姿态：{pd.get('stance', '待评估')}")
        return "\n".join(lines) + "\n"
    
    # Fallback: 仅输出纯数字事实，不做文本总结
    avg_score = sum(s.get("composite_score", 0) for s in scores) / len(scores) if scores else 0
    weak_count = sum(1 for s in scores if s.get("composite_score", 0) < 45)
    total_value = holdings_data.get("total_value", 0) if holdings_data else 0
    event_count = sum(n.get("news_count", 0) for n in (news_data or []))
    rec_count = len(recommendations) if recommendations else 0
    
    lines.append(f"- 组合规则初评分均值 {avg_score:.1f}/100；偏弱基金 {weak_count} 只；当前市值 ¥{total_value:,.2f}。")
    lines.append(f"- 新闻事件聚类 {event_count} 条；需由 agent 结合重仓链条做最终归因。")
    lines.append(f"- 推荐候选 {rec_count} 只；已做内部去同质化约束，最终推荐需按组合角色筛选。")
    
    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: 删除 `_render_market_brief` 函数**

整个函数删除（约 15 行）。该函数的功能由 agent 在 SLOT: 大盘归因 中完成。

在 `_render_trade_day_focus` 中，移除对 `_render_market_brief` 的调用，替换为纯数据行 + AGENT 标记：

```python
def _render_trade_day_focus(...):
    # ... 前面 QDII 表和 DCA 表的代码保持不变 ...
    
    # 替换市场简报：仅输出数字事实，文本留给 agent
    lines.append(f"\n### 大盘环境与当日根因\n")
    lines.append(f"- 组合平均评分：{avg_score:.1f}/100")
    if qdii_rows:
        lines.append(f"- QDII 覆盖 {len(qdii_rows)} 只（结算状态见上表）")
    if news_data:
        avg_sent = np.mean([n.get('sentiment_mean', 0) for n in news_data if n.get('sentiment_mean') is not None])
        lines.append(f"- 新闻情绪均值：{avg_sent:.2f}（{'偏正面' if avg_sent > 0.55 else '偏谨慎' if avg_sent < 0.45 else '中性'}）")
    lines.append(f"- 今日重点先看净值口径、QDII 确认状态和 pending 金额，再解读涨跌原因。")
    lines.append(f"\n<!-- AGENT: 大盘归因 -->\n")
```

- [ ] **Step 3: 删除 `_render_rebalance_brief` 等价代码（`_render_non_trade_day_focus` 中）**

保留 AGENT 标记，删除背后任何硬编码的文本生成逻辑。`_render_non_trade_day_focus` 中只保留数据和 AGENT 标记。

- [ ] **Step 4: 删除资金分配表中硬编码的 `target_pct` 计算逻辑**

在 `generate_report` 中构建资金分配表的部分，将所有基于评分计算 `target_pct` 的 `if-else` 逻辑删除，仅保留 `<!-- AGENT_FILL -->` 占位符：

```python
# 资金分配表 —— 仅输出当前数据，建议列全部留空给 Agent
rebalance_rows = []
for h in holdings_list:
    code = h.get("code", "")
    name = h.get("name", "")
    value = h.get("current_value", 0)
    pct = h.get("weight_pct", 0)
    rebalance_rows.append(
        f"| {name}（{code}） | ¥{value:,.2f} | {pct:.2f}% "
        f"| <!-- AGENT_FILL --> | <!-- AGENT_FILL --> | <!-- AGENT_FILL --> |"
    )
```

- [ ] **Step 5: 语法验证**

```bash
python3 -c "from src.output.report import generate_report; print('Report import OK')"
```

---

### Task 6: 更新 `src/output/templates.py` —— 补充 Sortino 展示

**Files:**
- Modify: `src/output/templates.py`

- [ ] **Step 1: 在 `portfolio_overview_table` 的风险指标部分添加 Sortino 列提示**

找到风险指标输出行（年化波动率/最大回撤/夏普比率附近），在报告格式说明中增加 Sortino 的文档注释（实际渲染由 scorer 数据驱动，模板不需要改逻辑）。

无需实质性修改——`generate_report` 会自动从 `score_payload.feature_matrix.sortino_ratio` 取值渲染。

---

## Phase 3: 全链路回归与冒烟测试

### Task 7: 运行既有测试套件确保无断裂

**Files:**
- Test: `tests/test_engine_calculator.py`
- Test: `tests/test_news_fetcher.py`

- [ ] **Step 1: 运行引擎计算器测试**

```bash
python3 -m pytest tests/test_engine_calculator.py -v 2>&1
```

Expected: 7 passed.

- [ ] **Step 2: 运行新闻抓取测试**

```bash
python3 -m pytest tests/test_news_fetcher.py -v 2>&1
```

Expected: 6 passed.

- [ ] **Step 3: 运行报告生成相关测试**

```bash
python3 -m pytest tests/test_report_agent_decisions.py tests/test_agent_context.py -v 2>&1
```

Expected: 7 passed.

- [ ] **Step 4: 运行推荐引擎测试**

```bash
python3 -m pytest tests/test_recommend_engine.py -v 2>&1
```

Expected: 4 passed.

- [ ] **Step 5: 若任何测试失败，根据失败信息修复对应模块**

常见需要修复的点：
- `test_report_agent_decisions.py:test_agent_markers_present` — 验证 AGENT 标记存在。如果删除硬编码函数后标记格式变化，更新测试断言。
- `test_agent_context.py` — 检查 `build_score_judgment_context` 是否能从新的 `scoring_matrix` 结构中提取数据。

### Task 8: 端到端集成测试

- [ ] **Step 1: 运行完整 analyze 流程（跳过推荐加速）**

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-recommend 2>&1 | tail -30
```

Expected: 
- `报告已保存: report.md`
- 无 ImportError / AttributeError
- 无 NaN / None 导致的 TypeError

- [ ] **Step 2: 验证 report.md 包含正确的插槽标记**

```bash
grep -c "AGENT_FILL\|<!-- AGENT:" report.md
```

Expected: 23+ (实际数量视持仓只数变动，至少 20+)

- [ ] **Step 3: 验证 report.md 不含定性硬编码文本**

```bash
grep -c "周期适配\|流动性\|估值\|行业景气度" report.md
```

Expected: 显著减少或为 0（因为 scorer 不再产出 basis 字符串）

- [ ] **Step 4: 验证新 feature_matrix 字段出现在输出中（可选，通过 scorer 直接测试）**

```bash
python3 -c "
from src.analysis.scorer import FundAnalyzer
import json
a = FundAnalyzer()
a.load_fund('001198')
s = a.score_fund('001198')
print('scoring_matrix keys:', list(s.get('scoring_matrix', {}).keys()))
print('feature_matrix keys:', list(s.get('feature_matrix', {}).keys()))
print('sortino_ratio:', s.get('feature_matrix', {}).get('sortino_ratio'))
print('hhi_index:', s.get('feature_matrix', {}).get('hhi_index'))
"
```

Expected: 打印 scoring_matrix 含 quant_baseline/agent_overlay/final_score，feature_matrix 含 sortino_ratio/hhi_index 等。

---

## 完工标准

- [x] Phase 0 完成: SKILL.md 更新为 2026-05-21 新版
- [ ] Phase 1 完成: verify_quant_framework.py 全部 PASS
- [ ] Phase 2 完成: scorer.py (3层解耦+Sortino) / sentiment.py (去SnowNLP+衰减) / report.py (去硬编码) / defaults.py (QUANT_CONFIG)
- [ ] Phase 3 完成: 所有 24 个单元测试 PASS + 端到端 analyze 成功
