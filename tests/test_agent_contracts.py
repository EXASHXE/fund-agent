import unittest

from src.agent.contracts import (
    build_agent_decision_request,
    build_agent_evidence_pack,
    build_news_search_request,
    validate_agent_decisions,
    validate_agent_news_plan,
)


class AgentContractsTest(unittest.TestCase):
    def test_build_request_contains_expected_front_loaded_tasks(self):
        request = build_agent_decision_request(
            portfolio_context={"holdings": []},
            scores=[{
                "fund_code": "001198",
                "fund_name": "东方惠",
                "composite_score": 64,
                "macro_score": 15,
                "meso_score": 19,
                "micro_score": 30,
                "recommendation": "持有",
                "action_logic": "规则初稿",
                "agent_score_context": {"fund_context": {"top_holdings": []}},
            }],
            news_data=[{"fund_code": "001198", "events": [], "news_list": []}],
            stress_tests=[{"scenario_id": "R_MARKET"}],
            recommendations=[{"code": "000300", "name": "宽基"}],
        )

        self.assertEqual(request["request_version"], "agent_decision_request.v1")
        self.assertEqual(request["fund_score_tasks"][0]["fund_code"], "001198")
        self.assertIn("expected_decision_schema", request)

    def test_validate_agent_decisions_accepts_minimal_payload(self):
        decisions = validate_agent_decisions({
            "decision_version": "agent_decision_set.v1",
            "portfolio": {"tldr": "维持但控制成长仓位"},
            "fund_scores": {},
            "news": {},
            "stress_tests": [],
            "recommendations": [],
            "evidence_notes": [],
        })

        self.assertEqual(decisions["portfolio"]["tldr"], "维持但控制成长仓位")

    def test_build_news_search_request_is_before_news_fetch(self):
        request = build_news_search_request(
            portfolio_context={"total_value": 10000},
            fund_profiles=[{
                "fund_code": "001198",
                "holding_keywords": ["寒武纪", "精测电子"],
                "fallback_keywords": ["半导体"],
            }],
        )

        self.assertEqual(request["request_version"], "agent_news_search_request.v1")
        self.assertEqual(request["fund_profiles"][0]["fund_code"], "001198")
        self.assertIn("expected_plan_schema", request)

    def test_validate_agent_news_plan_accepts_keywords(self):
        plan = validate_agent_news_plan({
            "plan_version": "agent_news_search_plan.v1",
            "funds": {
                "001198": {
                    "keywords": ["寒武纪", "精测电子", "国产AI芯片"],
                    "research_lenses": ["重仓公司业绩与估值"],
                }
            },
        })

        self.assertIn("国产AI芯片", plan["funds"]["001198"]["keywords"])

    def test_build_decision_request_handles_recommendation_context_cycles(self):
        recommendations = [{"code": "000300", "name": "宽基"}]
        rec_context = {"rule_ranked_candidates": recommendations}
        recommendations[0]["agent_recommendation_context"] = rec_context

        request = build_agent_decision_request(
            portfolio_context={"holdings": []},
            scores=[],
            news_data=[],
            stress_tests=[],
            recommendations=recommendations,
            recommendation_context=rec_context,
        )

        self.assertEqual(
            request["recommendation_task"]["candidate_recommendations"][0]["code"],
            "000300",
        )
        self.assertNotIn(
            "agent_recommendation_context",
            request["recommendation_task"]["candidate_recommendations"][0],
        )

    def test_build_agent_evidence_pack_is_single_report_input(self):
        pack = build_agent_evidence_pack(
            report_date="2026-05-15",
            portfolio_context={"total_value": 10000},
            workflow_context={"mode": "prior_settlement"},
            scores=[{"fund_code": "001198", "composite_score": 64}],
            holdings_data={"funds": [{"code": "001198"}]},
            news_data=[{"fund_code": "001198", "news_list": []}],
            stress_results=[{"scenario_id": "R_MARKET"}],
            recommendations=[{"code": "000300", "name": "宽基"}],
        )

        self.assertEqual(pack["pack_version"], "agent_evidence_pack.v1")
        self.assertIn("report_tasks", pack)
        self.assertEqual(pack["data"]["report_date"], "2026-05-15")
        self.assertIn("final_report_format", pack)


if __name__ == "__main__":
    unittest.main()
