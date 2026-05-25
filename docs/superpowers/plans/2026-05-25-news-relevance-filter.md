# 新闻相关性双层过滤优化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过规则层缩窄抓取口径 + Agent 层持仓相关性判断，消除与基金持仓无关的新闻（如"雷军谈手机涨价"出现在英伟达重仓的 QDII 基金中）。

**Architecture:** Layer 1 在 `news_fetcher.py` 和 `entity_mapper.py` 中修复关键词匹配（词边界、移除宽泛词、权重预算、fallback 禁用）。Layer 2 在 `agent_context.py` 中新增 `build_news_relevance_task()` 构造 Agent 判断上下文，在 `cli.py` 中追加到 `report.evidence.json`，Agent 执行 fund-analyst skill 时逐条判断并将结果写入 `agent_decisions.json`。

**Tech Stack:** Python 3, re (regex), unittest

---

### Task 1: 词边界匹配（`_matched_terms`）

**Files:**
- Modify: `src/news/news_fetcher.py:410-422`
- Modify: `tests/test_news_fetcher.py`

- [ ] **Step 1: 添加词边界匹配的测试**

```python
def test_matched_terms_english_word_boundary(self):
    from src.news.news_fetcher import _matched_terms
    # "AI" 作为独立词应匹配
    result = _matched_terms("NVIDIA AI chip demand surges", ["AI"])
    self.assertEqual(result, ["AI"])
    result = _matched_terms("NVDA launches new AI, HBM products", ["AI"])
    self.assertEqual(result, ["AI"])
    # "AI" 作为子串不应匹配
    result = _matched_terms("DAILY stock market update", ["AI"])
    self.assertEqual(result, [])
    result = _matched_terms("RAIL transportation news", ["AI"])
    self.assertEqual(result, [])
    result = _matched_terms("BAIC motor sales rise", ["AI"])
    self.assertEqual(result, [])

def test_matched_terms_chinese_word_boundary(self):
    from src.news.news_fetcher import _matched_terms
    # "芯片" 作为独立词应匹配（前后为空格/标点/行边界）
    result = _matched_terms("芯片需求爆发，英伟达受益", ["芯片"])
    self.assertEqual(result, ["芯片"])
    result = _matched_terms("半导体芯片行业景气度提升", ["芯片"])
    self.assertEqual(result, ["芯片"])
    # "芯片" 前面紧邻中文字符不应纯按子串宽松放行 —— 但"半导体芯片"是合理组合，保留
    result = _matched_terms("台积电高端制程满足AI芯片需求", ["芯片"])
    self.assertEqual(result, ["芯片"])

def test_matched_terms_short_english_rejects_substring(self):
    from src.news.news_fetcher import _matched_terms
    # "NV" 为短关键词，不应匹配 "NVIDIA"
    result = _matched_terms("NVIDIA stock hits all-time high", ["NV"])
    self.assertEqual(result, [])
    # 但独立出现时应匹配
    result = _matched_terms("NV is a ticker symbol", ["NV"])
    self.assertEqual(result, ["NV"])

def test_matched_terms_two_char_chinese(self):
    from src.news.news_fetcher import _matched_terms
    # 2字中文关键词：纯子串仍宽松匹配（避免"台积"丢失匹配），但需限制英文短词
    result = _matched_terms("台积电 Q1 财报超预期", ["台积"])
    self.assertEqual(result, ["台积"])
```

- [ ] **Step 2: 修改 `_matched_terms()` 实现词边界匹配**

```python
def _matched_terms(text: str, terms: List[str]) -> List[str]:
    """Return matched search terms with word-boundary awareness."""
    if not text:
        return []
    text_lower = text.lower()
    matched = []
    import re
    for term in terms:
        term = str(term).strip()
        if len(term) < 2:
            continue
        term_lower = term.lower()
        # 英文关键词（含纯ASCII）：启用 \b 词边界
        if term_lower.isascii():
            pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE)
            if pattern.search(text):
                matched.append(term)
        else:
            # 中文关键词 >= 2 字：保持子串匹配（"台积" → "台积电" 是合理降级）
            if term_lower in text_lower:
                matched.append(term)
    return matched
```

