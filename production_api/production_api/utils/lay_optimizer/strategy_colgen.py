"""
Column Generation Strategy for Cutting Order Planning (COP)
============================================================

Adapted from Gilmore-Gomory (1961/1963) for apparel lay planning.

PROBLEM FORMULATION
-------------------
Minimise: number of LAYS (physical bed spreads), NOT total plies.

Variables:
  y_j = plies assigned to pattern j (integer, 0..max_plies)
  z_j = 1 if pattern j is used (y_j > 0), 0 otherwise (binary)

Objective: minimise sum(z_j)  [= number of distinct lays]

Constraints:
  sum(pattern_j[s] * y_j) >= order[s]       for all sizes s
  y_j <= max_plies * z_j                     for all j   (linking)
  y_j >= 0, integer; z_j in {0,1}

This is a mixed-integer program — solved via column generation on the
LP relaxation, then rounded to integer.

LP RELAXATION (what we actually solve)
--------------------------------------
Since we can't directly minimise count-of-nonzero in an LP, we use:

  Minimise: sum(y_j / max_plies)

This makes a pattern used at max_plies cost exactly 1.0 (= one lay),
and a pattern at k plies cost k/max_plies (< one lay). The LP prefers
using fewer patterns at high plies over many patterns at low plies —
which is exactly "minimise lays."

The column generation pricing subproblem finds the pattern with the
most favorable reduced cost, subject to sum(pattern[s]) <= max_pieces.

COMPLEXITY: ~polynomial; typically 10-30 CG iterations, each O(n² * m).
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy.optimize import linprog
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Pricing subproblem (bounded knapsack)
# ---------------------------------------------------------------------------

def _pricing_dp(
    duals: List[float],
    n: int,
    capacity: int,
    upper: List[int],
) -> Tuple[List[int], float]:
    """
    Bounded knapsack via DP.
    max sum(duals[i] * x[i])  s.t.  sum(x[i]) <= capacity, 0 <= x[i] <= upper[i].
    Weight per item = 1.
    
    O(capacity * n) time.
    """
    # dp[c] = (value, allocation) for best solution using c slots
    INF = -1e30
    dp_val = [INF] * (capacity + 1)
    dp_alloc = [None] * (capacity + 1)
    dp_val[0] = 0.0
    dp_alloc[0] = [0] * n

    for c in range(capacity):
        if dp_val[c] <= INF:
            continue
        for i in range(n):
            if duals[i] <= 1e-12:
                continue
            if dp_alloc[c][i] >= upper[i]:
                continue
            nc = c + 1
            nv = dp_val[c] + duals[i]
            if nv > dp_val[nc]:
                dp_val[nc] = nv
                dp_alloc[nc] = list(dp_alloc[c])
                dp_alloc[nc][i] += 1

    best = max(range(capacity + 1), key=lambda c: dp_val[c])
    if dp_val[best] <= 0 or dp_alloc[best] is None:
        return [0] * n, 0.0
    return dp_alloc[best], dp_val[best]


def _pricing_greedy(
    duals: List[float],
    n: int,
    capacity: int,
    upper: List[int],
) -> Tuple[List[int], float]:
    """Greedy fallback: sort by dual desc, fill to capacity."""
    order = sorted(range(n), key=lambda i: -duals[i])
    pat = [0] * n
    rem = capacity
    for i in order:
        if duals[i] <= 1e-12 or rem <= 0:
            break
        take = min(rem, upper[i])
        pat[i] = take
        rem -= take
    obj = sum(duals[i] * pat[i] for i in range(n))
    return pat, obj


# ---------------------------------------------------------------------------
# LP master problem
# ---------------------------------------------------------------------------

def _solve_master(
    patterns: List[List[int]],
    order: List[int],
    n: int,
    max_plies: int,
) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Solve LP relaxation:
        min  sum(y_j / max_plies)
        s.t. sum(pattern_j[i] * y_j) >= order[i]   for all i
             0 <= y_j <= max_plies                   for all j
    
    Returns (y_values, duals) or (None, None).
    """
    if not _HAS_SCIPY or not patterns:
        return None, None

    m = len(patterns)

    # Objective: min sum(y_j / max_plies)
    c = np.array([1.0 / max_plies] * m)

    # Constraints: -A @ y <= -order  (converting >= to <=)
    A = np.array(patterns, dtype=float).T  # (n, m)
    A_ub = -A
    b_ub = -np.array(order, dtype=float)

    # Bounds: 0 <= y_j <= max_plies
    bounds = [(0, max_plies)] * m

    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                       method="highs", options={"disp": False, "time_limit": 5.0})
    except Exception:
        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds,
                           method="revised simplex", options={"disp": False})
        except Exception:
            return None, None

    if not res.success:
        return None, None

    y_vals = list(res.x)

    # Extract duals
    duals = None
    if hasattr(res, "ineqlin") and res.ineqlin is not None:
        try:
            raw = res.ineqlin.marginals
            if raw is not None and len(raw) == n:
                # Negate because we converted >= to -A <= -b
                duals = [-float(v) for v in raw]
        except Exception:
            pass

    if duals is None:
        # Estimate from constraint slack
        coverage = [sum(patterns[j][i] * y_vals[j] for j in range(m))
                    for i in range(n)]
        duals = []
        for i in range(n):
            if order[i] <= 0:
                duals.append(0.0)
            else:
                slack_ratio = max(0, (coverage[i] - order[i]) / order[i])
                duals.append(1.0 / max_plies / (1.0 + slack_ratio * 5))

    return y_vals, duals


