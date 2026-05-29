"""Phase 2 Summarizer: Research-style AI summary for news impact analysis.

Each summary answers structured questions about a news item's impact on a fund.
LLM-based when available, with rule-based fallback.
"""
from __future__ import annotations

import json
from typing import Any

from legacy.news.schemas import NewsLayer, ScoredNews, ResearchSummary


class Summarizer:
    """Generate research-style structured summaries for news items.

    When LLM is available, produces high-quality analytical summaries.
    Otherwise falls back to rule-based template generation.
    """

    _SUMMARY_PROMPT = """你是一位基金研究员。请分析以下新闻对该基金的影响。

基金代码: {fund_code}

新闻标题: {title}
新闻内容: {content}
新闻层级: {layer}
相关性得分: {relevance_score}

请用 JSON 格式回答（只返回 JSON，不要其他内容）：
{{
    "what": "新闻内容，简洁概括发生了什么事件",
    "why_important": "为什么这条新闻对该基金重要",
    "fund_impact": "对基金净值/持仓的影响评估",
    "affected_holdings": ["受影响的持仓股票代码列表"],
    "time_horizon": "short/medium/long",
    "risk_opportunity": "risk/opportunity/neutral",
    "suggested_action": "建议关注/操作",
    "confidence": 0.0到1.0之间的信度值
}}"""

    def summarize_news(
        self,
        scored_news: list[ScoredNews],
        fund_code: str,
        llm_client: Any = None,
    ) -> list[ResearchSummary]:
        """Generate structured summaries for scored news items.

        Args:
            scored_news: Scored news items sorted by relevance.
            fund_code: Fund code.
            llm_client: Optional OpenAI-compatible client. If None, uses rule-based.

        Returns:
            ResearchSummary list, one per news item.
        """
        if not scored_news:
            return []

        summaries = []
        for sn in scored_news:
            if llm_client is not None:
                try:
                    summary = self._llm_summary(sn, fund_code, llm_client)
                except Exception:
                    # Fall back to rule-based on LLM error
                    summary = self._rule_based_summary(sn, fund_code)
            else:
                summary = self._rule_based_summary(sn, fund_code)

            summaries.append(summary)

        return summaries

    def _llm_summary(
        self,
        sn: ScoredNews,
        fund_code: str,
        llm_client: Any,
    ) -> ResearchSummary:
        """Generate summary using LLM."""
        prompt = self._SUMMARY_PROMPT.format(
            fund_code=fund_code,
            title=sn.title,
            content=sn.content,
            layer=sn.layer.value,
            relevance_score=f"{sn.relevance_score:.2f}",
        )

        response = llm_client.chat.completions.create(
            model="deepseek-v4-flash-free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )

        content = response.choices[0].message.content

        # Parse JSON from response
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._rule_based_summary(sn, fund_code)
            else:
                return self._rule_based_summary(sn, fund_code)

        return ResearchSummary(
            fund_code=fund_code,
            news_title=sn.title,
            what=data.get("what", sn.title),
            why_important=data.get("why_important", "对基金持仓有影响"),
            fund_impact=data.get("fund_impact", ""),
            affected_holdings=data.get("affected_holdings", []),
            time_horizon=data.get("time_horizon", "medium"),
            risk_opportunity=data.get("risk_opportunity", "neutral"),
            suggested_action=data.get("suggested_action", "关注"),
            confidence=data.get("confidence", 0.5),
            source="llm",
        )

    def _rule_based_summary(
        self,
        sn: ScoredNews,
        fund_code: str,
    ) -> ResearchSummary:
        """Generate rule-based summary when LLM is unavailable.

        Uses layer, relevance score, and keyword matching to produce
        template-based structured analysis.
        """
        title = sn.title
        content = sn.content
        layer = sn.layer
        text = (title + " " + content).lower()

        # Determine what happened
        what = self._extract_what(title, text, layer)

        # Determine why it's important
        why_important = self._extract_why(layer, sn.relevance_score)

        # Determine fund impact
        fund_impact = self._extract_fund_impact(layer, text)

        # Determine affected holdings (from KG overlay via matched entity)
        affected_holdings = []
        if sn.top10_hit:
            affected_holdings.append("重仓股")

        # Time horizon based on layer
        time_horizon_map = {
            NewsLayer.FUND_DIRECT: "short",
            NewsLayer.HEAVY_HOLDING: "short",
            NewsLayer.INDUSTRY: "medium",
            NewsLayer.POLICY_MACRO: "medium",
            NewsLayer.OVERSEAS: "short",
            NewsLayer.BLACK_SWAN: "short",
        }
        time_horizon = time_horizon_map.get(layer, "medium")

        # Risk / opportunity assessment
        risk_opportunity = self._assess_risk_opportunity(text, sn.relevance_score)

        # Suggested action
        suggested_action = self._suggest_action(layer, sn.relevance_score, risk_opportunity)

        return ResearchSummary(
            fund_code=fund_code,
            news_title=title,
            what=what,
            why_important=why_important,
            fund_impact=fund_impact,
            affected_holdings=affected_holdings,
            time_horizon=time_horizon,
            risk_opportunity=risk_opportunity,
            suggested_action=suggested_action,
            confidence=sn.relevance_score,
            source="rule_based",
        )

    def _extract_what(self, title: str, text: str, layer: NewsLayer) -> str:
        """Extract what happened from news title/context."""
        if layer in (NewsLayer.FUND_DIRECT, NewsLayer.HEAVY_HOLDING):
            return title
        elif layer == NewsLayer.BLACK_SWAN:
            return f"风险事件: {title}"
        elif layer == NewsLayer.POLICY_MACRO:
            return f"宏观政策: {title}"
        elif layer == NewsLayer.OVERSEAS:
            return f"海外市场: {title}"
        return title

    def _extract_why(self, layer: NewsLayer, relevance: float) -> str:
        """Extract why this news is important."""
        if relevance >= 0.8:
            base = "直接且重大地"
        elif relevance >= 0.5:
            base = "有一定程度地"
        else:
            base = "间接地"

        reasons = {
            NewsLayer.FUND_DIRECT: f"{base}影响基金净值走势",
            NewsLayer.HEAVY_HOLDING: f"{base}影响基金重仓股走势",
            NewsLayer.INDUSTRY: f"{base}影响基金行业配置",
            NewsLayer.POLICY_MACRO: f"{base}影响宏观经济环境和投资策略",
            NewsLayer.OVERSEAS: f"{base}影响海外投资环境和风险偏好",
            NewsLayer.BLACK_SWAN: f"{base}影响市场系统性风险",
        }
        return reasons.get(layer, f"{base}影响基金投资组合")

    def _extract_fund_impact(self, layer: NewsLayer, text: str) -> str:
        """Assess news impact on fund."""
        # Keyword-based impact assessment
        positive_words = ["涨", "增长", "超预期", "利好", "突破", "上升", "回暖", "复苏"]
        negative_words = ["跌", "下降", "低于预期", "利空", "下滑", "崩盘", "危机", "风险", "降息"]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        if pos_count > neg_count:
            direction = "正向"
        elif neg_count > pos_count:
            direction = "负向"
        else:
            direction = "中性"

        impact_map = {
            NewsLayer.FUND_DIRECT: f"对基金净值产生{direction}影响",
            NewsLayer.HEAVY_HOLDING: f"对重仓股走势产生{direction}拉动",
            NewsLayer.INDUSTRY: f"对行业配置产生{direction}影响",
            NewsLayer.POLICY_MACRO: f"对基金投资环境产生{direction}影响",
            NewsLayer.OVERSEAS: f"对海外投资产生{direction}影响",
            NewsLayer.BLACK_SWAN: "可能引发系统性风险，建议密切关注",
        }
        return impact_map.get(layer, f"产生{direction}影响")

    def _assess_risk_opportunity(self, text: str, relevance: float) -> str:
        """Assess whether news represents risk or opportunity."""
        positive_words = ["涨", "增长", "超预期", "利好", "突破", "上升", "回暖"]
        negative_words = ["跌", "下降", "崩盘", "风险", "危机", "利空", "暴跌"]

        pos = sum(1 for w in positive_words if w in text)
        neg = sum(1 for w in negative_words if w in text)

        if pos > neg:
            return "opportunity"
        elif neg > pos:
            return "risk"
        return "neutral"

    def _suggest_action(
        self,
        layer: NewsLayer,
        relevance: float,
        risk_opportunity: str,
    ) -> str:
        """Suggest action based on layer, relevance, and risk assessment."""
        if relevance < 0.3:
            return "可不关注"

        if risk_opportunity == "risk":
            if layer in (NewsLayer.HEAVY_HOLDING, NewsLayer.FUND_DIRECT):
                return "密切观察，关注风险管理"
            return "关注风险信号"

        if risk_opportunity == "opportunity":
            if layer in (NewsLayer.HEAVY_HOLDING, NewsLayer.FUND_DIRECT):
                return "关注机会，可适当加仓"
            return "关注机会信号"

        # Neutral
        if layer in (NewsLayer.FUND_DIRECT, NewsLayer.HEAVY_HOLDING):
            return "持有观察"
        elif layer == NewsLayer.BLACK_SWAN:
            return "紧急关注，评估减仓需要"
        elif layer == NewsLayer.POLICY_MACRO:
            return "关注政策走向"
        elif layer == NewsLayer.OVERSEAS:
            return "关注海外市场动态"
        return "关注"
