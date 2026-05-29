"""Phase 2 Scorer: Multi-factor relevance scoring + vector reranking.

Uses KG query_relevance() for holding/industry/theme overlap,
adds timeliness decay and sentiment severity, then reranks with vectors.
"""
from __future__ import annotations

import math
from datetime import date, datetime

import networkx as nx

from legacy.news.schemas import NewsLayer, ScoredNews, ClassifiedNews
from src.graph.schema import KGEdgeType
from src.graph.industry_map import get_keywords_for_theme
from src.infra.vectorstore.search import cosine_similarity


class Scorer:
    """Multi-factor news relevance scorer with optional vector reranking."""

    def __init__(self, timeliness_lambda: float = 0.1):
        """Initialize scorer.

        Args:
            timeliness_lambda: Exponential decay constant for news age.
                Default 0.1 means news loses ~10% value per day.
        """
        self.timeliness_lambda = timeliness_lambda

    def score_relevance(
        self,
        classified_news: list[ClassifiedNews],
        fund_code: str,
        graph: nx.DiGraph,
    ) -> list[ScoredNews]:
        """Score relevance for classified news items using KG multi-factor analysis.

        Multi-factor weights (from design spec):
          holding_overlap × 0.25 + top10_hit × 0.20 + industry_hit × 0.15
          + theme_hit × 0.10 + timeliness × 0.10 + sentiment_severity × 0.10
          + nav_correlation × 0.10 (reserved, default 0)

        Args:
            classified_news: News items classified into layers.
            fund_code: Fund code being analyzed.
            graph: NetworkX KG.

        Returns:
            ScoredNews list with multi-factor relevance scores.
        """
        fund_id = f"fund:{fund_code}"
        results = []

        for cn in classified_news:
            scored = ScoredNews(
                title=cn.title,
                content=cn.content,
                date=cn.date,
                source=cn.source,
                url=cn.url,
                layer=cn.layer,
                weight=cn.weight,
                fund_code=cn.fund_code,
            )

            # 1. Holding overlap — check if news entity matches fund's holdings
            scored.holding_overlap = self._compute_holding_overlap(
                graph, fund_id, cn
            )

            # 2. Top-10 hit — is the matched entity a top-10 holding?
            scored.top10_hit = self._is_top10_hit(graph, fund_id, cn)

            # 3. Industry hit — does news relate to fund's industry exposure?
            scored.industry_hit = self._check_industry_hit(graph, fund_id, cn)

            # 4. Theme hit — does news relate to fund's investment themes?
            scored.theme_hit = self._check_theme_hit(graph, fund_id, cn)

            # 5. Timeliness — exponential decay from publication date
            scored.timeliness = self._compute_timeliness(cn.date)

            # 6. Sentiment severity — default 0.5
            scored.sentiment_severity = 0.5  # Reserved for sentiment analysis

            # Compute combined relevance score using design weights
            scored.relevance_score = (
                scored.holding_overlap * 0.25
                + (1.0 if scored.top10_hit else 0.0) * 0.20
                + (1.0 if scored.industry_hit else 0.0) * 0.15
                + (1.0 if scored.theme_hit else 0.0) * 0.10
                + scored.timeliness * 0.10
                + scored.sentiment_severity * 0.10
                + 0.0 * 0.10  # nav_correlation reserved
            )
            # Clamp to [0, 1]
            scored.relevance_score = min(1.0, max(0.0, scored.relevance_score))

            results.append(scored)

        return results

    def rerank_with_vectors(
        self,
        scored_news: list[ScoredNews],
        fund_code: str,
        embedding_pipeline=None,
        top_k: int = 20,
    ) -> list[ScoredNews]:
        """Rerank scored news using vector similarity.

        When embedding_pipeline is available:
          fund_profile = f"fund:{fund_code} holdings style industry"
          combined_score = relevance × 0.6 + cosine_similarity × 0.4

        Without embedding_pipeline (default):
          vector_score = 0.5 (neutral)
          combined_score follows same formula

        Results sorted by combined_score descending, limited to top_k.

        Args:
            scored_news: News items with relevance scores.
            fund_code: Fund code for profile embedding.
            embedding_pipeline: Optional EmbeddingPipeline for vector embeddings.
            top_k: Maximum results to return.

        Returns:
            Reranked ScoredNews list sorted by combined_score.
        """
        if embedding_pipeline is not None:
            # Build fund profile text for embedding query
            fund_profile = f"fund:{fund_code} holdings style industry theme"

            # Get news title embeddings
            titles = [sn.title for sn in scored_news]
            try:
                title_vectors = embedding_pipeline.embed_batch(titles)
                fund_vector = embedding_pipeline.embed(fund_profile)

                for sn, tv in zip(scored_news, title_vectors):
                    sn.vector_score = cosine_similarity(tv, fund_vector)
            except Exception:
                # Fallback: neutral vector scores
                for sn in scored_news:
                    sn.vector_score = 0.5
        else:
            # No embedding pipeline: default neutral
            for sn in scored_news:
                sn.vector_score = 0.5

        # Compute combined scores
        for sn in scored_news:
            sn.combined_score = (
                sn.relevance_score * 0.6 + sn.vector_score * 0.4
            )

        # Sort by combined score descending
        scored_news.sort(key=lambda x: x.combined_score, reverse=True)

        return scored_news[:top_k]

    # ── Private helpers ────────────────────────────────────────────

    def _compute_holding_overlap(
        self, graph: nx.DiGraph, fund_id: str, cn: ClassifiedNews
    ) -> float:
        """Compute holding overlap score.

        1.0 if the news entity directly matches a holding,
        0.5 if partial match via matched_entity, otherwise 0.
        """
        if not graph.has_node(fund_id):
            return 0.0

        entity = (cn.matched_entity or "").lower()
        if not entity:
            return 0.0

        # Check all holding edges
        for _, dst, edge_data in graph.edges(fund_id, data=True):
            edge = edge_data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.HOLDS:
                stock_code = dst.replace("stock:", "").lower()
                if entity == stock_code or stock_code in entity:
                    return 1.0
                # Partial: check if entity appears in stock name
                stock_data = graph.nodes[dst].get("data")
                if stock_data:
                    stock_name = (getattr(stock_data, "name", "") or "").lower()
                    if entity in stock_name or stock_name in entity:
                        return 0.5

        return 0.0

    def _is_top10_hit(
        self, graph: nx.DiGraph, fund_id: str, cn: ClassifiedNews
    ) -> bool:
        """Check if matched entity is a top-10 holding (by weight)."""
        if not graph.has_node(fund_id):
            return False

        entity = (cn.matched_entity or "").lower()
        if not entity:
            return False

        # Collect holdings with weights, sorted by weight desc
        holdings = []
        for _, dst, edge_data in graph.edges(fund_id, data=True):
            edge = edge_data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.HOLDS:
                stock_code = dst.replace("stock:", "")
                holdings.append((stock_code.lower(), edge.weight or 0))

        holdings.sort(key=lambda x: x[1], reverse=True)
        top10 = [code for code, _ in holdings[:10]]

        return entity in top10

    def _check_industry_hit(
        self, graph: nx.DiGraph, fund_id: str, cn: ClassifiedNews
    ) -> bool:
        """Check if news relates to fund's industry exposure."""
        if not graph.has_node(fund_id):
            return False

        entity = (cn.matched_entity or "").lower()
        entity_type = (cn.entity_type or "").lower()
        if not entity:
            return False

        # Direct industry match
        if entity_type == "industry":
            return True

        # Check EXPOSES edges for industry names
        for _, dst, edge_data in graph.edges(fund_id, data=True):
            edge = edge_data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.EXPOSES:
                ind_name = dst.replace("industry:sw_", "").lower()
                if entity in ind_name or ind_name in entity:
                    return True

        # Check news title/content for industry keywords
        text = (cn.title + " " + cn.content).lower()
        for _, dst, _ in graph.edges(fund_id, data=True):
            edge = graph.get_edge_data(fund_id, dst)
            if edge:
                edge_inner = edge.get("edge_data")
                if edge_inner and edge_inner.edge_type == KGEdgeType.EXPOSES:
                    ind_name = dst.replace("industry:sw_", "").lower()
                    if ind_name in text:
                        return True

        return False

    def _check_theme_hit(
        self, graph: nx.DiGraph, fund_id: str, cn: ClassifiedNews
    ) -> bool:
        """Check if news relates to fund's investment themes."""
        if not graph.has_node(fund_id):
            return False

        text = (cn.title + " " + cn.content).lower()

        # Traverse: fund → industry → theme
        for _, ind_dst, _ in graph.edges(fund_id, data=True):
            for _, theme_dst, _ in graph.edges(ind_dst, data=True):
                theme_name = theme_dst.replace("theme:", "").lower()
                if theme_name in text:
                    return True
                # Check theme keywords
                keywords = get_keywords_for_theme(theme_name) if theme_name else []
                for kw in keywords:
                    if kw.lower() in text:
                        return True

        return False

    def _compute_timeliness(self, date_str: str) -> float:
        """Compute timeliness using exponential decay from publication date.

        timeliness = exp(-lambda * days_old)
        """
        if not date_str:
            return 1.0

        try:
            # Parse date
            news_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            days_old = (date.today() - news_date).days
            days_old = max(0, days_old)
        except (ValueError, IndexError):
            return 1.0

        return math.exp(-self.timeliness_lambda * days_old)