- [ ] **Step 3: 运行相关测试验证修改**

Run: `python -m pytest tests/test_news_fetcher.py -v`
Expected: All tests PASS（现有测试保持兼容，新增测试全部通过）

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/news_fetcher.py tests/test_news_fetcher.py
rtk git commit -m "fix(news): add word boundary matching to _matched_terms for English keywords"
```

---

### Task 2: 缩窄行业关键词白名单

**Files:**
- Modify: `src/news/entity_mapper.py:7-20` (`_SECTOR_KEYWORD_MAP`)
- Modify: `src/news/news_fetcher.py:492-556` (`_INDUSTRY_THEME_MAP`)

- [ ] **Step 1: 修改 `_SECTOR_KEYWORD_MAP` — "科技" → 精确关键词**

Remove the broad "科技" entry and replace with more specific sub-categories:

```python
_SECTOR_KEYWORD_MAP = {
    "白酒": ["白酒", "茅台", "五粮液", "泸州老窖", "消费"],
    "半导体": ["半导体", "芯片", "光刻机", "HBM", "台积电", "中芯国际", "英伟达", "ASML"],
    "新能源": ["锂电", "电池", "光伏", "储能", "固态电池", "钠离子", "宁德时代", "比亚迪"],
    "消费": ["消费", "电商", "零售", "食品", "饮料", "家电"],
    "医药": ["医药", "创新药", "CXO", "医疗器械", "百济神州"],
    "银行": ["银行", "城商行", "农商行", "息差", "不良率"],
    "算力": ["AI芯片", "数据中心", "光模块", "CPO", "英伟达", "算力"],
    "汽车": ["汽车", "智驾", "新能源车", "整车", "零部件"],
    "能源": ["石油", "原油", "天然气", "LNG", "OPEC", "煤炭"],
    "金融": ["券商", "保险", "非银", "资管"],
    "地产": ["地产", "房地产", "物业", "基建"],
    "有色": ["铜", "铝", "黄金", "稀土", "锂", "钴", "镍"],
}
```

**关键变化**：删除 `"科技": ["AI", "人工智能", "算力", "CPO", "光模块", "数据中心", "大模型"]`，新增 `"算力": ["AI芯片", "数据中心", "光模块", "CPO", "英伟达", "算力"]`（窄口径）。

- [ ] **Step 2: 修改 `_INDUSTRY_THEME_MAP` — 移除"科技"映射**

```python
_INDUSTRY_THEME_MAP = {
    # 半导体链条
    "半导体": "半导体",
    "芯片": "半导体",
    "AI芯片": "半导体",
    "光刻机": "半导体",
    "刻蚀机": "半导体",
    "光刻": "半导体",
    "闪存": "半导体",
    "HBM": "半导体",
    "先进封装": "半导体",
    "CMP": "半导体",
    "薄膜沉积": "半导体",
    "晶圆": "半导体",
    "国产替代": "半导体",
    "ASIC": "半导体",
    "检测设备": "半导体",
    "存储": "半导体",
    # 算力（替代原来的"科技"）
    "算力": "算力",
    "数据中心": "算力",
    "光模块": "算力",
    # 新能源
    "新能源": "新能源",
    "锂电池": "新能源",
    "光伏": "新能源",
    "电池": "新能源",
    "新能源车": "新能源",
    "固态电池": "新能源",
    "储能": "新能源",
    "锂电": "新能源",
    "动力电池": "新能源",
    "碳酸锂": "新能源",
    "换电": "新能源",
    # 能源
    "石油": "能源",
    "原油": "能源",
    "天然气": "能源",
    "能源": "能源",
    "LNG": "能源",
    "油服": "能源",
    "石化": "能源",
    "钻井平台": "能源",
    "油气": "能源",
    # 医药
    "医药": "医药",
    "创新药": "医药",
    # 消费
    "消费": "消费",
    "白酒": "消费",
    # 有色
    "黄金": "有色",
    "贵金属": "有色",
    # 全球/新兴
    "新兴市场": "全球",
    "港股": "全球",
    "韩国半导体": "半导体",
}
```

**关键变化**：移除 `"AI"`、`"美股科技"`、`"人工智能"`、`"纳斯达克"`、`"AWS"`、`"Copilot"`、`"自动驾驶"`、`"科技"` 等映射到"科技"行业的条目。这些不再触发拉取全"科技"行业新闻。

- [ ] **Step 3: 运行测试验证未破坏现有逻辑**

Run: `python -m pytest tests/test_news_fetcher.py tests/test_news_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/entity_mapper.py src/news/news_fetcher.py
rtk git commit -m "fix(news): narrow sector/industry keyword maps, remove overly broad '科技' category"
```

---

### Task 3: 按持仓权重分配搜索预算

**Files:**
- Modify: `src/news/news_fetcher.py:179-253` (`fetch_fund_news`)

- [ ] **Step 1: 在 `build_news_search_profile()` 输出中携带 weight 信息**

首先修改 `extract_holding_keywords()` 的返回值以携带权重，然后在 `build_news_search_profile()` 中暴露 `stock_weights`：

修改 `build_news_search_profile()`（在 `src/news/news_fetcher.py:139` 附近），在 profile dict 中增加 `stock_weights` 字段：

```python
def build_news_search_profile(
    fund_code: str,
    fund_name: str,
    fund_type: str = "",
    agent_keywords: List[str] = None,
    limit: int = 10,
) -> Dict:
    stock_codes, stock_keywords = extract_holding_keywords(fund_code, limit=limit)
    
    # 也提取权重信息用于 search budget
    stock_weights = {}
    try:
        df = _cached_ak_call("fund_portfolio_hold_em", symbol=fund_code, date="2025")
        if df is None:
            df = _cached_ak_call("fund_portfolio_hold_em", symbol=fund_code, date="2024")
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                code = str(row.get("股票代码", "")).strip()
                weight = _parse_float_pct(row.get("占净值比例", 0))
                if code and code.lower() != "nan":
                    stock_weights[code] = weight
    except Exception:
        pass

    profile = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "stock_codes": stock_codes,
        "holding_keywords": stock_keywords,
        "agent_keywords": agent_keywords or [],
        "fallback_keywords": _fallback_fund_keywords(fund_name, fund_type),
        "stock_weights": stock_weights,
    }
    # ... rest unchanged
