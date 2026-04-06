"""
Core orchestrator for lay optimizer strategies.

Provides:
- optimize_lay_plan(): Run a single strategy
- optimize_all_strategies(): Run all registered strategies and compare
- _build_result(): Standardize output format

Production strategies (registered — run by default):
  milp, colgen, proportional_decomp, ilp, order_match, balanced, single_ratio

Experimental strategies (files kept, not registered — available via --strategy flag):
  knapsack, pso_ga, iterated_greedy, greedy_subtraction, max_density
"""

from typing import Dict, List, Optional, Tuple

from .common import with_timeout
from . import (
    strategy_ilp,
    strategy_order_match,
    strategy_single_ratio,
    strategy_balanced,
    strategy_colgen,
    strategy_milp,
    strategy_proportional_decomp,
)

# Experimental strategies — imported on demand only (not registered)
_EXPERIMENTAL_MODULES = {
    "greedy_subtraction": ".strategy_greedy",
    "max_density": ".strategy_max_density",
    "iterated_greedy": ".strategy_iterated_greedy",
    "pso_ga": ".strategy_pso_ga",
    "knapsack": ".strategy_knapsack",
}


def _load_experimental(name: str):
    """Lazy-load an experimental strategy module."""
    import importlib
    if name not in _EXPERIMENTAL_MODULES:
        return None
    return importlib.import_module(_EXPERIMENTAL_MODULES[name], package=__package__)


# ── Production strategy registry: name → (module, description, timeout_budget) ──
STRATEGIES = {
    "milp": (
        strategy_milp,
        "MILP — full Mixed Integer Linear Program (HiGHS solver)",
        20.0,
    ),
    "colgen": (
        strategy_colgen,
        "Column Generation (Gilmore-Gomory) — LP relaxation + knapsack pricing",
        15.0,
    ),
    "proportional_decomp": (
        strategy_proportional_decomp,
        "Proportional Decomposition — factor order into ratio × plies layers",
        20.0,
    ),
    "ilp": (
        strategy_ilp,
        "ILP — minimum lays via set cover with bounded enumeration",
        10.0,
    ),
    "order_match": (
        strategy_order_match,
        "Order Match — cut exactly what was ordered, zero waste",
        20.0,
    ),
    "balanced": (
        strategy_balanced,
        "Balanced — fewest lays with densest markers",
        10.0,
    ),
    "single_ratio": (
        strategy_single_ratio,
        "Single Ratio — one marker for all lays, simplest for CAD",
        3.0,
    ),
}

# ── Experimental strategies (not run by default, available via --strategy) ──
_EXPERIMENTAL_STRATEGIES = {
    "greedy_subtraction": (
        "Greedy Subtraction — iterative peel-off with variable plies (operator method)",
        5.0,
    ),
    "max_density": (
        "Max Density — pack markers close to max pieces/ply",
        5.0,
    ),
    "iterated_greedy": (
        "Iterated Greedy — construct + destroy-repair improvement loop",
        15.0,
    ),
    "pso_ga": (
        "PSO/GA Hybrid — population-based metaheuristic",
        20.0,
    ),
    "knapsack": (
        "Knapsack — beam search + DP on item selection",
        20.0,
    ),
}

# Run order for optimize_all_strategies — production strategies only
STRATEGY_ORDER = [
    "milp",
    "colgen",
    "proportional_decomp",
    "ilp",
    "order_match",
    "balanced",
    "single_ratio",
]


