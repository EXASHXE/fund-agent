# 系统架构升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 0520_plan 完成新闻引擎增强、内存闭环流转、量化指标扩展、后置校验器四模块改造。

**Architecture:** 四路并行改造 — 新闻采集（`news_fetcher.py` 重写匹配 + 新增源 + 降级）、流程控制（`keyword_cache.py` 缩短缓存 + `cli.py` Agent inline 回调）、量化分析（`holdings.py` HHI + `scorer.py` IR/Alpha/Treynor）、报告校验（新建 `validator.py` + 集成到 `cli.py`）。

**Tech Stack:** Python 3.12+, AKShare, pandas, numpy, unittest

---

### Task 1: 重写 `_matches_terms` — 统一字符级关键词匹配

**Files:**
- Modify: `src/news/news_fetcher.py:205-220`
- Test: `tests/test_news_fetcher.py`（修改现有测试，新增中文短词测试）

- [ ] **Step 1: 重写函数，移除 `\b`/`isascii` 分支**

```python
def _matches_terms(text: str, terms: List[str]) -> bool:
    """统一字符级关键词匹配。中文按单字包含，英文按小写包含。"""
    if not text:
        return False
    text_lower = text.lower()
    for term in terms:
        term = str(term).strip()
        if len(term) < 2:
            continue
        if term.lower() in text_lower:
            return True
    return False
```

**原理**：中文关键词（如"芯片"、"AI"、"半导体"）直接用 `in` 做子串匹配，无需 `\b` 或 `isascii` 边界。`text_lower` 和 `term.lower()` 统一小写化后，无论中英文都能正确命中。移除原有 `len(term) <= 2 and term_lower.isascii()` 的特殊分支——2 字符英文如 "AI" 也能被 `in` 匹配，误匹配风险极低（新闻文本几乎不可能出现孤立的 "ai" 字符串指代非人工智能含义）。

- [ ] **Step 2: 修改现有 news_fetcher 测试以匹配新行为**

```python
def test_matches_terms_chinese_short(self):
    """短中文关键词（2-3字）应命中"""
    self.assertTrue(_matches_terms("芯片行业迎来利好", ["芯片"]))
    self.assertTrue(_matches_terms("半导体板块大涨", ["半导体"]))
    self.assertTrue(_matches_terms("白酒消费回暖", ["白酒"]))

def test_matches_terms_english_short(self):
    """短英文关键词（2字符）应命中"""
    self.assertTrue(_matches_terms("AI芯片需求爆发", ["AI"]))
    self.assertTrue(_matches_terms("NVIDIA股价创新高", ["NV"]))

def test_matches_terms_no_false_positive(self):
    """不应有误匹配"""
    self.assertFalse(_matches_terms("正常文章内容", ["芯片"]))
    self.assertFalse(_matches_terms("regular text", ["AI"]))
```

- [ ] **Step 3: 运行测试**

Run: `python3 -m unittest tests.test_news_fetcher -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/news/news_fetcher.py tests/test_news_fetcher.py
git commit -m "refactor: rewrite _matches_terms to unified substring matching"
```

---

### Task 2: 新增 AKShare 数据源 — 财联社电报全量流 + 行业新闻

**Files:**
- Modify: `src/news/news_fetcher.py:132-151`

- [ ] **Step 1: 扩展 `_fetch_market_news_frames` 函数**

```python
def _fetch_market_news_frames(ak, days: int):
    frames = []

    # 财联社电报全量流（时效性更强、数据量更大）
    try:
        frames.append((ak.stock_telegraph_cls(), "财联社电报全量"))
    except Exception:
        pass

    # 现有：财联社分类电报
    for symbol in ["全部", "重点"]:
        try:
            frames.append((ak.stock_info_global_cls(symbol=symbol), f"财联社电报:{symbol}"))
        except Exception:
            pass

    # 行业新闻兜底（申万一级行业覆盖）
    for industry in ["半导体", "新能源", "医药", "消费", "科技"]:
        try:
            frames.append((ak.stock_info_global_cls(symbol=industry), f"行业新闻:{industry}"))
        except Exception:
            pass

    try:
        frames.append((ak.stock_news_main_cx(), "财新数据通"))
    except Exception:
        pass

    # 新闻联播（最多回看 3 天）
    for i in range(min(days, 3)):
        d = (_shared_today() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            frames.append((ak.news_cctv(date=d), f"新闻联播:{d}"))
        except Exception:
            pass

    return frames
```

- [ ] **Step 2: Commit**

```bash
git add src/news/news_fetcher.py
git commit -m "feat: add ak.stock_telegraph_cls and industry news sources"
```

---

