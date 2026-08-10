import json
import subprocess
import sys
import unittest

from production_api.production_api.utils.lay_optimizer.common import validate_inputs, validate_plan
from production_api.production_api.utils.lay_optimizer.core import optimize_lay_plan
from production_api.production_api.utils.lay_optimizer.strategy_cp_sat import solve as solve_cp_sat


ORDER = {"S": 25, "M": 150, "L": 200, "XL": 100, "2XL": 25}
SCREENSHOT_ORDER = {
    "45": 140, "50": 267, "55": 436, "60": 679,
    "65": 800, "70": 839, "75": 880, "80": 961,
}


class ValidationTests(unittest.TestCase):
    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            validate_inputs({}, 50, 10, 3, 8)
        with self.assertRaises(ValueError):
            validate_inputs({"S": -1}, 50, 10, 3, 8)
        with self.assertRaises(ValueError):
            validate_inputs({"S": 1}, 0, 10, 3, 8)
        with self.assertRaises(ValueError):
            validate_inputs({"S": 1}, 50, 10, 3, 0)
        validate_inputs({"S": 1}, 50, 10, 0, 1)

    def test_enforces_every_hard_constraint(self):
        bad = [({"S": 1, "M": 0, "L": 0, "XL": 0, "2XL": 0}, 51)]
        errors = validate_plan(bad, ORDER, 50, 10, 3, 8, True)
        self.assertTrue(any("allowed range" in error for error in errors))
        self.assertTrue(any("odd plies" in error for error in errors))
        self.assertTrue(any("deviation" in error for error in errors))

        too_many_lays = [({"S": 1}, 1), ({"S": 1}, 1)]
        errors = validate_plan(too_many_lays, {"S": 2}, 50, 10, 0, 1)
        self.assertTrue(any("maximum is 1" in error for error in errors))

    def test_rejects_strategy_plan_that_exceeds_max_lays(self):
        result = optimize_lay_plan(
            ORDER, 50, 10, 3, 1, "two_lay_dp", False,
        )
        self.assertFalse(result["success"])
        self.assertEqual("invalid", result["status"])
        self.assertIn("maximum is 1", result["error"])

    def test_cp_sat_returns_exact_valid_plan(self):
        plan = solve_cp_sat(ORDER, 50, 10, 3, 8, False, timeout=5)
        self.assertIsNotNone(plan)
        self.assertEqual([], validate_plan(plan, ORDER, 50, 10, 3, 8, False))
        self.assertEqual(2, len(plan))

    def test_minimum_deviation_handles_large_physical_lay_limit(self):
        result = optimize_lay_plan(
            SCREENSHOT_ORDER, 140, 15, 3, 50, "minimum_deviation", True,
        )
        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual("success", result["status"])
        self.assertLessEqual(result["summary"]["total_lays"], 50)
        self.assertEqual(0, result["summary"]["overcut"])


class ProcessIsolationTests(unittest.TestCase):
    def test_cli_process_returns_structured_result(self):
        completed = subprocess.run(
            [
                sys.executable, "-m", "production_api.production_api.utils.lay_optimizer",
                "--order", "S:25,M:150,L:200,XL:100,2XL:25",
                "--max-plies", "50", "--max-pieces", "10",
                "--strategy", "cp_sat", "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["success"])
        self.assertEqual("success", result["status"])
        self.assertEqual(8, result["params"]["max_lays"])


if __name__ == "__main__":
    unittest.main()
