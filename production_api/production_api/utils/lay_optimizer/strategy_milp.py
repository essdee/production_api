"""
MILP strategy — Direct Mixed Integer Linear Programming.

Formulates the entire lay planning problem as a single MILP:
  - Pre-enumerates candidate marker ratio patterns
  - Binary y_j: whether pattern j is used
  - Integer p_j: ply count for pattern j
  - Minimize: Σ y_j (number of lays)
  - Subject to per-size tolerance constraints

Uses scipy.optimize.milp with HiGHS solver (branch-and-bound + cutting planes).
Zero recursion. Handles large orders in seconds.
"""

import math
import itertools
import time
import numpy as np
from typing import Dict, List, Optional, Tuple

from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import csc_array

from .common import (
    _SolverTimer,
    _SolverTimeout,
    check_tolerance,
    plan_cut_totals,
)
from . import strategy_colgen as _colgen


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
    timeout: float = 20.0,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Solve lay planning via direct MILP.

    Approach: pre-enumerate (pattern, ply_count) columns.
    Each column j has a fixed ratio and fixed ply count.
    x_j ∈ {0, 1}: whether this column is selected.
    Coverage = Σ_j x_j * ratio_j[s] * plies_j for each size s.

    Eliminates bilinear products → pure binary MILP → fast for HiGHS.

    Returns list of (ratio_dict, plies) tuples, or None if infeasible.
    """
    sizes = list(order.keys())
    tol = tolerance_pct / 100.0
    n = len(sizes)
    if n == 0:
        return None

    # ---------------------------------------------------------------
    # Step 1: Enumerate (pattern, ply) columns
    # ---------------------------------------------------------------
    columns = _enumerate_columns(order, sizes, max_plies, max_pieces, tol, max_lays, tubular)

    if not columns:
        return None

    J = len(columns)
    max_active = min(max_lays, J)

    # ---------------------------------------------------------------
    # Step 2: Build MILP
    # ---------------------------------------------------------------
    # Variables: x_0 ... x_{J-1}, all binary
    # Objective: minimize Σ x_j (number of lays)
    c = np.ones(J)

    # Bounds: x_j ∈ {0, 1}
    lb = np.zeros(J)
    ub = np.ones(J)
    integrality = np.ones(J)  # all binary

    # Constraints
    A_rows = []
    A_cols = []
    A_data = []
    lower_bounds = []
    upper_bounds = []
    row = 0

    # (A) Per-size coverage: order[s]*(1-tol) ≤ Σ_j x_j * coverage_j[s] ≤ order[s]*(1+tol)
    for i, s in enumerate(sizes):
        if order[s] == 0:
            continue
        for j, (ratio, plies) in enumerate(columns):
            cov = ratio.get(s, 0) * plies
            if cov > 0:
                A_rows.append(row)
                A_cols.append(j)
                A_data.append(float(cov))
        # Use floor for upper bound to match check_tolerance's strict comparison:
        # abs(cut - order) / order <= tol  →  cut <= order * (1 + tol)
        # For integer cuts: largest valid cut = floor(order * (1 + tol))
        # Similarly smallest valid cut = ceil(order * (1 - tol))
        lo = math.ceil(order[s] * (1 - tol))
        hi = math.floor(order[s] * (1 + tol))
        lower_bounds.append(float(lo))
        upper_bounds.append(float(hi))
        row += 1

    # (B) Maximum lays: Σ x_j ≤ max_active
    for j in range(J):
        A_rows.append(row)
        A_cols.append(j)
        A_data.append(1.0)
    lower_bounds.append(0.0)
    upper_bounds.append(float(max_active))
    row += 1

    A = csc_array((A_data, (A_rows, A_cols)), shape=(row, J))
    constraints = LinearConstraint(A, lower_bounds, upper_bounds)
    bounds = Bounds(lb, ub)

    # ---------------------------------------------------------------
    # Step 3: Solve
    # ---------------------------------------------------------------
    options = {"time_limit": max(timeout - 1.0, 5.0), "presolve": True}

    result = milp(
        c=c,
        constraints=constraints,
        integrality=integrality,
        bounds=bounds,
        options=options,
    )

    if not result.success:
        return None

    # ---------------------------------------------------------------
    # Step 4: Extract solution
    # ---------------------------------------------------------------
    x = result.x
    plan = []
    for j in range(J):
        if round(x[j]) > 0:
            ratio, plies = columns[j]
            plan.append((dict(ratio), plies))

    if not plan:
        return None

    # Validate
    if not check_tolerance(plan, order, sizes, tol):
        return None

    # Sort by ply count descending
    plan.sort(key=lambda x: -x[1])

    return plan


def _enumerate_columns(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Enumerate (ratio_pattern, ply_count) columns for the MILP.

    Each column represents a complete lay: a specific marker ratio at a specific ply count.
    We enumerate "useful" columns — those that contribute meaningfully to covering the order.

    The key insight: for each size s with order q_s, useful ply counts are
    q_s / r for r = 1..max_pieces. And for each ply count, a useful ratio
    is floor or ceil of q_s / plies for each size.

    Cap total columns at ~5000 to keep solver fast.
    """
    n = len(sizes)
    active_sizes = [s for s in sizes if order[s] > 0]
    if not active_sizes:
        return []

    total = sum(order[s] for s in active_sizes)
    column_set = set()  # (ratio_tuple, plies) for dedup

    def add_col(ratio_dict, plies):
        """Add a (ratio, plies) column if valid."""
        key = tuple(ratio_dict.get(s, 0) for s in sizes)
        if sum(key) > 0 and sum(key) <= max_pieces and plies > 0 and plies <= max_plies:
            if tubular and plies % 2 != 0:
                return
            column_set.add((key, plies))

    # ---------------------------------------------------------------
    # Generate key ply counts
    # ---------------------------------------------------------------
    ply_set = set()
    ply_set.add(max_plies)
    if max_plies > 1:
        ply_set.add(max_plies - 1)
    if max_plies > 2:
        ply_set.add(max_plies - 2)

    for s in active_sizes:
        q = order[s]
        for r in range(1, min(max_pieces + 1, q + 1)):
            p = q // r
            if 0 < p <= max_plies:
                ply_set.add(p)
            p2 = math.ceil(q / r) if r > 0 else 0
            if 0 < p2 <= max_plies:
                ply_set.add(p2)

    # Add divisor plies for common coverage
    for s in active_sizes:
        q = order[s]
        for d in range(1, min(int(math.sqrt(q)) + 2, max_plies + 1)):
            if q % d == 0:
                ply_set.add(d)
                if q // d <= max_plies:
                    ply_set.add(q // d)

    # Small ply values (for cleanup lays)
    for p in range(1, min(31, max_plies + 1)):
        ply_set.add(p)

    if tubular:
        ply_set = {p for p in ply_set if p % 2 == 0}

    ply_list = sorted(p for p in ply_set if 0 < p <= max_plies)

    # ---------------------------------------------------------------
    # For each ply count, generate ratio patterns
    # ---------------------------------------------------------------
    for plies in ply_list:
        # Full proportional: floor
        ratio_f = {s: order[s] // plies for s in active_sizes}
        add_col(ratio_f, plies)

        # Full proportional: ceil (trim to fit max_pieces)
        ratio_c = {s: min(math.ceil(order[s] / plies), max_pieces) for s in active_sizes}
        while sum(ratio_c.values()) > max_pieces:
            # Trim size with smallest overcut
            trimmable = [(order[s] - (ratio_c[s] - 1) * plies, s)
                         for s in active_sizes if ratio_c[s] > 0]
            trimmable.sort()
            _, ts = trimmable[0]
            ratio_c[ts] -= 1
        add_col(ratio_c, plies)

        # Mixed: round (closest to exact proportion)
        ratio_r = {}
        for s in active_sizes:
            ratio_r[s] = round(order[s] / plies)
        while sum(ratio_r.values()) > max_pieces:
            trimmable = sorted(
                [(abs(order[s] - (ratio_r[s] - 1) * plies), s)
                 for s in active_sizes if ratio_r[s] > 0]
            )
            _, ts = trimmable[0]
            ratio_r[ts] -= 1
        add_col(ratio_r, plies)

    # ---------------------------------------------------------------
    # Single-size columns (essential for cleanup)
    # ---------------------------------------------------------------
    for s in active_sizes:
        q = order[s]
        for r in range(1, min(max_pieces + 1, q + 1)):
            # Exact coverage: plies = q / r
            if q % r == 0 and q // r <= max_plies:
                p = q // r
                d = {sz: 0 for sz in sizes}
                d[s] = r
                add_col(d, p)
            # Approximate coverage at common ply counts
            for p in [max_plies, max_plies // 2, q // r if r > 0 else 0,
                       math.ceil(q / r) if r > 0 else 0]:
                if 0 < p <= max_plies:
                    d = {sz: 0 for sz in sizes}
                    d[s] = r
                    add_col(d, p)
            if len(column_set) > 20000:
                break

    # ---------------------------------------------------------------
    # Pair columns: two sizes at a time filling max_pieces
    # ---------------------------------------------------------------
    if n <= 12 and len(column_set) < 15000:
        for s1, s2 in itertools.combinations(active_sizes, 2):
            # Try key plies where both sizes have good ratios
            for plies in ply_list:
                r1_f = order[s1] // plies
                r2_f = order[s2] // plies
                r1_c = min(math.ceil(order[s1] / plies), max_pieces)
                r2_c = min(math.ceil(order[s2] / plies), max_pieces)

                for r1, r2 in [(r1_f, r2_f), (r1_c, r2_c), (r1_f, r2_c), (r1_c, r2_f)]:
                    if r1 + r2 > max_pieces:
                        r2 = max_pieces - r1
                    if r1 > 0 and r2 > 0 and r1 + r2 <= max_pieces:
                        d = {sz: 0 for sz in sizes}
                        d[s1] = r1
                        d[s2] = r2
                        add_col(d, plies)

                if len(column_set) > 20000:
                    break
            if len(column_set) > 20000:
                break

    # ---------------------------------------------------------------
    # Proportional-density patterns at key plies
    # ---------------------------------------------------------------
    for plies in [max_plies, max_plies - 1, max_plies - 2,
                  max_plies // 2, max_plies // 3]:
        if plies <= 0:
            continue
        for density in range(max(1, max_pieces - 3), max_pieces + 1):
            ratio = {}
            budget = density
            sorted_s = sorted(active_sizes, key=lambda s: -order[s])
            for s in sorted_s:
                if budget <= 0:
                    break
                prop = order[s] / total if total > 0 else 0
                r = max(0, min(budget, round(prop * density)))
                ratio[s] = r
                budget -= r
            # Distribute leftover
            for s in sorted_s:
                if budget <= 0:
                    break
                if ratio.get(s, 0) == 0 and order[s] > 0:
                    ratio[s] = 1
                    budget -= 1
            add_col(ratio, plies)

    # ---------------------------------------------------------------
    # Seed from colgen's LP-driven patterns (finds hard-to-enumerate combos)
    # ---------------------------------------------------------------
    seed_cols = _get_colgen_columns(order, sizes, max_plies, max_pieces, tol, max_lays, tubular)
    for r, p in seed_cols:
        add_col(r, p)

    # Convert to list
    result = []
    for (key, plies) in column_set:
        d = {sizes[i]: key[i] for i in range(n)}
        result.append((d, plies))

    return result


def _get_colgen_columns(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Run colgen and extract its (pattern, ply) pairs as seed columns for MILP.
    Falls back gracefully if colgen fails or times out.
    """
    try:
        plan = _colgen.solve(
            order=order,
            max_plies=max_plies,
            max_pieces=max_pieces,
            tolerance_pct=tol * 100.0,
            max_lays=max_lays,
            tubular=tubular,
        )
        if plan:
            return [(dict(r), p) for r, p in plan]
    except Exception:
        pass
    return []


def _repair_rounding(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
    max_plies: int,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Attempt to repair a plan that slightly violates tolerance by
    adjusting ply counts ±1.
    """
    if not plan:
        return None

    best = None
    best_dev = float('inf')

    # Try adjusting each lay's plies by -1, 0, +1
    for adjustments in itertools.product([-1, 0, 1], repeat=len(plan)):
        candidate = []
        valid = True
        for (ratio, plies), adj in zip(plan, adjustments):
            new_plies = plies + adj
            if new_plies <= 0 or new_plies > max_plies:
                valid = False
                break
            if tubular and new_plies % 2 != 0:
                valid = False
                break
            candidate.append((ratio, new_plies))
        if not valid:
            continue
        if check_tolerance(candidate, order, sizes, tol):
            dev = sum(
                abs(sum(r.get(s, 0) * p for r, p in candidate) - order[s])
                for s in sizes
            )
            if dev < best_dev:
                best_dev = dev
                best = candidate

    return best