### Task 3: 关键词降级匹配 — 空白回退二次扫描

**Files:**
- Modify: `src/news/news_fetcher.py:81-129`（`fetch_fund_news` 函数）

- [ ] **Step 1: 在 `fetch_fund_news` 末尾增加降级逻辑**

在 `fetch_fund_news` 函数 return 之前，如果 `all_news` 为空，执行降级重试：

```python
    all_news.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 降级匹配：首轮关键词无命中时，自动缩短关键词重试
    if not all_news:
        degraded_terms = _degrade_keywords(search_terms)
        if degraded_terms and degraded_terms != search_terms:
            for df, source_hint in _fetch_market_news_frames(ak, days):
                _append_news_from_df(
                    all_news, seen, df, cutoff,
                    source_hint=source_hint,
                    include_terms=degraded_terms,
                )
            all_news.sort(key=lambda x: x.get("date", ""), reverse=True)

    return all_news


def _degrade_keywords(terms: List[str]) -> List[str]:
    """关键词降级：截取前2字 + 兜底词组。"""
    degraded = []
    for t in terms:
        t = str(t).strip()
        if len(t) >= 2:
            degraded.append(t[:2])  # 截取前 2 字（中文）或全词（英文短词）
    # 去重
    seen = set()
    result = []
    for kw in degraded:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result
```

**注意**：`_degrade_keywords` 需要添加到 `news_fetcher.py`（在 `_matches_terms` 附近）。

- [ ] **Step 2: Commit**

```bash
git add src/news/news_fetcher.py
git commit -m "feat: add keyword degradation fallback for zero-hit news search"
```

---

### Task 4: 缩短关键词缓存至 14 天

**Files:**
- Modify: `src/news/keyword_cache.py:9`

- [ ] **Step 1: 修改常量**

```python
MAX_CACHE_AGE_DAYS = 14
```

将 `src/news/keyword_cache.py:9` 的 `MAX_CACHE_AGE_DAYS = 90` 改为 `MAX_CACHE_AGE_DAYS = 14`。

- [ ] **Step 2: Commit**

```bash
git add src/news/keyword_cache.py
git commit -m "feat: shorten news keyword cache max age from 90 to 14 days"
```

---

### Task 5: Agent inline 回调接口 + cli.py 流程改造

**Files:**
- Modify: `src/cli.py:115-131`（缓存失效处理段）
- Modify: `src/cli.py:142-162`（报告生成后集成 validator）

- [ ] **Step 1: 定义 `request_agent_keywords_inline` 回调签名**

在 `src/cli.py` 中（或新建 `src/news/agent_bridge.py`），在 `cmd_analyze` 之前新增：

```python
def request_agent_keywords_inline(
    holding_codes: List[str],
    fund_profiles: List[Dict],
) -> Optional[Dict[str, List[str]]]:
    """标准 Agent 关键词请求回调。上层 runtime 可 monkey-patch 此函数。

    返回格式: {"fund_code": ["kw1", "kw2", ...], ...}
    若 Agent 不可用（纯 CLI），返回 None 触发降级兜底。
    """
    return None  # 默认无 Agent，降级到重仓股名+默认词
```

- [ ] **Step 2: 改造 `cmd_analyze` 缓存失效分支**

修改 `src/cli.py` 中缓存失效后的逻辑（约 line 124-127）：

```python
    news_keyword_plan = load_valid_keyword_cache(keyword_cache_path, codes, today=_shared_today())
    if not news_keyword_plan:
        # 尝试 Agent inline 回调获取实时关键词
        fund_profiles = []
        for code in codes:
            fund_data = analyzer.funds.get(code, {})
            basic = fund_data.get("basic", {})
            fund_profiles.append({
                "code": code,
                "name": basic.get("name", code),
                "type": basic.get("fund_type", ""),
            })
        agent_kw = request_agent_keywords_inline(codes, fund_profiles)
        if agent_kw:
            news_keyword_plan = {
                "cache_version": "news_keyword_profiles.v1",
                "holding_codes": sorted(codes),
                "generated_at": _shared_today().isoformat(),
                "funds": {
                    code: {"keywords": agent_kw.get(code, [])}
                    for code in codes
                },
            }
        else:
            print(f"[INFO] Agent 不可用，降级使用基金重仓股名 + 默认词组推导关键词。")
```

**关键变更**：移除 `[WARN]` 日志，改为 `[INFO]` 说明降级策略；不再写中间文件；Agent 可用时内存内构造 `news_keyword_plan`。

- [ ] **Step 3: Commit**

```bash
git add src/cli.py
git commit -m "feat: add inline agent keyword callback with graceful degradation"
```