```

添加辅助函数：

```python
def _parse_float_pct(value) -> float:
    """Parse a percent value to float (e.g. '7.79' → 7.79, '5%' → 5.0)."""
    try:
        raw = str(value).strip()
        if raw.endswith("%"):
            return float(raw[:-1])
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 2: 修改 `fetch_fund_news()` 中对个股新闻的调用**

在 `fetch_fund_news()` 中（约 line 213），按权重分级搜索：

```python
    # 个股新闻接口：重仓股（weight >= 5%）用 stock_news_em，轻仓股跳过
    stock_weights = profile.get("stock_weights", {})
    for code in stock_codes:
        weight = stock_weights.get(code, 0)
        if weight < 2.0:
            continue  # 轻仓股（< 2%）跳过个股新闻接口，减少噪音
        try:
            df = _cached_ak_call("stock_news_em", symbol=code)
            _append_news_from_df(
                all_news, seen, df, cutoff,
                source_hint=f"东方财富个股新闻:{code}",
                max_date=reference_date,
                forced_match_term=code,
            )
        except Exception:
            continue
```

- [ ] **Step 3: 运行现有测试**

Run: `python -m pytest tests/test_news_fetcher.py tests/test_news_pipeline.py -v`
Expected: All PASS（现有测试用 mock 数据，不依赖真实持仓权重）

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/news_fetcher.py
rtk git commit -m "feat(news): prioritize high-weight holdings for stock-specific news fetching"
```

---

### Task 4: Fallback 关键词门控

**Files:**
- Modify: `src/news/news_fetcher.py:162-175` (`build_news_search_profile`)

- [ ] **Step 1: 添加 fallback 禁用条件**

在 `build_news_search_profile()` 中，修改 terms 聚合逻辑：

```python
    terms = []
    # 优先用重仓股名和 Agent 关键词（精准匹配）
    for group in ["holding_keywords", "agent_keywords"]:
        for kw in profile[group]:
            if kw and kw not in terms:
                terms.append(kw)
    # 仅当持仓关键词 < 5 时才启用兜底词（防止泛词污染）
    if len(terms) < 5:
        for kw in profile["fallback_keywords"]:
            if kw and kw not in terms:
                terms.append(kw)
    if fund_code not in terms:
        terms.append(fund_code)
