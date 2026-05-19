import unittest

from src.cli import _sanitize_stress_tests_for_snapshot


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


if __name__ == "__main__":
    unittest.main()
