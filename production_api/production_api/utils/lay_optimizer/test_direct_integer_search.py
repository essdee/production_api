import unittest

from production_api.production_api.utils.lay_optimizer.common import validate_plan
from production_api.production_api.utils.lay_optimizer.core import STRATEGIES, STRATEGY_ORDER
from production_api.production_api.utils.lay_optimizer.strategy_direct_integer_search import solve


SMALL_ORDER = {"S": 25, "M": 150, "L": 200, "XL": 100, "2XL": 25}
TUBULAR_ORDER = {
    "45": 140,
    "50": 267,
    "55": 436,
    "60": 679,
    "65": 800,
    "70": 839,
    "75": 880,
    "80": 961,
}


class DirectIntegerSearchTests(unittest.TestCase):
    def test_registered_as_first_production_strategy(self):
        self.assertIn("direct_integer_search", STRATEGIES)
        self.assertEqual("direct_integer_search", STRATEGY_ORDER[0])

    def test_is_deterministic_on_small_order(self):
        first = solve(SMALL_ORDER, 50, 10, 3, 8, False)
        second = solve(SMALL_ORDER, 50, 10, 3, 8, False)
        self.assertEqual(first, second)
        self.assertEqual([], validate_plan(first, SMALL_ORDER, 50, 10, 3, 8, False))
        self.assertEqual(2, len(first))

    def test_reports_infeasible_when_tubular_table_cannot_hold_one_pair(self):
        self.assertIsNone(solve({"S": 2}, 1, 1, 0, 1, True))

    def test_finds_minimum_three_lay_tubular_plan(self):
        plan = solve(TUBULAR_ORDER, 140, 15, 3, 50, True)
        self.assertIsNotNone(plan)
        self.assertEqual([], validate_plan(plan, TUBULAR_ORDER, 140, 15, 3, 50, True))
        self.assertEqual(3, len(plan))

        cut = {
            size: sum(ratio[size] * plies for ratio, plies in plan)
            for size in TUBULAR_ORDER
        }
        self.assertTrue(all(cut[size] >= quantity for size, quantity in TUBULAR_ORDER.items()))
        self.assertLessEqual(
            sum(abs(cut[size] - quantity) for size, quantity in TUBULAR_ORDER.items()),
            8,
        )


if __name__ == "__main__":
    unittest.main()