def _build_result(
    plan: Optional[List[Tuple[Dict[str, int], int]]],
    order: Dict[str, int],
    sizes: List[str],
    strategy: str,
    strategy_desc: str,
    params: dict,
) -> dict:
    """Build standardized result dict from a plan."""
    if plan is None:
        return {
            "success": False,
            "strategy": strategy,
            "strategy_description": strategy_desc,
            "error": f"No feasible plan found within ±{params['tolerance_pct']}% tolerance",
            "lays": [],
            "summary": {},
            "per_size": {},
            "params": params,
        }

    lays_out = []
    totals = {s: 0 for s in sizes}

    for i, (ratio, plies) in enumerate(plan, 1):
        cut = {s: ratio.get(s, 0) * plies for s in sizes}
        for s in sizes:
            totals[s] += cut[s]
        pcs_per_ply = sum(ratio.get(s, 0) for s in sizes)
        lays_out.append({
            "lay_no": i,
            "plies": plies,
            "ratio": {s: ratio.get(s, 0) for s in sizes},
            "pieces_per_ply": pcs_per_ply,
            "total_pieces": sum(cut.values()),
            "cut_per_size": cut,
        })

    per_size = {}
    overcut = 0
    undercut = 0
    for s in sizes:
        diff = totals[s] - order[s]
        pct = abs(diff) / order[s] * 100 if order[s] > 0 else 0
        per_size[s] = {"order": order[s], "cut": totals[s], "diff": diff, "pct": round(pct, 1)}
        if diff > 0:
            overcut += diff
        else:
            undercut += abs(diff)

    total_order = sum(order.values())
    ratio_strs = set()
    for lay in lays_out:
        r_str = ":".join(str(lay["ratio"][s]) for s in sizes)
        ratio_strs.add(r_str)

    return {
        "success": True,
        "strategy": strategy,
        "strategy_description": strategy_desc,
        "lays": lays_out,
        "summary": {
            "total_lays": len(lays_out),
            "unique_markers": len(ratio_strs),
            "total_cut": sum(totals.values()),
            "total_order": total_order,
            "overcut": overcut,
            "undercut": undercut,
            "overcut_pct": round(overcut / total_order * 100, 1) if total_order > 0 else 0,
            "undercut_pct": round(undercut / total_order * 100, 1) if total_order > 0 else 0,
            "avg_pieces_per_ply": round(
                sum(l["pieces_per_ply"] for l in lays_out) / len(lays_out), 1
            ) if lays_out else 0,
        },
        "per_size": per_size,
        "params": params,
    }


def optimize_lay_plan(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    strategy: str = "ilp",
    tubular: bool = False,
) -> dict:
    """
    Optimize lay plan for a cutting order using a single strategy.

    Args:
        order:          Dict of {size: quantity}
        max_plies:      Maximum plies per lay (physical table limit)
        max_pieces:     Maximum garment pieces per marker (CAD constraint)
        tolerance_pct:  Allowed deviation per size (default ±3%)
        max_lays:       Maximum lays to try (default 8)
        strategy:       Strategy name (see STRATEGIES)
        tubular:        If True, all ply counts must be even

    Returns: dict with 'lays', 'summary', 'per_size', 'strategy' keys
    """
    order = {str(k): int(v) for k, v in order.items()}
    sizes = list(order.keys())
    params = {
        "max_plies": max_plies,
        "max_pieces": max_pieces,
        "tolerance_pct": tolerance_pct,
        "tubular": tubular,
    }

    if strategy in STRATEGIES:
        module, desc, budget = STRATEGIES[strategy]
    elif strategy in _EXPERIMENTAL_STRATEGIES:
        module = _load_experimental(strategy)
        if module is None:
            raise ValueError(f"Could not load experimental strategy: {strategy}")
        desc, budget = _EXPERIMENTAL_STRATEGIES[strategy]
    else:
        all_names = list(STRATEGIES.keys()) + list(_EXPERIMENTAL_STRATEGIES.keys())
        raise ValueError(f"Unknown strategy: {strategy}. Available: {all_names}")

    plan = with_timeout(
        module.solve, budget,
        order, max_plies, max_pieces, tolerance_pct, max_lays, tubular=tubular,
    )

    return _build_result(plan, order, sizes, strategy, desc, params)


def optimize_all_strategies(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> tuple:
    """
    Run ALL strategies and return (results, failed).
    results: unique successful plans
    failed: infeasible or deduplicated plans
    """
    results = []
    seen_plans = {}
    failed = []

    for strategy_name in STRATEGY_ORDER:
        result = optimize_lay_plan(
            order, max_plies, max_pieces, tolerance_pct, max_lays, strategy_name, tubular=tubular,
        )
        if result["success"]:
            plan_key = tuple(
                (tuple(sorted(lay["ratio"].items())), lay["plies"])
                for lay in result["lays"]
            )
            if plan_key not in seen_plans:
                seen_plans[plan_key] = result["strategy"]
                results.append(result)
            else:
                result["deduplicated"] = True
                result["same_as"] = seen_plans[plan_key]
                failed.append(result)
        else:
            failed.append(result)

    return results, failed
