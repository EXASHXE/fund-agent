import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.news.keyword_cache import (
    build_keyword_request,
    load_valid_keyword_cache,
)


class NewsKeywordCacheTest(unittest.TestCase):
    def test_load_valid_cache_requires_same_holdings_and_recent_quarter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news_keyword_profiles.json"
            path.write_text(json.dumps({
                "cache_version": "news_keyword_profiles.v1",
                "generated_at": "2026-04-01",
                "holding_codes": ["001198", "017436"],
                "funds": {
                    "001198": {"keywords": ["寒武纪", "AI芯片"]},
                    "017436": {"keywords": ["英伟达", "纳斯达克"]},
                },
            }, ensure_ascii=False), encoding="utf-8")

            cache = load_valid_keyword_cache(
                str(path),
                ["017436", "001198"],
                today=date(2026, 5, 19),
            )

            self.assertEqual(cache["funds"]["001198"]["keywords"], ["寒武纪", "AI芯片"])

    def test_load_valid_cache_rejects_changed_holdings_or_expired_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "news_keyword_profiles.json"
            path.write_text(json.dumps({
                "cache_version": "news_keyword_profiles.v1",
                "generated_at": "2026-01-01",
                "holding_codes": ["001198", "017436"],
                "funds": {
                    "001198": {"keywords": ["寒武纪"]},
                    "017436": {"keywords": ["英伟达"]},
                },
            }, ensure_ascii=False), encoding="utf-8")

            self.assertIsNone(load_valid_keyword_cache(str(path), ["001198"], today=date(2026, 5, 19)))
            self.assertIsNone(load_valid_keyword_cache(str(path), ["001198", "017436"], today=date(2026, 5, 19)))

    def test_build_keyword_request_contains_holdings_sectors_and_tags(self):
        config = SimpleNamespace(holdings=[
            SimpleNamespace(code="001198", name="东方惠灵活配置混合A", type="domestic"),
        ])
        analyzer = SimpleNamespace(funds={
            "001198": {
                "basic": {"name": "东方惠灵活配置混合A", "fund_type": "混合型"},
                "holdings": pd.DataFrame([
                    {"股票代码": "688256", "股票名称": "寒武纪", "占净值比例": "8.2%"},
                ]),
                "sectors": pd.DataFrame([
                    {"行业": "半导体", "占比": "35%"},
                ]),
            }
        })

        request = build_keyword_request(config, analyzer, report_date=date(2026, 5, 19))

        fund = request["funds"][0]
        self.assertEqual(request["request_version"], "news_keyword_request.v1")
        self.assertEqual(fund["fund_code"], "001198")
        self.assertEqual(fund["top_holdings"][0]["stock_name"], "寒武纪")
        self.assertEqual(fund["sectors"][0]["sector"], "半导体")
        self.assertIn("style_tags", fund)


class NewsKeywordCacheCliTest(unittest.TestCase):
    def test_analyze_stops_and_writes_keyword_request_when_cache_missing(self):
        from src import cli

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.md"
            config = SimpleNamespace(holdings=[
                SimpleNamespace(code="001198", name="东方惠灵活配置混合A", type="domestic"),
            ])
            args = SimpleNamespace(
                config="fund-portfolio.yaml",
                output=str(output),
                skip_recommend=True,
                agent_news_plan=None,
                agent_news_request_output=None,
                require_agent_news_plan=False,
                agent_request_output=None,
                require_agent_decisions=False,
                agent_decisions=None,
                agent_evidence_output=None,
                require_agent_report=False,
                snapshot_after=False,
                news_keyword_cache=str(Path(tmp) / "missing.json"),
                news_keyword_request_output=None,
            )

            with patch("src.config.loader.load_portfolio_config", return_value=config), \
                 patch("src.config.loader.import_to_database"), \
                 patch("src.db.storage.FundStorage", return_value=SimpleNamespace(get_fund_score_history=lambda *a, **k: [])), \
                 patch("src.analysis.scorer.FundAnalyzer") as analyzer_cls, \
                 patch("src.analysis.correlation.compute_correlations", return_value=pd.DataFrame()), \
                 patch("src.analysis.stress.stress_test", return_value=[]), \
                 patch("src.cli._compute_holdings", return_value={"funds": [], "by_fund": {}}), \
                 patch("src.cli._build_workflow_context", return_value={}), \
                 patch("src.cli._run_news_analysis") as news_analysis:
                analyzer = analyzer_cls.return_value
                analyzer.funds = {
                    "001198": {
                        "completeness": "A",
                        "basic": {"name": "东方惠灵活配置混合A", "fund_type": "混合型"},
                        "holdings": pd.DataFrame([{"股票名称": "寒武纪"}]),
                        "sectors": pd.DataFrame([{"行业": "半导体"}]),
                    }
                }
                analyzer.score_fund.return_value = {
                    "fund_code": "001198",
                    "fund_name": "东方惠灵活配置混合A",
                    "composite_score": 60,
                    "score_level_emoji": "🟡",
                }

                cli.cmd_analyze(args)

            self.assertFalse(news_analysis.called)
            request_path = Path(f"{output}.news_keywords_request.json")
            self.assertTrue(request_path.exists())
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["request_version"], "news_keyword_request.v1")


if __name__ == "__main__":
    unittest.main()