---

### Task 6: HHI 指数计算 — `holdings.py`

**Files:**
- Modify: `src/analysis/holdings.py`（新增 `compute_hhi` 函数）

- [ ] **Step 1: 新增 HHI 计算函数**

在 `src/analysis/holdings.py` 文件末尾添加：

```python
def compute_hhi(holdings_df) -> Optional[float]:
    """计算赫芬达尔-赫施曼指数（HHI）。

    HHI = sum((weight_i * 100)^2) for top 10 holdings.
    数值范围: 0（完全分散）~ 10000（完全集中）。
    > 2500 表示高度集中，< 1500 表示分散。
    """
    if holdings_df is None or getattr(holdings_df, "empty", True):
        return None
    try:
        hhi = 0.0
        for _, row in holdings_df.head(10).iterrows():
            weight_col = None
            for col in ["占净值比例", "持仓占比", "占比", "持股占比"]:
                if col in row and row.get(col) is not None:
                    weight_col = col
                    break
            if weight_col:
                w = float(row[weight_col])
                hhi += (w * 100) ** 2
        return round(hhi, 2)
    except Exception:
        return None
```

- [ ] **Step 2: 在 `FundAnalyzer._build_fund_context` 中集成 HHI**

修改 `src/analysis/scorer.py:407-439` 中的 `_build_fund_context`，在 return 的 dict 中追加：

```python
        hhi_val = None
        if isinstance(holdings, pd.DataFrame) and not holdings.empty:
            from src.analysis.holdings import compute_hhi
            hhi_val = compute_hhi(holdings)
        return {
            ...
            "hhi": hhi_val,
            ...
        }
```

- [ ] **Step 3: Commit**

```bash
git add src/analysis/holdings.py src/analysis/scorer.py
git commit -m "feat: add HHI concentration index to holdings analysis"
```

---

### Task 7: 高级量化指标 — Information Ratio, Jensen's Alpha, Treynor Ratio

**Files:**
- Modify: `src/analysis/scorer.py`（新增 `_compute_advanced_metrics` 方法）

- [ ] **Step 1: 在 `FundAnalyzer` 类中新增方法**

在 `src/analysis/scorer.py` 的 `FundAnalyzer` 类中（`_compute_perf_from_nav` 之后）添加：

```python
    def _compute_advanced_metrics(self, code: str) -> dict:
        """计算信息比率、詹森 Alpha、特雷诺比率。

        使用 NASDAQ 100 (^NDX) 和沪深300 (000300) 作为市场基准。
        QDII 用纳斯达克，国内用沪深300。
        """
        import numpy as np

        nav_df = self.funds[code].get("nav")
        if nav_df is None or nav_df.empty or "日增长率" not in nav_df.columns:
            return {}

        returns = nav_df["日增长率"].dropna().values / 100.0
        if len(returns) < 60:
            return {}

        basic = self.funds[code].get("basic", {})
        ftype = basic.get("fund_type", "")
        is_qdii = "QDII" in ftype

        # 获取基准指数日收益
        try:
            import akshare as ak
            if is_qdii:
                bench_df = ak.index_us_stock_sina(symbol=".IXIC")
                bench_df["date"] = pd.to_datetime(bench_df["date"])
                bench_df["return"] = bench_df["close"].pct_change()
            else:
                bench_df = ak.stock_zh_index_daily(symbol="sh000300")
                bench_df["date"] = pd.to_datetime(bench_df["date"])
                bench_df["return"] = bench_df["close"].pct_change()
            bench_returns = bench_df["return"].dropna().values
            bench_returns = bench_returns[-len(returns):] if len(bench_returns) > len(returns) else bench_returns
        except Exception:
            return {}

        if len(bench_returns) < 30:
            return {}

        # 对齐长度
        min_len = min(len(returns), len(bench_returns))
        fund_r = returns[-min_len:]
        bench_r = bench_returns[-min_len:]

        rf_daily = 0.025 / 252  # 无风险利率 2.5%

        # Beta (协方差/方差)
        cov = np.cov(fund_r, bench_r)[0][1]
        var = np.var(bench_r)
        beta = cov / var if var > 0 else 1.0

        # 信息比率 (IR)
        excess = fund_r - bench_r
        ir = (np.mean(excess) / np.std(excess)) * np.sqrt(252) if np.std(excess) > 0 else 0

        # 詹森 Alpha
        alpha = (np.mean(fund_r - rf_daily) - beta * np.mean(bench_r - rf_daily)) * 252

        # 特雷诺比率
        treynor = (np.mean(fund_r - rf_daily) * 252) / beta if beta > 0 else 0

        return {
            "information_ratio": round(float(ir), 4),
            "jensen_alpha": round(float(alpha), 4),
            "treynor_ratio": round(float(treynor), 4),
            "beta": round(float(beta), 4),
        }
```

