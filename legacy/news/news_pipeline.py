"""Phase 2 NewsPipeline: 8-stage holdings-driven news processing pipeline.

Orchestrates: entity extraction → retrieval → classification → scoring
→ vector reranking → AI reranking → summarization → event extraction.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from legacy.news.schemas import SearchPlan, NewsLayer
from legacy.news.retriever import Retriever
from legacy.news.classifier import Classifier
from legacy.news.scorer import Scorer
from legacy.news.summarizer import Summarizer
from legacy.events.extractor import extract_events_from_text

logger = logging.getLogger(__name__)

# All 8 stages in order
PIPELINE_STAGES = [
    "entity_extraction",      # Stage 1:  Build SearchPlan from KG
    "targeted_retrieval",     # Stage 2:  Fetch news per stock/entity
    "layer_classification",   # Stage 3:  Classify into 6 layers
    "relevance_scoring",      # Stage 4:  Multi-factor relevance scoring
    "vector_reranking",       # Stage 5:  Vector similarity reranking
    "ai_reranking",           # Stage 6:  AI reranking (reserved)
    "research_summary",       # Stage 7:  Research-style AI summary
    "event_extraction",       # Stage 8:  Extract structured events
]


class NewsPipeline:
    """Holdings-driven news pipeline orchestrator with 8 stages.

    Replaces the keyword-based pipeline with a KG+vector+AI pipeline.
    Coordinates Retriever, Classifier, Scorer, Summarizer, and EventExtractor.
    """

    def __init__(
        self,
        llm_client: Any = None,
        embedding_pipeline=None,
        vector_store=None,
        finnhub_client=None,
        tavily_client=None,
    ):
        """Initialize pipeline with optional AI components.

        When LLM/vector components are None, pipeline uses rule-based fallbacks.

        Args:
            llm_client: OpenAI-compatible client for AI summarization.
            embedding_pipeline: EmbeddingPipeline for vector reranking.
            vector_store: Qdrant client (reserved).
            finnhub_client: FinnhubNewsClient for US stock news (optional).
            tavily_client: TavilySearchClient for AI research supplement (optional).
        """
        self.retriever = Retriever()
        self.classifier = Classifier()
        self.scorer = Scorer()
        self.summarizer = Summarizer()
        self.llm_client = llm_client
        self.embedding_pipeline = embedding_pipeline
        self.vector_store = vector_store
        self.finnhub_client = finnhub_client
        self.tavily_client = tavily_client

    def run(
        self,
        fund_codes: list[str],
        graph: nx.DiGraph,
        vector_store=None,
    ) -> dict[str, dict]:
        """Run the full pipeline for one or more funds.

        Args:
            fund_codes: List of fund codes to process.
            graph: Knowledge graph (NetworkX DiGraph).
            vector_store: Optional Qdrant client.

        Returns:
            Dict mapping fund_code → pipeline results dict with keys:
                search_plan, classified_news, scored_news,
                research_summaries, events, stages_completed
        """
        results = {}

        for fund_code in fund_codes:
            fund_result = self._run_single_fund(fund_code, graph)
            results[fund_code] = fund_result

        return results

    def _run_single_fund(
        self,
        fund_code: str,
        graph: nx.DiGraph,
    ) -> dict:
        """Run all 8 stages for a single fund.

        Returns dict with per-stage outputs and metadata.
        """
        stages_completed = []

        # ── Stage 1: Entity extraction ──────────────────────────
        search_plan = self.retriever.build_search_plan(fund_code, graph)
        stages_completed.append("entity_extraction")

        # ── Stage 2: Targeted retrieval ─────────────────────────
        raw_news = []
        seen_titles = set()

        # Retrieve per-stock news for heavy holdings first
        for stock in search_plan.heavy_holdings:
            try:
                stock_news = self.retriever.retrieve_stock_news(stock)
                for item in stock_news:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        raw_news.append(item)
            except Exception as e:
                logger.debug(f"Failed to retrieve news for stock {stock}: {e}")

        # Retrieve for regular holdings
        for stock in search_plan.stocks:
            if stock in search_plan.heavy_holdings:
                continue  # Already fetched
            try:
                stock_news = self.retriever.retrieve_stock_news(stock)
                for item in stock_news:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        raw_news.append(item)
            except Exception as e:
                logger.debug(f"Failed to retrieve news for stock {stock}: {e}")

        # Retrieve market news for macro/theme queries
        if search_plan.macro_queries:
            try:
                market_news = self.retriever.retrieve_market_news(
                    search_plan.macro_queries[:10]
                )
                for item in market_news:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        raw_news.append(item)
            except Exception as e:
                logger.debug(f"Failed to retrieve market news: {e}")

        stages_completed.append("targeted_retrieval")

        # ── Stage 2b: Finnhub US stock news (QDII holdings) ─────
        if self.finnhub_client:
            for stock in search_plan.stocks:
                try:
                    us_news = self.finnhub_client.get_company_news(stock, days=7)
                    for item in us_news:
                        if item["title"] not in seen_titles:
                            seen_titles.add(item["title"])
                            raw_news.append(item)
                except Exception as e:
                    logger.debug(f"Finnhub news failed for {stock}: {e}")

        # ── Stage 2c: Tavily supplementary search ───────────────
        if self.tavily_client and search_plan.macro_queries:
            for query in search_plan.macro_queries[:3]:
                try:
                    tav_news = self.tavily_client.search_news(query, days=7, max_results=3)
                    for item in tav_news:
                        if item["title"] not in seen_titles:
                            seen_titles.add(item["title"])
                            raw_news.append(item)
                except Exception as e:
                    logger.debug(f"Tavily search failed for '{query}': {e}")

        if not raw_news:
            return {
                "search_plan": search_plan,
                "classified_news": [],
                "scored_news": [],
                "research_summaries": [],
                "events": [],
                "stages_completed": ["entity_extraction", "targeted_retrieval"],
            }

        # ── Stage 3: News layer classification ──────────────────
        classified_news = self.classifier.classify_news(
            raw_news, search_plan, fund_code
        )
        stages_completed.append("layer_classification")

        # ── Stage 4: Relevance scoring ──────────────────────────
        scored_news = self.scorer.score_relevance(
            classified_news, fund_code, graph
        )
        stages_completed.append("relevance_scoring")

        # ── Stage 5: Vector reranking ───────────────────────────
        scored_news = self.scorer.rerank_with_vectors(
            scored_news,
            fund_code,
            embedding_pipeline=self.embedding_pipeline,
        )
        stages_completed.append("vector_reranking")

        # ── Stage 6: AI reranking (reserved) ────────────────────
        # Future: LLM reranks top-20 with impact assessment
        stages_completed.append("ai_reranking")

        # ── Stage 7: Research-style summary ─────────────────────
        research_summaries = self.summarizer.summarize_news(
            scored_news, fund_code, llm_client=self.llm_client
        )
        stages_completed.append("research_summary")

        # ── Stage 8: Event extraction ───────────────────────────
        events = []
        for sn in scored_news[:10]:  # Top 10 by relevance
            text = f"{sn.title} {sn.content}"
            extracted = extract_events_from_text(text, llm_client=self.llm_client)
            events.extend(extracted)
        stages_completed.append("event_extraction")

        return {
            "search_plan": search_plan,
            "classified_news": classified_news,
            "scored_news": scored_news,
            "research_summaries": research_summaries,
            "events": events,
            "raw_news_count": len(raw_news),
            "stages_completed": stages_completed,
        }