```

**关键变化**：`len(terms) < 3` → `len(terms) < 5`（更保守的阈值，有足够持仓关键词时不启用）。

- [ ] **Step 2: 添加测试**

```python
def test_build_search_profile_skips_fallback_when_sufficient_holdings(self):
    from src.news.news_fetcher import build_news_search_profile
    from unittest.mock import patch
    fake_ak = types.SimpleNamespace()
    fake_ak.fund_portfolio_hold_em = lambda symbol, date: pd.DataFrame([
        {"股票代码": "688256", "股票名称": "寒武纪", "占净值比例": "9.0%"},
        {"股票代码": "688072", "股票名称": "拓荆科技", "占净值比例": "8.0%"},
        {"股票代码": "688123", "股票名称": "聚辰股份", "占净值比例": "7.0%"},
        {"股票代码": "002371", "股票名称": "北方华创", "占净值比例": "7.0%"},
        {"股票代码": "688766", "股票名称": "普冉股份", "占净值比例": "6.0%"},
    ])
    old = sys.modules.get("akshare")
    sys.modules["akshare"] = fake_ak
    try:
        profile = build_news_search_profile("001198", "半导体基金", fund_type="混合型")
    finally:
        if old is not None:
            sys.modules["akshare"] = old
        else:
            sys.modules.pop("akshare", None)
    # 5个持仓关键词，不应启用 fallback（无 "混合型" 等泛词）
    terms = profile["search_terms"]
    for bw in ["半导体", "芯片"]:
        self.assertNotIn(bw, terms)
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_news_fetcher.py::NewsFetcherTest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/news_fetcher.py tests/test_news_fetcher.py
rtk git commit -m "fix(news): raise fallback keyword threshold from 3 to 5 holding keywords"
```

---

### Task 5: `build_news_relevance_task()` — Agent 相关性判断上下文

**Files:**
- Modify: `src/news/agent_context.py`

- [ ] **Step 1: 添加 `build_news_relevance_task()` 函数**

在 `src/news/agent_context.py` 末尾添加：

```python
def build_news_relevance_task(
    fund_name: str,
    fund_code: str,
    entity_profile,
    news_with_catalyst: List[Dict],
) -> Dict:
    """构造新闻相关性判断任务，供 Agent 在执行 skill 时使用。

    任务将持仓信息与候选新闻打包，Agent 需逐条判断是否有实质性投资关联。
    """
    holdings_payload = [
        {"name": h.get("stock_name", ""), "code": h.get("stock_code", ""), "weight_pct": round(h.get("weight", 0) * 100, 2)}
        for h in (getattr(entity_profile, "holdings", []) or [])[:10]
    ]

    candidate_news = []
    for i, n in enumerate(news_with_catalyst[:20]):
        catalyst = n.get("catalyst") or {}
        candidate_news.append({
            "id": i + 1,
            "title": (n.get("title") or "")[:200],
            "content": (n.get("content") or "")[:300],
            "matched_terms": n.get("matched_terms") or [],
            "rule_relevance": catalyst.get("relevance", 0),
            "date": n.get("date", ""),
            "source": n.get("source", ""),
        })

    return {
        "task": "agent_news_relevance",
        "fund_code": fund_code,
        "fund_name": fund_name,
        "instruction": (
            "逐条判断以下新闻与基金持仓是否有实质性投资关联（非泛泛关联）。"
            "实质性关联指：新闻事件直接影响其所持股票的基本面、估值、行业前景或市场情绪。"
            "仅标记能够影响持仓的新闻为 relevant。"
            "以下为泛泛关联（应标记为 irrelevant）："
            "- 新闻提到某公司发布手机但基金持半导体设备和芯片股"
            "- 新闻提到某车企发布新车但基金持上游半导体和材料股"
            "- 泛消费电子新闻与基金持仓无直接产业链关联"
        ),
        "holdings": holdings_payload,
        "candidate_news": candidate_news,
        "expected_output": {
            "relevant_news_ids": [1, 3, 5],
            "per_news_reasons": {
                "2": "小米手机发布与基金持有的美股半导体无直接关联",
                "4": "YU7汽车发布与基金持仓无交集"
            }
        }
    }