- [ ] **Step 2: 在 `_build_fund_context` 中集成**

在 `_build_fund_context` return dict 中追加 `"advanced_metrics": self._compute_advanced_metrics(code)`。

- [ ] **Step 3: Commit**

```bash
git add src/analysis/scorer.py
git commit -m "feat: add IR, Jensen's Alpha, Treynor Ratio advanced metrics"
```

---

### Task 8: 新建后置校验器 `validator.py`

**Files:**
- Create: `src/output/validator.py`
- Modify: `src/cli.py:142-162`

- [ ] **Step 1: 创建 `src/output/validator.py`**

```python
"""报告后置校验器：止盈止损线自动校准 + 合规声明强制追加。"""
import re
from typing import Dict


COMPLIANCE_TEXT = """---

## 风险提示

- 本报告基于历史公共数据和统计模型自动生成，不构成任何形式的投资承诺或保证
- 历史业绩不代表未来表现，市场有风险，投资需谨慎
- 海外市场（QDII）基金额外面临汇率波动、交易时差和流动性风险
- 情景压力测试为理论假设模拟，实际市场可能出现超出假设范围的更极端波动
- 定投是长期策略，短期浮亏属正常现象，请确保有持续现金流支撑
- 投资者应结合自身风险承受能力、流动性需求和投资期限审慎决策"""


def post_process_report(raw_markdown: str, analytics_evidence: dict) -> str:
    """后置处理 Markdown 报告：校正止盈止损线，追加合规声明。

    analytics_evidence 应包含:
      - scores: List[Dict]（每只基金的评分详情，含 annual_volatility）
    """
    result = raw_markdown

    # 1. 止盈止损线自动校准
    scores = analytics_evidence.get("scores", [])
    for s in scores:
        vol = s.get("annual_volatility", 20) or 20
        fund_name = s.get("fund_name", "")
        if not fund_name:
            continue

        # 公式：止盈 = vol * 2.0（上限 60%），止损 = vol * 1.5（上限 40%）
        stop_profit = min(60.0, max(15.0, vol * 2.0))
        stop_loss = min(40.0, max(10.0, vol * 1.5))

        # 替换报告中的止盈线
        result = re.sub(
            rf'(\*\*{re.escape(fund_name)}\*\*.*?\|\s*\*\*止盈线\*\*\s*\|\s*)\+[\d.]+%',
            rf'\1+{stop_profit:.2f}%',
            result,
            flags=re.DOTALL,
        )
        # 替换报告中的止损线
        result = re.sub(
            rf'(\*\*{re.escape(fund_name)}\*\*.*?\|\s*\*\*止损线\*\*\s*\|\s*)-?[\d.]+%',
            rf'\1-{stop_loss:.2f}%',
            result,
            flags=re.DOTALL,
        )

    # 2. 移除已有的风险提示（如有），追加标准合规声明
    # 找到最后出现的 "## 风险提示" 并移除其后的所有内容
    existing_idx = result.rfind("## 风险提示")
    if existing_idx >= 0:
        # 查找该标题后的下一个 --- 分隔线，删除到文件末尾
        result = result[:existing_idx].rstrip()

    result = result.rstrip() + "\n\n" + COMPLIANCE_TEXT + "\n"

    return result
```

- [ ] **Step 2: 在 `cli.py` 的 `cmd_analyze` 中集成 validator**

在 `cmd_analyze` 的报告写入之前（约 line 154-156），插入 validator 调用：

```python
    # 后置校验：止盈止损校准 + 合规声明追加
    from src.output.validator import post_process_report
    report = post_process_report(report, {"scores": scores})
```

- [ ] **Step 3: Commit**

```bash
git add src/output/validator.py src/cli.py
git commit -m "feat: add post-process report validator with auto stop-profit/loss and compliance"
```

---

### Task 9: 全链路冒烟测试

**Files:**
- Test: 运行完整分析命令

- [ ] **Step 1: 执行完整分析**

```bash
python3 -m src.cli analyze -c fund-portfolio.yaml -o report.md --skip-recommend
```

检查输出要求：
- 无异常退出
- 新闻采集有实质性输出（非全部 empty）
- 报告末尾有 6 条合规声明
- 止盈止损线为波动率×2.0/×1.5 计算值

- [ ] **Step 2: 运行全部单测**

```bash
python3 -m unittest discover tests -v
```
Expected: All 24+ tests PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: full system smoke test passed after optimization"
```
