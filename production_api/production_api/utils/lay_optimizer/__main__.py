"""
CLI entry point for lay optimizer.

Usage:
    python3 -m lay_optimizer --order "45:208,50:333,55:229" --max-plies 70 --max-pieces 21
    python3 -m lay_optimizer --test        # Run all test cases
    python3 -m lay_optimizer --test power_bermuda  # Run specific test case
"""

import argparse
import json
import sys

from .core import (
    optimize_lay_plan, optimize_all_strategies,
    STRATEGIES, _EXPERIMENTAL_STRATEGIES, STRATEGY_ORDER,
)
from .display import print_plan, print_comparison
from .test_cases import TEST_CASES, get_test_case, run_all_tests

ALL_STRATEGY_NAMES = list(STRATEGIES.keys()) + list(_EXPERIMENTAL_STRATEGIES.keys())


def main():
    parser = argparse.ArgumentParser(
        description="Lay Planning Optimizer v3.0 — Essdee MRP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Production strategies (run by default with --strategy all):
  milp              MILP — full Mixed Integer Linear Program (HiGHS solver)
  colgen            Column Generation — LP relaxation + knapsack pricing
  proportional_decomp  Proportional Decomposition — ratio × plies factorization
  ilp               ILP — minimum lays via set cover with bounded enumeration
  order_match       Order Match — zero waste, cut exactly what was ordered
  balanced          Balanced — fewest lays with densest markers
  single_ratio      Single Ratio — one marker for all lays, simplest for CAD
  all               Run all 7 production strategies and compare (default)

Experimental strategies (available via --strategy, not run by default):
  greedy_subtraction  Greedy peel-off (operator baseline method)
  max_density         Pack markers close to max pieces/ply
  iterated_greedy     Construct + destroy-repair improvement loop
  pso_ga              PSO/GA population-based metaheuristic
  knapsack            Beam search + DP on item selection

Test mode:
  --test            Run all 5 test cases
  --test ID         Run specific test case (power_bermuda, starkits_tshirt, 
                    prince_rns_tubular, stress_order, small_skewed)

Examples:
  python3 -m lay_optimizer \\
      --order "45:208,50:333,55:229,60:239,65:225,70:225,75:225" \\
      --max-plies 70 --max-pieces 21

  python3 -m lay_optimizer --test
  python3 -m lay_optimizer --test stress_order --strategy greedy_subtraction
        """,
    )
    parser.add_argument("--order", help='Size:Qty — JSON dict or "S:Q,S:Q,..." string')
    parser.add_argument("--max-plies", type=int, help="Max plies per lay")
    parser.add_argument("--max-pieces", type=int, help="Max garments per marker")
    parser.add_argument("--tolerance", type=float, default=3.0, help="Allowed ±%% per size (default: 3)")
    parser.add_argument("--max-lays", type=int, default=8, help="Max lays to consider (default: 8)")
    parser.add_argument(
        "--strategy", default="all",
        choices=ALL_STRATEGY_NAMES + ["all"],
        help="Strategy to use (default: all = run 7 production strategies)",
    )
    parser.add_argument("--tubular", action="store_true", help="Tubular fabric — force even ply counts")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--test", nargs="?", const="all", default=None,
        help="Run test cases (all or specific ID)",
    )

    args = parser.parse_args()

    # Test mode
    if args.test is not None:
        if args.test == "all":
            strategies = [args.strategy] if args.strategy != "all" else None
            run_all_tests(strategies=strategies, verbose=True)
        else:
            tc = get_test_case(args.test)
            if tc is None:
                ids = ", ".join(t["id"] for t in TEST_CASES)
                print(f"❌ Unknown test case: {args.test}")
                print(f"   Available: {ids}")
                sys.exit(1)
            strategies = [args.strategy] if args.strategy != "all" else None
            run_all_tests(strategies=strategies, verbose=True)
        return

    # Normal mode — requires --order, --max-plies, --max-pieces
    if not args.order or not args.max_plies or not args.max_pieces:
        parser.error("--order, --max-plies, and --max-pieces are required (or use --test)")

    # Parse order
    order_str = args.order.strip()
    if order_str.startswith("{"):
        order = json.loads(order_str)
        order = {str(k): int(v) for k, v in order.items()}
    else:
        order = {}
        for part in order_str.split(","):
            s, q = part.strip().split(":", 1)
            order[s.strip()] = int(q.strip())

    if args.strategy == "all":
        results, failed = optimize_all_strategies(
            order, args.max_plies, args.max_pieces, args.tolerance, args.max_lays,
            tubular=args.tubular,
        )
        if args.json:
            print(json.dumps({"plans": results, "failed": failed}, indent=2))
        else:
            print_comparison(results, failed)
    else:
        result = optimize_lay_plan(
            order, args.max_plies, args.max_pieces, args.tolerance, args.max_lays, args.strategy,
            tubular=args.tubular,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_plan(result)


if __name__ == "__main__":
    main()
