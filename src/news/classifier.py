"""Phase 2 Classifier: 6-layer news classification.

Assigns each news item to one of 6 layers based on entity matching
against fund holdings, industries, themes, and macro signals.
"""
from __future__ import annotations

from src.news.schemas import NewsLayer, SearchPlan, ClassifiedNews


# Keywords that trigger macro/policy classification
_POLICY_MACRO_KEYWORDS = [
    "央行", "利率", "降息", "加息", "LPR", "美联储", "FOMC",
    "政策", "监管", "宏观", "GDP", "CPI", "PMI", "国债",
    "汇率", "人民币", "美元", "调控", "刺激", "税",
]

# Keywords that trigger overseas classification
_OVERSEAS_KEYWORDS = [
    "纳斯达克", "标普", "道琼斯", "美股", "港股", "恒生",
    "日经", "欧洲", "美股科技", "海外", "全球市场",
    "新兴市场", "QDII",
]

# Keywords that trigger black swan classification
_BLACK_SWAN_KEYWORDS = [
    "崩盘", "暴跌", "系统性风险", "黑天鹅", "金融危机",
    "战争", "冲突", "灾难", "疫情", "封锁",
]


class Classifier:
    """6-layer news classifier: assigns each news item to a relevance layer."""

    # Layer weights as defined in the design spec
    LAYER_WEIGHTS = {
        NewsLayer.FUND_DIRECT: 1.0,
        NewsLayer.HEAVY_HOLDING: 0.8,
        NewsLayer.INDUSTRY: 0.5,
        NewsLayer.POLICY_MACRO: 0.3,
        NewsLayer.OVERSEAS: 0.2,
        NewsLayer.BLACK_SWAN: 0.6,  # Variable, but default high
    }

    def classify_news(
        self,
        news_items: list[dict],
        search_plan: SearchPlan,
        fund_code: str,
    ) -> list[ClassifiedNews]:
        """Classify a list of raw news items into 6 layers.

        Classification priority (highest to lowest):
          1. FUND_DIRECT   — fund code or name in title/content
          2. HEAVY_HOLDING — heavy holding stock (>=5%) mentioned
          3. INDUSTRY      — sector or theme keyword match
          4. POLICY_MACRO  — macro/policy keywords matched
          5. OVERSEAS      — overseas market keywords matched
          6. BLACK_SWAN    — black swan / risk event keywords

        Args:
            news_items: Raw news dicts with title, content, date.
            search_plan: SearchPlan from KG for this fund.
            fund_code: Fund code being analyzed.

        Returns:
            List of ClassifiedNews with layer and metadata.
        """
        results = []

        # Build lookup sets
        stock_set = {s.lower() if s else "" for s in search_plan.stocks}
        stock_name_set = {n.lower() if n else "" for n in getattr(search_plan, "stock_names", [])}
        heavy_set = {h.lower() if h else "" for h in search_plan.heavy_holdings}
        fund_name_full = (search_plan.fund_name or "").lower()
        fund_code_lower = fund_code.lower()
        # Extract core fund name (strip common suffixes like "混合", "股票", "债券", etc.)
        fund_name_core = self._core_name(fund_name_full)

        for item in news_items:
            title = (item.get("title") or "").lower()
            content = (item.get("content") or "").lower()
            text = title + " " + content

            classified = ClassifiedNews(
                title=item.get("title", ""),
                content=item.get("content", ""),
                date=item.get("date", ""),
                source=item.get("source", ""),
                url=item.get("url", ""),
                fund_code=fund_code,
                raw=item,
            )

            # Layer 1: Fund-direct match
            if self._is_fund_direct(text, fund_code_lower, fund_name_core):
                classified.layer = NewsLayer.FUND_DIRECT
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.FUND_DIRECT]
                classified.matched_entity = fund_code
                classified.entity_type = "fund"
                results.append(classified)
                continue

            # Layer 2: Heavy holding stock match (by code or name)
            matched_heavy = self._match_stock(text, heavy_set, stock_name_set)
            if matched_heavy:
                classified.layer = NewsLayer.HEAVY_HOLDING
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.HEAVY_HOLDING]
                classified.matched_entity = matched_heavy.upper()
                classified.entity_type = "stock"
                results.append(classified)
                continue

            # Layer 2b: Regular stock match (not heavy, but still holding)
            matched_stock = self._match_stock(text, stock_set, stock_name_set)
            if matched_stock:
                classified.layer = NewsLayer.HEAVY_HOLDING
                classified.weight = 0.6  # Slightly lower than heavy
                classified.matched_entity = matched_stock.upper()
                classified.entity_type = "stock"
                results.append(classified)
                continue

            # Layer 6: Black swan (check before lower-priority layers)
            if self._match_keywords(text, _BLACK_SWAN_KEYWORDS):
                classified.layer = NewsLayer.BLACK_SWAN
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.BLACK_SWAN]
                classified.matched_entity = "black_swan"
                classified.entity_type = "event"
                results.append(classified)
                continue

            # Layer 3: Industry/theme match
            sector_match = self._match_entity(text, search_plan.sectors)
            theme_match = self._match_entity(text, search_plan.themes)
            if sector_match or theme_match:
                classified.layer = NewsLayer.INDUSTRY
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.INDUSTRY]
                classified.matched_entity = sector_match or theme_match or ""
                classified.entity_type = "industry"
                results.append(classified)
                continue

            # Layer 4: Policy/macro match
            if self._match_keywords(text, _POLICY_MACRO_KEYWORDS):
                classified.layer = NewsLayer.POLICY_MACRO
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.POLICY_MACRO]
                classified.matched_entity = "macro"
                classified.entity_type = "macro"
                results.append(classified)
                continue

            # Layer 5: Overseas match
            if self._match_keywords(text, _OVERSEAS_KEYWORDS):
                classified.layer = NewsLayer.OVERSEAS
                classified.weight = self.LAYER_WEIGHTS[NewsLayer.OVERSEAS]
                classified.matched_entity = "overseas"
                classified.entity_type = "market"
                results.append(classified)
                continue

            # Default: classify as INDUSTRY with low weight for general market news
            classified.layer = NewsLayer.INDUSTRY
            classified.weight = 0.1
            classified.matched_entity = "general"
            classified.entity_type = "unknown"
            results.append(classified)

        return results

    def _is_fund_direct(self, text: str, fund_code: str, fund_name_core: str) -> bool:
        """Check if text directly references the fund."""
        if fund_code and fund_code in text:
            return True
        if fund_name_core and len(fund_name_core) >= 3 and fund_name_core in text:
            return True
        return False

    def _core_name(self, fund_name: str) -> str:
        """Extract core fund name by stripping common suffixes."""
        for suffix in ["混合", "股票", "债券", "指数", "货币", "保本", "QDII", "ETF", "LOF", "分级"]:
            fund_name = fund_name.replace(suffix, "")
        for suffix in ["A", "C", "B", "R1", "R2", "R3", "R4", "R5"]:
            if fund_name.endswith(f"({suffix})") or fund_name.endswith(f"（{suffix}）"):
                fund_name = fund_name.rsplit("(", 1)[0] if "(" in fund_name else fund_name.split("（")[0]
        return fund_name.strip()

    def _match_stock(self, text: str, stock_codes: set, stock_names: set = None) -> str | None:
        """Match stock codes or names in text. Returns matched entity or None."""
        # Match by stock code
        for code in stock_codes:
            if not code:
                continue
            if code in text:
                return code

        # Match by stock name
        if stock_names:
            for name in stock_names:
                if not name or len(name) < 2:
                    continue
                if name in text:
                    return name

        return None

    def _match_entity(self, text: str, entities: list[str]) -> str | None:
        """Match entity names (sectors, themes) in text.
        
        Returns matched entity or None.
        """
        for entity in entities:
            if not entity:
                continue
            if entity.lower() in text:
                return entity
        return None

    def _match_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if any keyword appears in text."""
        return any(kw in text for kw in keywords if kw)
