import unittest
from unittest.mock import Mock

from seller_evaluator import evaluate_seller


def api_for(reputation):
    api = Mock()
    api._request.return_value = {"seller_reputation": reputation}
    return api


class SellerEvaluatorTests(unittest.TestCase):
    def test_approves_5_green_market_leader_without_sales_requirement(self):
        evaluation = evaluate_seller(
            api_for(
                {
                    "level_id": "5_green",
                    "power_seller_status": "new_future_level",
                    "transactions": {"total": 0},
                }
            ),
            123456,
        )

        self.assertTrue(evaluation.approved)
        self.assertEqual(evaluation.level_id, "5_green")
        self.assertEqual(evaluation.power_seller_status, "new_future_level")
        self.assertEqual(evaluation.reason, "Aprovado: vendedor 5_green e MercadoLíder.")

    def test_rejects_5_green_without_market_leader_status(self):
        evaluation = evaluate_seller(
            api_for({"level_id": "5_green", "power_seller_status": None}),
            "789",
        )

        self.assertFalse(evaluation.approved)
        self.assertEqual(
            evaluation.reason,
            "Reprovado: vendedor não possui status de MercadoLíder.",
        )

    def test_rejects_non_5_green_market_leader(self):
        evaluation = evaluate_seller(
            api_for({"level_id": "3_yellow", "power_seller_status": "gold"}),
            "789",
        )

        self.assertFalse(evaluation.approved)
        self.assertEqual(
            evaluation.reason,
            "Reprovado: reputação diferente de 5_green.",
        )

    def test_reports_both_rejection_reasons_when_both_criteria_fail(self):
        evaluation = evaluate_seller(api_for({}), "789")

        self.assertFalse(evaluation.approved)
        self.assertEqual(
            evaluation.reason,
            "Reprovado: reputação diferente de 5_green. "
            "Reprovado: vendedor não possui status de MercadoLíder.",
        )
        self.assertIsNone(evaluation.level_id)
        self.assertIsNone(evaluation.power_seller_status)


if __name__ == "__main__":
    unittest.main()
