"""Direct CP-SAT model for lay planning.

This strategy models marker ratios, ply counts, and their products directly.
It minimizes the number of active lays first, then weighted size deviation.
OR-Tools reports either an optimal solution or the best feasible incumbent found
within the strategy time limit. A validated heuristic incumbent is used only to
shrink the number of model slots; it does not change the exact constraints or
exclude a plan with fewer lays.
"""

import math
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from .common import validate_plan


def _separate_size_upper_bound(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Build a simple feasible plan that proves an upper bound on lay count.

    Each marker contains one size only. This is not intended as a good floor
    plan; it safely limits the number of CP-SAT lay slots because an optimum
    can never need more lays than an already-feasible incumbent.
    """
    unit = 2 if tubular else 1
    max_ply_units = max_plies // unit
    if max_ply_units <= 0:
        return None

    tol = tolerance_pct / 100.0
    plan = []
    for size, quantity in order.items():
        lo = math.ceil(quantity * (1 - tol)) if quantity > 0 else 0
        hi = math.floor(quantity * (1 + tol)) if quantity > 0 else 0
        first = math.ceil(lo / unit) * unit
        candidates = range(first, hi + 1, unit)
        target = min(
            candidates,
            key=lambda value: (abs(value - quantity), value < quantity),
            default=None,
        )
        if target is None:
            return None

        remaining = target // unit
        full_capacity = max_pieces * max_ply_units
        while remaining >= full_capacity:
            plan.append(({s: max_pieces if s == size else 0 for s in order}, max_ply_units * unit))
            remaining -= full_capacity

        ratio, remainder = divmod(remaining, max_ply_units)
        if ratio:
            plan.append(({s: ratio if s == size else 0 for s in order}, max_ply_units * unit))
        if remainder:
            plan.append(({s: 1 if s == size else 0 for s in order}, remainder * unit))
    return plan or None


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
    timeout: float = 28.0,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    sizes = list(order)
    tol = tolerance_pct / 100.0
    if tubular and max_plies < 2:
        return None
    model = cp_model.CpModel()

    incumbents = [_separate_size_upper_bound(
        order, max_plies, max_pieces, tolerance_pct, tubular,
    )]
    try:
        from .strategy_iterated_greedy import solve as greedy_solve

        greedy = greedy_solve(
            order, max_plies, max_pieces, tolerance_pct, min(max_lays, 12), tubular,
        )
        if greedy and not validate_plan(
            greedy, order, max_plies, max_pieces, tolerance_pct, max_lays, tubular,
        ):
            incumbents.append(greedy)
    except Exception:
        # The direct model remains usable when the optional warm-start heuristic
        # cannot construct a plan.
        pass
    incumbent = min((plan for plan in incumbents if plan), key=len, default=None)
    lay_slots = len(incumbent) if incumbent and len(incumbent) <= max_lays else max_lays

    active = [model.new_bool_var(f"active_{lay}") for lay in range(lay_slots)]
    if tubular:
        max_pairs = max_plies // 2
        ply_pairs = [model.new_int_var(0, max_pairs, f"ply_pairs_{lay}") for lay in range(lay_slots)]
        plies = [model.new_int_var(0, max_pairs * 2, f"plies_{lay}") for lay in range(lay_slots)]
        for lay in range(lay_slots):
            model.add(plies[lay] == 2 * ply_pairs[lay])
    else:
        plies = [model.new_int_var(0, max_plies, f"plies_{lay}") for lay in range(lay_slots)]

    ratios = {}
    cuts = {}
    for lay in range(lay_slots):
        model.add(plies[lay] <= max_plies * active[lay])
        model.add(plies[lay] >= (2 if tubular else 1) * active[lay])
        lay_ratios = []
        for size in sizes:
            ratio = model.new_int_var(0, max_pieces, f"ratio_{lay}_{size}")
            cut = model.new_int_var(0, max_pieces * max_plies, f"cut_{lay}_{size}")
            ratios[lay, size] = ratio
            cuts[lay, size] = cut
            model.add(ratio <= max_pieces * active[lay])
            model.add_multiplication_equality(cut, [ratio, plies[lay]])
            lay_ratios.append(ratio)
        model.add(sum(lay_ratios) <= max_pieces * active[lay])
        model.add(sum(lay_ratios) >= active[lay])

    # Symmetry breaking: active lays and ply counts are ordered.
    for lay in range(lay_slots - 1):
        model.add(active[lay] >= active[lay + 1])
        model.add(plies[lay] >= plies[lay + 1])

    over_vars = []
    under_vars = []
    secondary_bound = 0
    minimum_total_cut = 0
    for size in sizes:
        target = order[size]
        lo = math.ceil(target * (1 - tol)) if target > 0 else 0
        hi = math.floor(target * (1 + tol)) if target > 0 else 0
        minimum_total_cut += lo
        total = sum(cuts[lay, size] for lay in range(lay_slots))
        model.add(total >= lo)
        model.add(total <= hi)

        over = model.new_int_var(0, max(0, hi - target), f"over_{size}")
        under = model.new_int_var(0, max(0, target - lo), f"under_{size}")
        model.add(total - target == over - under)
        over_vars.append(over)
        under_vars.append(under)
        secondary_bound += max(0, hi - target) + 3 * max(0, target - lo)

    effective_max_plies = (max_plies // 2) * 2 if tubular else max_plies
    max_cut_per_lay = max_pieces * effective_max_plies
    model.add(sum(active) >= math.ceil(minimum_total_cut / max_cut_per_lay))

    lay_weight = secondary_bound + 1
    model.minimize(lay_weight * sum(active) + sum(over_vars) + 3 * sum(under_vars))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.log_search_progress = False
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    plan = []
    for lay in range(lay_slots):
        if solver.value(active[lay]) == 0:
            continue
        ratio = {size: solver.value(ratios[lay, size]) for size in sizes}
        plan.append((ratio, solver.value(plies[lay])))
    return plan or None
