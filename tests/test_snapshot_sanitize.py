import unittest

from types import SimpleNamespace

from src.cli import _score_snapshot_payload, _sanitize_stress_tests_for_snapshot, _should_snapshot_after_analyze


class SnapshotSanitizeTest(unittest.TestCase):
    def test_stress_tests_drop_report_only_fields_before_db_save(self):
        sanitized = _sanitize_stress_tests_for_snapshot([
            {
                "scenario_id": "R_QDII",
                "scenario_desc": "海外权益与汇率共振",
                "fund_code": "008253",
                "fund_name": "华宝致远混合A",
                "estimated_drawdown_pct": -7.0,
                "risk_driver": "美股估值回撤",
                "agent_instruction": "agent重估",
            }
        ])

        self.assertEqual(sanitized[0]["fund_code"], "008253")
        self.assertEqual(sanitized[0]["estimated_drawdown_pct"], -7.0)
        self.assertNotIn("fund_name", sanitized[0])
        self.assertNotIn("risk_driver", sanitized[0])
        self.assertNotIn("agent_instruction", sanitized[0])

    def test_analyze_snapshot_is_enabled_by_default(self):
        self.assertTrue(_should_snapshot_after_analyze(SimpleNamespace()))
        self.assertFalse(_should_snapshot_after_analyze(SimpleNamespace(snapshot_after=False)))
        self.assertTrue(_should_snapshot_after_analyze(SimpleNamespace(snapshot_after=True)))

    def test_score_snapshot_payload_preserves_structured_matrices(self):
        payload = _score_snapshot_payload({
            "fund_code": "000001",
            "data_completeness": "A",
            "composite_score": 70,
            "score_level": "yellow",
            "macro_score": 14,
            "macro_basis": "",
            "macro_detail": {},
            "meso_score": 20,
            "meso_basis": "",
            "meso_detail": {},
            "micro_score": 36,
            "micro_basis": "",
            "micro_detail": {},
            "recommendation": "持有",
            "stop_profit_pct": 20,
            "stop_loss_pct": -15,
            "action_logic": "",
            "feature_matrix": {"sortino_ratio": 1.2},
            "trend_matrix": {"short_term": {"direction": "up"}},
            "operation_advice": {"action": "buy"},
            "factor_matrix": {"macro": []},
            "score_confidence": 0.8,
        })

        self.assertEqual(payload["feature_matrix"]["sortino_ratio"], 1.2)
        self.assertEqual(payload["trend_matrix"]["short_term"]["direction"], "up")
        self.assertEqual(payload["operation_advice"]["action"], "buy")
        self.assertEqual(payload["score_confidence"], 0.8)


if __name__ == "__main__":
    unittest.main()
