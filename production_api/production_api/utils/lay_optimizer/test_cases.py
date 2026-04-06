"""
Test cases for lay optimizer validation.

Each test case is a dict with:
  - name: Human-readable name
  - order: {size: qty}
  - max_plies: Max plies per lay
  - max_pieces: Max pieces per marker
  - tolerance: Allowed ±% per size
  - tubular: Whether tubular fabric (even plies only)
  - difficulty: easy/normal/medium/hard/constrained
  - known_best: Known best results from v2.0 baseline (for comparison)

Usage:
    from lay_optimizer.test_cases import TEST_CASES, get_test_case, run_all_tests

    # Get a specific test case
    tc = get_test_case("power_bermuda")

    # Run all tests and print results
    run_all_tests()
"""

from typing import Dict, List, Optional


TEST_CASES = [
    {
        "id": "power_bermuda",
        "name": "TC1: Power Bermuda (7 sizes, 1,684 pcs)",
        "order": {"45": 208, "50": 333, "55": 229, "60": 239, "65": 225, "70": 225, "75": 225},
        "max_plies": 70,
        "max_pieces": 21,
        "tolerance": 3.0,
        "tubular": False,
        "difficulty": "normal",
        "known_best": {
            "min_lays": 2,
            "best_overcut_pct": 0.1,
            "best_strategy": "ilp",
            "all_strategies_time_s": 1.13,
        },
    },
    {
        "id": "starkits_tshirt",
        "name": "TC2: Starkits T-Shirt (8 sizes, 5,195 pcs)",
        "order": {"2": 457, "4": 893, "6": 980, "8": 980, "10": 812, "12": 555, "14": 371, "16": 147},
        "max_plies": 70,
        "max_pieces": 21,
        "tolerance": 3.0,
        "tubular": False,
        "difficulty": "medium",
        "known_best": {
            "min_lays": 5,
            "best_overcut_pct": 0.8,
            "best_strategy": "balanced",
            "all_strategies_time_s": 4.99,
        },
    },
    {
        "id": "prince_rns_tubular",
        "name": "TC3: PRINCE RNS Tubular (7 sizes, 1,684 pcs)",
        "order": {"45": 208, "50": 333, "55": 229, "60": 239, "65": 225, "70": 225, "75": 225},
        "max_plies": 70,
        "max_pieces": 21,
        "tolerance": 3.0,
        "tubular": True,
        "difficulty": "constrained",
        "known_best": {
            "min_lays": 2,
            "best_overcut_pct": 0.7,
            "best_strategy": "ilp",
            "all_strategies_time_s": 0.56,
        },
    },
    {
        "id": "stress_order",
        "name": "TC4: Stress Order (9 sizes, 18,000 pcs)",
        "order": {
            "XS": 1200, "S": 2400, "M": 3200, "L": 3600, "XL": 2800,
            "2XL": 2000, "3XL": 1400, "4XL": 800, "5XL": 600,
        },
        "max_plies": 200,
        "max_pieces": 21,
        "tolerance": 3.0,
        "tubular": False,
        "difficulty": "hard",
        "known_best": {
            "min_lays": 5,
            "best_overcut_pct": 0.0,
            "best_strategy": "order_match",
            "all_strategies_time_s": 10.65,
        },
    },
    {
        "id": "vikram_real_order",
        "name": "TC6: Real Order (8 sizes, 5,195 pcs, 144 plies, 17 pcs/marker)",
        "order": {"45": 144, "50": 289, "55": 462, "60": 707, "65": 822, "70": 866, "75": 909, "80": 996},
        "max_plies": 144,
        "max_pieces": 17,
        "tolerance": 3.0,
        "tubular": False,
        "difficulty": "medium",
        "known_best": {
            "min_lays": 3,
            "best_overcut_pct": 0.2,
            "best_strategy": "milp",
            "all_strategies_time_s": 15.0,
        },
    },
    {
        "id": "small_skewed",
        "name": "TC5: Small Skewed (5 sizes, 500 pcs)",
        "order": {"S": 25, "M": 150, "L": 200, "XL": 100, "2XL": 25},
        "max_plies": 50,
        "max_pieces": 10,
        "tolerance": 3.0,
        "tubular": False,
        "difficulty": "easy",
        "known_best": {
            "min_lays": 2,
            "best_overcut_pct": 0.0,
            "best_strategy": "ilp",
            "all_strategies_time_s": 0.09,
        },
    },
]


def get_test_case(test_id: str) -> Optional[dict]:
    """Get a test case by ID."""
    for tc in TEST_CASES:
        if tc["id"] == test_id:
            return tc
    return None


def list_test_cases() -> List[str]:
    """List all test case IDs."""
    return [tc["id"] for tc in TEST_CASES]


def run_all_tests(strategies: Optional[List[str]] = None, verbose: bool = True):
    """
    Run all test cases against all (or specified) strategies.
    Returns a results dict with timing and comparison data.
    
    Usage:
        results = run_all_tests()
        results = run_all_tests(strategies=["greedy_subtraction", "ilp"])
    """
    import time
    from .core import optimize_all_strategies, optimize_lay_plan, STRATEGY_ORDER
    from .display import print_comparison

    all_results = {}

    for tc in TEST_CASES:
        if verbose:
            print(f"\n{'=' * 70}")
            print(f"  {tc['name']}")
            print(f"  Difficulty: {tc['difficulty']} | Tubular: {tc['tubular']}")
            print(f"{'=' * 70}")

        start = time.monotonic()

        if strategies:
            results = []
            failed = []
            for s in strategies:
                r = optimize_lay_plan(
                    tc["order"], tc["max_plies"], tc["max_pieces"],
                    tc["tolerance"], strategy=s, tubular=tc["tubular"],
                )
                if r["success"]:
                    results.append(r)
                else:
                    failed.append(r)
        else:
            results, failed = optimize_all_strategies(
                tc["order"], tc["max_plies"], tc["max_pieces"],
                tc["tolerance"], tubular=tc["tubular"],
            )

        elapsed = time.monotonic() - start

        if verbose:
            print_comparison(results, failed)
            print(f"\n  ⏱ Total time: {elapsed:.2f}s")

            # Compare with known best
            kb = tc["known_best"]
            if results:
                best_lays = min(r["summary"]["total_lays"] for r in results)
                if best_lays < kb["min_lays"]:
                    print(f"  🏆 NEW RECORD! {best_lays} lays (was {kb['min_lays']})")
                elif best_lays == kb["min_lays"]:
                    print(f"  ✅ Matches known best: {best_lays} lays")
                else:
                    print(f"  ⚠️  Regression: {best_lays} lays (was {kb['min_lays']})")

        all_results[tc["id"]] = {
            "results": results,
            "failed": failed,
            "time_s": elapsed,
            "test_case": tc,
        }

    return all_results


if __name__ == "__main__":
    run_all_tests()
