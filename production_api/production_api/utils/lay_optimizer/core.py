"""
Core orchestrator for lay optimizer strategies.

Provides:
- optimize_lay_plan(): Run a single strategy
- optimize_all_strategies(): Run all registered strategies and compare
- _build_result(): Standardize output format

Production strategies (registered — run by default):
  direct_integer_search, cp_sat, milp, column_generation, proportional, two_lay_dp,
  minimum_deviation, balanced, single_marker, iterated_greedy

Experimental strategies (available explicitly via --strategy):
  operator_greedy, marker_capacity, genetic_search, randomized_set_cover
"""

import time
from typing import Dict, List, Optional, Tuple

from .common import (
    run_solver_process,
    validate_inputs,
    validate_plan,
)
from . import (
    strategy_ilp,
    strategy_order_match,
    strategy_single_ratio,
    strategy_balanced,
    strategy_colgen,
    strategy_milp,
    strategy_proportional_decomp,
    strategy_iterated_greedy,
    strategy_direct_integer_search,
)

try:
    from . import strategy_cp_sat
    _CP_SAT_IMPORT_ERROR = None
except ImportError as exc:  # deployment can continue while OR-Tools is installed
    strategy_cp_sat = None
    _CP_SAT_IMPORT_ERROR = str(exc)

# Experimental strategies — imported on demand only (not registered)
_EXPERIMENTAL_MODULES = {
    "operator_greedy": ".strategy_greedy",
    "marker_capacity": ".strategy_max_density",
    "genetic_search": ".strategy_pso_ga",
    "randomized_set_cover": ".strategy_knapsack",
}

STRATEGY_ALIASES = {
    "colgen": "column_generation",
    "proportional_decomp": "proportional",
    "ilp": "two_lay_dp",
    "order_match": "minimum_deviation",
    "single_ratio": "single_marker",
    "greedy_subtraction": "operator_greedy",
    "max_density": "marker_capacity",
    "pso_ga": "genetic_search",
    "knapsack": "randomized_set_cover",
}


def _load_experimental(name: str):
    """Lazy-load an experimental strategy module."""
    import importlib
    if name not in _EXPERIMENTAL_MODULES:
        return None
    return importlib.import_module(_EXPERIMENTAL_MODULES[name], package=__package__)


# ── Production strategy registry: name → (module, description, timeout_budget) ──
STRATEGIES = {
    "direct_integer_search": (
        strategy_direct_integer_search,
        "Direct integer search — minimum lays, then weighted deviation",
        22.0,
    ),
    "cp_sat": (
        strategy_cp_sat,
        "CP-SAT — direct exact model, minimum lays then deviation",
        30.0,
    ),
    "milp": (
        strategy_milp,
        "Restricted-column MILP — minimum lays then weighted deviation",
        25.0,
    ),
    "column_generation": (
        strategy_colgen,
        "Column-generation heuristic — LP pricing plus feasible integer repair",
        15.0,
    ),
    "proportional": (
        strategy_proportional_decomp,
        "Operator proportional plan — primary marker plus residual cleanup",
        20.0,
    ),
    "two_lay_dp": (
        strategy_ilp,
        "Bounded DP — specialized one/two-lay search with greedy extension",
        10.0,
    ),
    "minimum_deviation": (
        strategy_order_match,
        "Minimum deviation — prefer exact fulfillment, then closest feasible cut",
        20.0,
    ),
    "balanced": (
        strategy_balanced,
        "Balanced — fewest lays with densest markers",
        10.0,
    ),
    "single_marker": (
        strategy_single_ratio,
        "Single marker — one ratio reused across every physical lay",
        3.0,
    ),
    "iterated_greedy": (
        strategy_iterated_greedy,
        "Iterated greedy — deterministic construct, destroy, repair and tune",
        15.0,
    ),
}

STRATEGY_PRIORITIES = {
    "direct_integer_search": "Minimum lays via deterministic ply-tuple search and ratio DP",
    "cp_sat": "Minimum lays with an exact direct model; weighted deviation breaks ties",
    "milp": "Minimum lays over a generated configuration pool; weighted deviation breaks ties",
    "column_generation": "Discover productive marker patterns quickly on large orders",
    "proportional": "Keep the main marker proportional to the order and minimize cleanup work",
    "two_lay_dp": "Find particularly strong one- and two-lay plans for small orders",
    "minimum_deviation": "Minimize total size-wise cut deviation, accepting more lays",
    "balanced": "Minimize lays, then favor fuller markers and lower deviation",
    "single_marker": "Minimize CAD work by reusing one marker ratio",
    "iterated_greedy": "Find a robust feasible plan quickly and improve it locally",
    "operator_greedy": "Mirror the manual peel-off planning workflow",
    "marker_capacity": "Maximize pieces used from the configured marker capacity",
    "genetic_search": "Explore diverse lay structures with genetic search",
    "randomized_set_cover": "Cover the order from a static pool with randomized restarts",
}