```

- [ ] **Step 2: 添加测试**

在 `tests/test_agent_context.py` 末尾添加：

```python
    def test_build_news_relevance_task_includes_holdings_and_news(self):
        from src.news.agent_context import build_news_relevance_task
        from src.news.schemas import EntityProfile

        entity = EntityProfile(
            fund_code="008253",
            fund_name="华宝致远混合A",
            stock_codes=["NVDA", "MU"],
            stock_names=["英伟达", "美光科技"],
            holdings=[
                {"stock_code": "NVDA", "stock_name": "英伟达", "weight": 0.0779},
                {"stock_code": "MU", "stock_name": "美光科技", "weight": 0.0453},
            ],
            sector_keywords=["半导体"],
            theme_keywords=["芯片"],
        )

        news_with_catalyst = [
            {
                "title": "英伟达Q1财报超预期",
                "content": "英伟达发布强劲财报",
                "date": "2026-05-22",
                "source": "财联社",
                "matched_terms": ["英伟达"],
                "catalyst": {"relevance": 0.85, "weighted_score": 0.42},
            },
            {
                "title": "雷军回应重新发布YU7标准版",
                "content": "少了一款竞争产品特别不利",
                "date": "2026-05-22",
                "source": "财联社",
                "matched_terms": ["AI"],
                "catalyst": {"relevance": 0.20, "weighted_score": 0.02},
            },
        ]

        task = build_news_relevance_task("华宝致远混合A", "008253", entity, news_with_catalyst)

        self.assertEqual(task["task"], "agent_news_relevance")
        self.assertEqual(len(task["holdings"]), 2)
        self.assertEqual(task["holdings"][0]["name"], "英伟达")
        self.assertEqual(len(task["candidate_news"]), 2)
        self.assertEqual(task["candidate_news"][0]["rule_relevance"], 0.85)
        self.assertEqual(task["candidate_news"][1]["rule_relevance"], 0.20)
        self.assertIn("实质性投资关联", task["instruction"])
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_agent_context.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/agent_context.py tests/test_agent_context.py
rtk git commit -m "feat(news): add build_news_relevance_task() for agent-side relevance filtering"
```

---

### Task 6: 将 relevance_task 接入 pipeline 和 evidence.json

**Files:**
- Modify: `src/news/pipeline.py`（在 results 中追加 `relevance_task`）
- Modify: `src/cli.py:520-527`（在 evidence.json 的 `news_evidence` 中包含 `relevance_task`）

- [ ] **Step 1: pipeline.py 中追加 `relevance_task`**

在 `src/news/pipeline.py` 的 `results.append(...)` 中（约 line 156），追加一个字段：

```python
        from src.news.agent_context import build_news_relevance_task
        relevance_task = build_news_relevance_task(name, code, entity, catalyst_news)

        results.append({
            "fund_code": code,
            "fund_name": name,
            # ... existing fields ...
            "relevance_task": relevance_task,  # NEW
            "status": "ok",
        })