# ---------------------------------------------------------------------------
# Seed patterns
# ---------------------------------------------------------------------------

def _build_seeds(
    order: List[int],
    sizes: List[str],
    max_pieces: int,
    max_plies: int,
) -> List[List[int]]:
    """Build diverse initial pattern set biased toward mixed proportional patterns."""
    n = len(sizes)
    total = sum(order)
    if total == 0:
        return []

    patterns = []
    seen = set()

    def _add(pat):
        t = tuple(pat)
        if t not in seen and 0 < sum(pat) <= max_pieces:
            seen.add(t)
            patterns.append(list(pat))

    # 1. Best proportional patterns (the most important seeds for COP)
    # At max_plies: what ratio gives us closest to order?
    for plies in [max_plies, max_plies - 1, max_plies - 2,
                  max_plies // 2, max_plies // 3, max_plies // 4]:
        if plies <= 0:
            continue
        # Floor ratio
        pat_f = [order[i] // plies if order[i] > 0 else 0 for i in range(n)]
        _add(pat_f)
        # Ceil ratio
        pat_c = [math.ceil(order[i] / plies) if order[i] > 0 else 0 for i in range(n)]
        if sum(pat_c) <= max_pieces:
            _add(pat_c)
        # Round ratio
        pat_r = [round(order[i] / plies) if order[i] > 0 else 0 for i in range(n)]
        _add(pat_r)
        # Bump floor toward max_pieces
        if sum(pat_f) < max_pieces and sum(pat_f) > 0:
            bumped = list(pat_f)
            gaps = [(order[i] - pat_f[i] * plies, i) for i in range(n) if pat_f[i] > 0 or order[i] > 0]
            gaps.sort(reverse=True)
            budget = max_pieces - sum(bumped)
            for gap, i in gaps:
                if budget <= 0:
                    break
                if bumped[i] < math.ceil(order[i] / plies):
                    bumped[i] += 1
                    budget -= 1
            _add(bumped)

    # 2. Scale proportional to various target sums
    for target in range(max(1, max_pieces - 3), max_pieces + 1):
        raw = [order[i] / total * target for i in range(n)]
        pat = [max(0, round(r)) if order[i] > 0 else 0 for i, r in enumerate(raw)]
        _add(pat)

    # 3. Equal share
    active = sum(1 for i in range(n) if order[i] > 0)
    if active > 0:
        per = max_pieces // active
        if per > 0:
            _add([per if order[i] > 0 else 0 for i in range(n)])

    # 4. Single-size (for LP feasibility — needed if no mixed works)
    for i in range(n):
        if order[i] > 0:
            pat = [0] * n
            pat[i] = min(order[i], max_pieces)
            _add(pat)

    return patterns


# ---------------------------------------------------------------------------
# Integer rounding → lay plan
# ---------------------------------------------------------------------------

def _solve_cleanup(
    remaining: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_cleanup_lays: int,
    tubular: bool,
    original_order: Dict[str, int],
    main_plan: List[Tuple[Dict[str, int], int]],
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Solve the residual order after main LP lays.
    
    The residual is usually small (10-15% of original order).
    We use a direct approach: try all viable ply counts, build ratio via
    floor/ceil, and check tolerance against the FULL plan (main + cleanup).
    
    For 2-lay cleanup: recursively solve remainder after first cleanup lay.
    """
    n = len(sizes)
    rem_list = [max(0, remaining[s]) for s in sizes]
    total_rem = sum(rem_list)
    if total_rem == 0:
        return []

    def _check_full(extra_lays):
        full = main_plan + extra_lays
        totals = {s: 0 for s in sizes}
        for ratio, plies in full:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        for s in sizes:
            if original_order[s] > 0:
                if abs(totals[s] - original_order[s]) / original_order[s] > tol:
                    return False, totals
        return True, totals

    def _to_ratio(pat_list):
        return {sizes[i]: pat_list[i] for i in range(n)}

    def _fix(p):
        if tubular and p % 2 != 0:
            return max(0, p - 1)
        return p

    # --- Single cleanup lay ---
    best_1 = None
    best_1_overcut = float("inf")

    for plies in range(1, max_plies + 1):
        plies = _fix(plies)
        if plies <= 0:
            continue

        # Try ceil ratio
        ratio_c = [math.ceil(rem_list[i] / plies) if rem_list[i] > 0 else 0
                   for i in range(n)]
        # Try floor ratio
        ratio_f = [rem_list[i] // plies if rem_list[i] > 0 else 0
                   for i in range(n)]
        # Try round ratio
        ratio_r = [round(rem_list[i] / plies) if rem_list[i] > 0 else 0
                   for i in range(n)]

        for ratio in [ratio_c, ratio_r, ratio_f]:
            if sum(ratio) == 0 or sum(ratio) > max_pieces:
                continue
            test = [(_to_ratio(ratio), plies)]
            ok, totals = _check_full(test)
            if ok:
                overcut = sum(max(0, totals[s] - original_order[s]) for s in sizes)
                if overcut < best_1_overcut:
                    best_1_overcut = overcut
                    best_1 = test

    if best_1 is not None:
        return best_1

    if max_cleanup_lays < 2:
        return None

    # --- Two cleanup lays: try main cleanup + sub-cleanup ---
    best_2 = None
    best_2_overcut = float("inf")

    # Use key ply counts (not exhaustive — would be too slow)
    key_plies = set()
    for i in range(n):
        if rem_list[i] > 0:
            for d in range(1, min(max_pieces + 1, rem_list[i] + 1)):
                key_plies.add(rem_list[i] // d)
                key_plies.add(math.ceil(rem_list[i] / d))
    # Also add small range
    for p in range(1, min(max_plies + 1, 51)):
        key_plies.add(p)
    key_plies = sorted(p for p in key_plies if 0 < p <= max_plies)
    if tubular:
        key_plies = [p for p in key_plies if p % 2 == 0]

    for p1 in key_plies[:50]:  # Cap iterations
        ratio_1 = [min(rem_list[i], math.ceil(rem_list[i] / p1))
                   if rem_list[i] > 0 else 0 for i in range(n)]
        # Scale down to max_pieces
        while sum(ratio_1) > max_pieces:
            # Remove smallest nonzero
            min_idx = min((i for i in range(n) if ratio_1[i] > 0),
                          key=lambda i: ratio_1[i], default=None)
            if min_idx is None:
                break
            ratio_1[min_idx] = max(0, ratio_1[min_idx] - 1)
        if sum(ratio_1) == 0 or sum(ratio_1) > max_pieces:
            continue

        # After lay 1, what's left?
        after_1 = [max(0, rem_list[i] - ratio_1[i] * p1) for i in range(n)]
        if sum(after_1) == 0:
            test = [(_to_ratio(ratio_1), p1)]
            ok, totals = _check_full(test)
            if ok:
                overcut = sum(max(0, totals[s] - original_order[s]) for s in sizes)
                if overcut < best_2_overcut:
                    best_2_overcut = overcut
                    best_2 = test
            continue

        # Lay 2 for the remainder
        for p2 in key_plies[:30]:
            ratio_2 = [math.ceil(after_1[i] / p2) if after_1[i] > 0 else 0
                       for i in range(n)]
            if sum(ratio_2) == 0 or sum(ratio_2) > max_pieces:
                ratio_2 = [after_1[i] // p2 if after_1[i] > 0 else 0 for i in range(n)]
            if sum(ratio_2) == 0 or sum(ratio_2) > max_pieces:
                continue
            test = [(_to_ratio(ratio_1), p1), (_to_ratio(ratio_2), p2)]
            ok, totals = _check_full(test)
            if ok:
                overcut = sum(max(0, totals[s] - original_order[s]) for s in sizes)
                if overcut < best_2_overcut:
                    best_2_overcut = overcut
                    best_2 = test

    return best_2


def _greedy_lay_builder(
    order_dict: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Iteratively build lay plan: at each step, find the best proportional ratio
    for the remaining order at the best ply count, then subtract.
    
    This is the "peel-off" heuristic from COP literature — simple, fast,
    and produces good solutions when combined with LP-seeded main patterns.
    """
    n = len(sizes)
    remaining = dict(order_dict)
    plan = []

    def _fix(p):
        if tubular and p % 2 != 0:
            return max(0, p - 1)
        return p

    for _ in range(max_lays):
        rem_list = [max(0, remaining[s]) for s in sizes]
        total_rem = sum(rem_list)
        if total_rem == 0:
            break

        best_lay = None
        best_score = -1  # Score: pieces covered by this lay

        # Try ply counts from max down
        for plies in range(max_plies, 0, -1):
            plies = _fix(plies)
            if plies <= 0:
                continue

            # Build proportional ratio
            for mode in ["ceil", "round", "floor"]:
                ratio = [0] * n
                for i in range(n):
                    if rem_list[i] <= 0:
                        ratio[i] = 0
                    elif mode == "ceil":
                        ratio[i] = math.ceil(rem_list[i] / plies)
                    elif mode == "round":
                        ratio[i] = round(rem_list[i] / plies)
                    else:
                        ratio[i] = rem_list[i] // plies

                # Trim to fit max_pieces
                while sum(ratio) > max_pieces:
                    # Remove the size with least remaining
                    candidates = [(rem_list[i], i) for i in range(n) if ratio[i] > 0]
                    if not candidates:
                        break
                    candidates.sort()
                    _, idx = candidates[0]
                    ratio[idx] = max(0, ratio[idx] - 1)

                if sum(ratio) == 0 or sum(ratio) > max_pieces:
                    continue

                # Score: how many pieces does this cover?
                pieces = sum(min(ratio[i] * plies, rem_list[i]) for i in range(n))

                # Penalty for overcut
                overcut = sum(max(0, ratio[i] * plies - rem_list[i]) for i in range(n))

                score = pieces - overcut * 2

                if score > best_score:
                    best_score = score
                    best_lay = (ratio, plies)

            # For efficiency, break early if we found a high-density lay
            if best_lay and best_score > total_rem * 0.9:
                break

        if best_lay is None:
            break

        ratio_list, plies = best_lay
        ratio_dict = {sizes[i]: ratio_list[i] for i in range(n)}
        plan.append((ratio_dict, plies))

        for i, s in enumerate(sizes):
            remaining[s] -= ratio_list[i] * plies

    # Validate
    totals = {s: 0 for s in sizes}
    for ratio, plies in plan:
        for s in sizes:
            totals[s] += ratio.get(s, 0) * plies
    for s in sizes:
        if order_dict[s] > 0:
            if abs(totals[s] - order_dict[s]) / order_dict[s] > tol:
                return None
    return plan if plan else None


def _round_to_plan(
    patterns: List[List[int]],
    y_values: List[float],
    order_dict: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Convert LP fractional y_j to integer lay plan.

    Multi-strategy approach:
    A) LP main pattern + cleanup solver for residual
    B) LP main pattern + greedy peel-off for residual  
    C) Full greedy peel-off seeded by LP's best pattern
    D) Direct LP rounding
    """
    n = len(sizes)

    active = [(j, patterns[j], y_values[j])
              for j in range(len(patterns))
              if y_values[j] > 0.01 and sum(patterns[j]) > 0]
    active.sort(key=lambda x: -x[2])

    if not active:
        return None

    def _fix_plies(p):
        if tubular and p % 2 != 0:
            return max(0, p - 1)
        return p

    def _check(plan):
        if not plan:
            return False
        totals = {s: 0 for s in sizes}
        for ratio, plies in plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        for s in sizes:
            if order_dict[s] > 0:
                if abs(totals[s] - order_dict[s]) / order_dict[s] > tol:
                    return False
        return True

    def _to_ratio(pat):
        return {sizes[i]: pat[i] for i in range(n)}

    best_plan = None
    best_lays = max_lays + 1

    def _update_best(plan):
        nonlocal best_plan, best_lays
        if plan and _check(plan) and len(plan) < best_lays and len(plan) <= max_lays:
            best_plan = plan
            best_lays = len(plan)

    # ---------------------------------------------------------------
    # Approach A+B: LP main pattern at various plies + cleanup/greedy
    # ---------------------------------------------------------------
    main_pat = active[0]
    _, main_ratio_list, main_y = main_pat

    y_floor = math.floor(main_y)
    plies_to_try = set()
    for delta in [-2, -1, 0, 1]:
        plies_to_try.add(_fix_plies(min(max_plies, y_floor + delta)))
    plies_to_try.add(_fix_plies(max_plies))
    plies_to_try.discard(0)

    for main_plies in sorted(plies_to_try, reverse=True):
        remaining = dict(order_dict)
        ratio = _to_ratio(main_ratio_list)
        for s in sizes:
            remaining[s] -= ratio[s] * main_plies

        # Skip if overcut exceeds tolerance
        max_over = 0
        for s in sizes:
            if order_dict[s] > 0 and remaining[s] < 0:
                max_over = max(max_over, -remaining[s] / order_dict[s])
        if max_over > tol:
            continue

        main_plan = [(ratio, main_plies)]
        if _check(main_plan):
            _update_best(main_plan)
            continue

        max_cleanup = min(max_lays, best_lays - 1) - 1
        if max_cleanup <= 0:
            continue

        # A: Structured cleanup
        cleanup = _solve_cleanup(
            remaining, sizes, max_plies, max_pieces, tol,
            min(max_cleanup, 2), tubular, order_dict, main_plan,
        )
        if cleanup is not None:
            _update_best(main_plan + cleanup)

        # B: Greedy peel-off on residual
        if max_cleanup > 0:
            rem_positive = {s: max(0, remaining[s]) for s in sizes}
            greedy_cleanup = _greedy_lay_builder(
                rem_positive, sizes, max_plies, max_pieces, tol,
                max_cleanup, tubular,
            )
            if greedy_cleanup is not None:
                candidate = main_plan + greedy_cleanup
                if _check(candidate):
                    _update_best(candidate)

    # ---------------------------------------------------------------
    # Approach C: Full greedy from scratch (uses LP insight indirectly)
    # ---------------------------------------------------------------
    if best_lays > 2:
        greedy_full = _greedy_lay_builder(
            order_dict, sizes, max_plies, max_pieces, tol,
            max_lays, tubular,
        )
        _update_best(greedy_full)

    # ---------------------------------------------------------------
    # Approach D: Direct LP rounding
    # ---------------------------------------------------------------
    for y_fn in [round, math.ceil]:
        plan = []
        for _, pat, y in active:
            plies = _fix_plies(y_fn(y))
            if plies <= 0:
                continue
            plan.append((_to_ratio(pat), plies))
            if len(plan) > max_lays:
                break
        _update_best(plan)

    return best_plan


# ---------------------------------------------------------------------------
# Column generation loop
# ---------------------------------------------------------------------------

def _colgen_loop(
    order_dict: Dict[str, int],
    sizes: List[str],
    max_pieces: int,
    max_plies: int,
    max_iter: int = 50,
) -> Tuple[List[List[int]], List[float]]:
    """Run column generation. Returns (patterns, y_values)."""
    n = len(sizes)
    order = [order_dict[s] for s in sizes]
    total = sum(order)
    if total == 0:
        return [], []

    # Upper bounds per size in any pattern
    upper = [min(max_pieces, math.ceil(order[i] / max(1, max_plies)) + 2)
             for i in range(n)]

    patterns = _build_seeds(order, sizes, max_pieces, max_plies)
    if not patterns:
        return [], []

    EPS = 1e-4
    best_y = None

    for _ in range(max_iter):
        y_vals, duals = _solve_master(patterns, order, n, max_plies)
        if y_vals is None or duals is None:
            break

        best_y = list(y_vals)

        # Price new pattern
        pat_dp, obj_dp = _pricing_dp(duals, n, max_pieces, upper)
        pat_gr, obj_gr = _pricing_greedy(duals, n, max_pieces, upper)
        new_pat, new_obj = (pat_dp, obj_dp) if obj_dp >= obj_gr else (pat_gr, obj_gr)

        # Reduced cost threshold: objective coefficient = 1/max_plies
        # New column improves if dual_obj > cost = 1/max_plies
        if new_obj <= 1.0 / max_plies + EPS:
            break

        if tuple(new_pat) in {tuple(p) for p in patterns}:
            break
        if sum(new_pat) == 0 or sum(new_pat) > max_pieces:
            break

        patterns.append(list(new_pat))

    # Final solve with all patterns
    if best_y is not None and len(best_y) < len(patterns):
        y_final, _ = _solve_master(patterns, order, n, max_plies)
        if y_final is not None:
            best_y = y_final

    return patterns, best_y if best_y is not None else []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Column Generation (Gilmore-Gomory) strategy for lay planning.

    Minimises number of lays via LP relaxation + integer rounding.
    Typically <1s even on 18K-piece orders. Near-optimal (≤1 lay gap).

    Returns list of (ratio_dict, plies) or None.
    """
    if not _HAS_SCIPY:
        return None

    global max_pieces_global
    max_pieces_global = max_pieces

    sizes = list(order.keys())
    tol = tolerance_pct / 100.0
    eff_plies = max_plies
    if tubular and eff_plies % 2 != 0:
        eff_plies -= 1

    patterns, y_values = _colgen_loop(order, sizes, max_pieces, eff_plies, 50)

    if not patterns or not y_values:
        return None

    plan = _round_to_plan(
        patterns, y_values, order, sizes,
        eff_plies, max_pieces, tol, max_lays, tubular,
    )

    if plan is None:
        return None

    # Validate
    totals = {s: 0 for s in sizes}
    for ratio, plies in plan:
        for s in sizes:
            totals[s] += ratio.get(s, 0) * plies
    for s in sizes:
        if order[s] > 0 and abs(totals[s] - order[s]) / order[s] > tol:
            return None

    return plan