# ── Experimental strategies (not run by default, available via --strategy) ──
_EXPERIMENTAL_STRATEGIES = {
    "operator_greedy": (
        "Operator Greedy — iterative peel-off with variable plies",
        5.0,
    ),
    "marker_capacity": (
        "Marker Capacity — pack ratios close to the pieces-per-marker limit",
        5.0,
    ),
    "genetic_search": (
        "Genetic Search — population crossover, mutation and local search",
        20.0,
    ),
    "randomized_set_cover": (
        "Randomized Set Cover — static configuration pool plus improvement",
        20.0,
    ),
}

# Run order for optimize_all_strategies — production strategies only
STRATEGY_ORDER = [
    "direct_integer_search",
    "cp_sat",
    "milp",
    "column_generation",
    "proportional",
    "two_lay_dp",
    "minimum_deviation",
    "balanced",
    "single_marker",
    "iterated_greedy",
]


def _build_result(
    plan: Optional[List[Tuple[Dict[str, int], int]]],
    order: Dict[str, int],
    sizes: List[str],
    strategy: str,
    strategy_desc: str,
    params: dict,
    error: Optional[str] = None,
    status: str = "ok",
    duration_s: float = 0.0,
) -> dict:
    """Build standardized result dict from a plan."""
    if plan is None:
        return {
            "success": False,
            "strategy": strategy,
            "strategy_description": strategy_desc,
            "priority": STRATEGY_PRIORITIES.get(strategy, ""),
            "error": error or f"No feasible plan found within ±{params['tolerance_pct']}% tolerance",
            "status": status,
            "duration_s": round(duration_s, 3),
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
        "priority": STRATEGY_PRIORITIES.get(strategy, ""),
        "status": status,
        "duration_s": round(duration_s, 3),
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
    order = {str(k).strip(): int(v) for k, v in order.items()}
    validate_inputs(order, max_plies, max_pieces, tolerance_pct, max_lays)
    sizes = list(order.keys())
    params = {
        "max_plies": max_plies,
        "max_pieces": max_pieces,
        "tolerance_pct": tolerance_pct,
        "max_lays": max_lays,
        "tubular": tubular,
    }

    strategy = STRATEGY_ALIASES.get(strategy, strategy)

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

    if module is None:
        return _build_result(
            None, order, sizes, strategy, desc, params,
            error=f"Strategy dependency unavailable: {_CP_SAT_IMPORT_ERROR}",
            status="unavailable",
        )

    started = time.monotonic()
    plan, run_status, run_error = run_solver_process(
        module.__name__, budget,
        order, max_plies, max_pieces, tolerance_pct, max_lays, tubular=tubular,
    )
    duration = time.monotonic() - started

    if run_status != "ok":
        return _build_result(
            None, order, sizes, strategy, desc, params,
            error=run_error, status=run_status, duration_s=duration,
        )
    if plan is None:
        return _build_result(
            None, order, sizes, strategy, desc, params,
            status="infeasible", duration_s=duration,
        )

    violations = validate_plan(
        plan, order, max_plies, max_pieces, tolerance_pct, max_lays, tubular,
    )
    if violations:
        return _build_result(
            None, order, sizes, strategy, desc, params,
            error="Invalid strategy result: " + "; ".join(violations),
            status="invalid", duration_s=duration,
        )
    return _build_result(
        plan, order, sizes, strategy, desc, params,
        status="success", duration_s=duration,
    )


def _plan_key(result):
    """Canonical unordered lay key used for reliable deduplication."""
    return tuple(sorted(
        (tuple(sorted(lay["ratio"].items())), lay["plies"])
        for lay in result["lays"]
    ))


def _dominates(left, right):
    """Whether left is no worse on every operator-facing metric and better on one."""
    ls, rs = left["summary"], right["summary"]
    left_metrics = (
        ls["total_lays"], ls["unique_markers"], ls["undercut"], ls["overcut"],
        -ls["avg_pieces_per_ply"],
    )
    right_metrics = (
        rs["total_lays"], rs["unique_markers"], rs["undercut"], rs["overcut"],
        -rs["avg_pieces_per_ply"],
    )
    return all(a <= b for a, b in zip(left_metrics, right_metrics)) and any(
        a < b for a, b in zip(left_metrics, right_metrics)
    )


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
            plan_key = _plan_key(result)
            if plan_key not in seen_plans:
                seen_plans[plan_key] = result["strategy"]
                results.append(result)
            else:
                result["deduplicated"] = True
                result["same_as"] = seen_plans[plan_key]
                failed.append(result)
        else:
            failed.append(result)

    pareto_results = []
    for result in results:
        dominators = [other for other in results if other is not result and _dominates(other, result)]
        if dominators:
            result["dominated"] = True
            result["dominated_by"] = dominators[0]["strategy"]
            failed.append(result)
        else:
            result["pareto_optimal"] = True
            pareto_results.append(result)

    pareto_results.sort(key=lambda r: (
        r["summary"]["total_lays"],
        r["summary"]["undercut"],
        r["summary"]["overcut"],
        r["summary"]["unique_markers"],
    ))
    return pareto_results, failed