```

- [ ] **Step 2: cli.py 中追加到 evidence.json**

在 `src/cli.py:520-527`，修改 `news_evidence` 构建：

```python
            "news_evidence": {
                "news_count": news.get("news_count", 0),
                "decayed_lexicon_signal": news.get("sentiment_mean"),
                "brief": news.get("brief") or {},
                "evaluation": news.get("news_evaluation") or {},
                "samples": (news.get("news_list") or [])[:10],
                "post_cutoff_news": news.get("post_cutoff_news") or [],
                "relevance_task": news.get("relevance_task") or {},  # NEW
            },
```

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_news_pipeline.py tests/test_report_agent_decisions.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
rtk git add src/news/pipeline.py src/cli.py
rtk git commit -m "feat(news): integrate relevance_task into pipeline and report.evidence.json"
```

---

### Task 7: SKILL.md 补充相关性判断规则

**Files:**
- Modify: `skills/fund-analyst/SKILL.md`

- [ ] **Step 1: 追加新闻相关性判断规则**

在 `skills/fund-analyst/SKILL.md` 的"新闻关键词规则"章节之后（约 line 148），追加新章节：

```markdown
## 新闻相关性判断规则

Agent 在审核 `report.evidence.json` 中每只基金的 `news_evidence.relevance_task` 时：

1. 逐条读取 `candidate_news`，对照 `holdings`（重仓股清单）。
2. 仅将**直接影响持仓股基本面/估值/行业前景/市场情绪**的新闻视为 relevant。
3. 以下为**泛泛关联**，应主动标记为 irrelevant：
   - 新闻提到某品牌发布手机/汽车/消费电子产品，但基金持有的是上游半导体设备和芯片公司
   - 泛"科技"话题（如"手机只会越来越贵"）与基金具体持仓无产业链关联
   - 纯政策/宏观新闻未直接点明持仓股名称
4. 在 `agent_decisions.json` 的 `news.{code}` 中：
   - `key_news` 仅包含 Agent 判断为高度相关的新闻
   - 对无关新闻主导的基金，`relevance` 降级为 `low`，`impact` 降级为 `neutral` 或 `insufficient_evidence`
   - 如证据稿中提供了 `noise_discarded` 字段，记录被排除的无关新闻数量
```

- [ ] **Step 2: Commit**

```bash
rtk git add skills/fund-analyst/SKILL.md
rtk git commit -m "docs(skill): add news relevance filtering rules to fund-analyst skill"
```

---

### Task 8: 全量测试验证

**Files:** (no code changes, verification only)

- [ ] **Step 1: 运行所有新闻相关测试**

```bash
python -m pytest tests/test_news_fetcher.py tests/test_news_pipeline.py tests/test_news_evaluator.py tests/test_agent_context.py -v
```
Expected: All tests PASS

- [ ] **Step 2: 运行全量测试**

```bash
python -m pytest tests/ -v
```
Expected: All tests PASS

- [ ] **Step 3: 模拟分析验证（不写入文件）**

```bash
python -m src.cli analyze -c fund-portfolio.yaml --no-news --no-snapshot-after 2>&1 | head -5
```
Expected: 正常启动（不依赖网络）

---

### 自评审

1. **Spec 覆盖检查**：
   - Layer 1 所有 5 个子项：Task 1（词边界）、Task 2（关键词白名单缩窄）、Task 3（权重预算）、Task 4（fallback 门控）→ 全部对应
   - Layer 2：Task 5（`build_news_relevance_task`）、Task 6（接入 pipeline/evidence）、Task 7（SKILL.md 规则补充）→ 全部对应

2. **占位符检查**：无 "TBD"、"TODO"、抽象描述。所有步骤均含具体代码。

3. **类型一致性检查**：
   - Task 2 `_SECTOR_KEYWORD_MAP` 键名同步到 Task 2 `_INDUSTRY_THEME_MAP`
   - Task 5 `from src.news.schemas import EntityProfile` 与现有代码一致
   - Task 5 `build_news_relevance_task` 签名与 Task 6 调用匹配
