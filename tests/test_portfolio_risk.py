import unittest

import pandas as pd

from src.analysis.portfolio_risk import build_portfolio_risk_matrix


class PortfolioRiskTest(unittest.TestCase):
    def test_build_portfolio_risk_matrix_exposure_and_cluster_warnings(self):
        holdings_data = {
            "total_value": 10000,
            "funds": [
                {"code": "000001", "name": "半导体基金", "value": 3000},
                {"code": "000002", "name": "新能源基金", "value": 2500},
                {"code": "000003", "name": "短债基金", "value": 1000},
            ],
        }
        scores = [
            {"fund_code": "000001", "fund_name": "半导体基金", "fund_type": "股票型"},
            {"fund_code": "000002", "fund_name": "新能源基金", "fund_type": "股票型"},
            {"fund_code": "000003", "fund_name": "短债基金", "fund_type": "债券型"},
        ]
        correlations = pd.DataFrame(
            [[1.0, 0.9, 0.1], [0.9, 1.0, 0.2], [0.1, 0.2, 1.0]],
            index=["000001", "000002", "000003"],
            columns=["000001", "000002", "000003"],
        )

        matrix = build_portfolio_risk_matrix(holdings_data, scores, correlations)

        self.assertGreater(matrix["cluster_exposures"]["growth_manufacturing"], 0.5)
        self.assertTrue(any("高相关" in warning for warning in matrix["warnings"]))
        self.assertIn("000001", matrix["marginal_risk"])


if __name__ == "__main__":
    unittest.main()
