"""
Knapsack Transformation Strategy for Cutting Order Planning (COP)
=================================================================

Based on Filipič, Fister & Mernik (2006): "Optimization of markers in
clothing industry" — transforms COP into a bounded knapsack problem.

APPROACH
--------
The COP is framed as: select a set of (marker_ratio, ply_count) items
from a knapsack, where:
  - Each item = one lay configuration
  - "Capacity" = demand per size (with ±tol% band)
  - Objective = minimize number of items (lays)

Implementation:
1. Build pattern pool — proportional ratios at key ply counts,
   compressed variants when demand exceeds marker capacity
2. Greedy set cover with randomized restarts
3. Improvement phase — remove/swap/ply-tune to reduce lay count
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from .common import (
    check_tolerance,
    total_deviation,
    generate_candidate_ratios,
)
from . import strategy_greedy as _greedy


# ---------------------------------------------------------------------------
# Pattern pool generation (knapsack items)
# ---------------------------------------------------------------------------

def _build_pattern_pool(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    tubular: bool,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Generate diverse (ratio, plies) pairs as candidate lays.
    
    Phase 1: Standard ratios at key ply counts
    Phase 2: Compressed proportional ratios for high-demand orders
    Phase 3: Single-size cleanup patterns
    """
    pool: List[Tuple[Dict[str, int], int]] = []
    seen = set()
    hi = {s: math.floor(order[s] * (1 + tol)) for s in sizes}
    total_order = sum(order[s] for s in sizes)

    def _add(ratio: Dict[str, int], plies: int) -> bool:
        if plies <= 0 or plies > max_plies:
            return False
        if tubular and plies % 2 != 0:
            return False
        total_r = sum(ratio.get(s, 0) for s in sizes)
        if total_r <= 0 or total_r > max_pieces:
            return False
        # Don't add patterns that overshoot any size
        for s in sizes:
            if ratio.get(s, 0) * plies > hi[s]:
                return False
        key = (tuple(ratio.get(s, 0) for s in sizes), plies)
        if key in seen:
            return False
        seen.add(key)
        pool.append((dict(ratio), plies))
        return True

    # --- Key ply counts ---
    ply_set = set()
    ply_set.add(max_plies)
    for s in sizes:
        q = order[s]
        if q <= 0:
            continue
        for r in range(1, min(max_pieces + 1, q + 1)):
            for p in [q // r, math.ceil(q / r)]:
                if 0 < p <= max_plies:
                    ply_set.add(p)
    for frac in [0.1, 0.2, 0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1.0]:
        ply_set.add(max(1, int(max_plies * frac)))
    if tubular:
        ply_set = {p for p in ply_set if p > 0 and p % 2 == 0}
    else:
        ply_set = {p for p in ply_set if p > 0}

    for plies in sorted(ply_set):
        # Standard candidate ratios
        ratios = generate_candidate_ratios(order, sizes, max_pieces, plies, mode="all")
        for r in ratios:
            _add(r, plies)

        # Compressed proportional when demand/ply > max_pieces
        demand_per_ply = {s: order[s] / plies for s in sizes}
        total_dpp = sum(demand_per_ply[s] for s in sizes)
        if total_dpp > max_pieces:
            scale = max_pieces / total_dpp
            
            # Floor + fractional fill
            r_floor = {}
            total_f = 0
            for s in sizes:
                v = int(demand_per_ply[s] * scale)
                v = max(0, min(v, max_pieces - total_f))
                r_floor[s] = v
                total_f += v
            remaining = max_pieces - total_f
            frac = {s: (demand_per_ply[s] * scale) % 1 for s in sizes}
            for s in sorted(sizes, key=lambda s: -frac[s]):
                if remaining <= 0:
                    break
                r_floor[s] += 1
                remaining -= 1
            _add(r_floor, plies)

            # Large-first variant
            r_large = {s: 0 for s in sizes}
            total_l = 0
            for s in sorted(sizes, key=lambda s: -order[s]):
                v = min(math.ceil(demand_per_ply[s]), max_pieces - total_l)
                v = max(0, v)
                r_large[s] = v
                total_l += v
                if total_l >= max_pieces:
                    break
            _add(r_large, plies)

            # Small-first variant
            r_small = {s: 0 for s in sizes}
            total_s = 0
            for s in sorted(sizes, key=lambda s: order[s]):
                v = min(math.ceil(demand_per_ply[s]), max_pieces - total_s)
                v = max(0, v)
                r_small[s] = v
                total_s += v
                if total_s >= max_pieces:
                    break
            _add(r_small, plies)

    # Single-size cleanup patterns
    for s in sizes:
        if order[s] <= 0:
            continue
        for r_val in range(1, min(max_pieces + 1, order[s] + 1)):
            d = {sz: 0 for sz in sizes}
            d[s] = r_val
            for p in [1, 2, 3, 5, 7, 10, 14, 20, 28, 30, 50]:
                if 0 < p <= max_plies:
                    _add(d, p)

    return pool


# ---------------------------------------------------------------------------
# Coverage scoring
# ---------------------------------------------------------------------------

def _coverage_score(
    ratio: Dict[str, int],
    plies: int,
    remaining: Dict[str, int],
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
) -> float:
    """
    Score a (ratio, plies) item by how well it covers remaining demand.
    Rewards useful coverage, penalizes waste on already-fulfilled sizes.
    """
    score = 0.0
    for s in sizes:
        cut = ratio.get(s, 0) * plies
        if remaining[s] > 0:
            useful = min(cut, remaining[s])
            score += useful * 2.0
            overcut = cut - remaining[s]
            if overcut > 0:
                score -= overcut * 0.5
        else:
            score -= cut * 1.0
    return score


# ---------------------------------------------------------------------------
# Greedy set cover
# ---------------------------------------------------------------------------

def _greedy_cover(
    pool: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
    max_lays: int,
    randomize: float = 0.0,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Greedy set cover: iteratively pick the best-scoring pool item.
    """
    lo = {s: math.ceil(order[s] * (1 - tol)) for s in sizes}
    hi = {s: math.floor(order[s] * (1 + tol)) for s in sizes}
    remaining = dict(order)
    cut = {s: 0 for s in sizes}
    plan = []

    for _ in range(max_lays):
        # Check if we're done
        if all(cut[s] >= lo[s] for s in sizes if order[s] > 0):
            break

        # Score all feasible items
        scored = []
        for ratio, plies in pool:
            # Check hi-bound feasibility
            if any(cut[s] + ratio.get(s, 0) * plies > hi[s] for s in sizes):
                continue
            sc = _coverage_score(ratio, plies, remaining, order, sizes, tol)
            if sc > 0:
                scored.append((sc, ratio, plies))

        if not scored:
            break

        scored.sort(key=lambda x: -x[0])
        if randomize > 0 and random.random() < randomize:
            k = max(1, int(len(scored) * 0.15))
            _, ratio, plies = random.choice(scored[:k])
        else:
            _, ratio, plies = scored[0]

        plan.append((dict(ratio), plies))
        for s in sizes:
            c = ratio.get(s, 0) * plies
            cut[s] += c
            remaining[s] = max(0, remaining[s] - c)

    # Check feasibility
    if all(lo[s] <= cut[s] <= hi[s] for s in sizes if order[s] > 0):
        return plan
    return None


# ---------------------------------------------------------------------------
# Improvement phase
# ---------------------------------------------------------------------------

def _improve(
    plan: List[Tuple[Dict[str, int], int]],
    pool: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    tol: float,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Try to reduce lay count or deviation:
    1. Remove a lay if remaining lays still cover demand
    2. Merge two lays into one from the pool
    3. Replace a lay with a better pool item
    4. Ply-tune ±1/±2
    """
    best = list(plan)
    best_n = len(best)
    best_dev = total_deviation(best, order, sizes)
    improved = True

    while improved:
        improved = False

        # Strategy 1: Try removing each lay
        for victim in range(len(best)):
            reduced = [lay for i, lay in enumerate(best) if i != victim]
            if not reduced:
                continue
            if check_tolerance(reduced, order, sizes, tol):
                dev = total_deviation(reduced, order, sizes)
                if len(reduced) < best_n or (len(reduced) == best_n and dev < best_dev):
                    best = reduced
                    best_n = len(reduced)
                    best_dev = dev
                    improved = True
                    break

        if improved:
            continue

        # Strategy 2: Merge pairs — remove 2, replace with 1 from pool
        if len(best) >= 3:
            for i in range(len(best)):
                for j in range(i + 1, len(best)):
                    reduced = [lay for k, lay in enumerate(best) if k != i and k != j]
                    for ratio, plies in pool:
                        trial = reduced + [(dict(ratio), plies)]
                        if check_tolerance(trial, order, sizes, tol):
                            if len(trial) < best_n:
                                best = trial
                                best_n = len(trial)
                                best_dev = total_deviation(trial, order, sizes)
                                improved = True
                                break
                    if improved:
                        break
                if improved:
                    break

        if improved:
            continue

        # Strategy 3: Replace each lay with a better pool item
        for i in range(len(best)):
            for ratio, plies in pool:
                trial = list(best)
                trial[i] = (dict(ratio), plies)
                if check_tolerance(trial, order, sizes, tol):
                    dev = total_deviation(trial, order, sizes)
                    if dev < best_dev:
                        best = trial
                        best_dev = dev
                        # Don't set improved=True (same lay count)

        # Strategy 4: Ply tune ±1/±2
        for i in range(len(best)):
            r, p = best[i]
            for delta in [-2, -1, 1, 2]:
                p_new = max(1, min(max_plies, p + delta))
                if p_new == p:
                    continue
                trial = list(best)
                trial[i] = (dict(r), p_new)
                if check_tolerance(trial, order, sizes, tol):
                    dev = total_deviation(trial, order, sizes)
                    if dev < best_dev:
                        best = trial
                        best_dev = dev

    return best


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

N_RESTARTS = 16

def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Knapsack transformation solver.
    
    Seeded from greedy_subtraction as baseline.
    Own algorithm: static pool + greedy set cover + improvement.
    """
    sizes = list(order.keys())
    tol = tolerance_pct / 100.0
    if not sizes:
        return None

    pool = _build_pattern_pool(order, sizes, max_plies, max_pieces, tol, tubular)
    if not pool:
        return None

    best_plan = None
    best_lays = max_lays + 1
    best_dev = float('inf')

    def _update(plan):
        nonlocal best_plan, best_lays, best_dev
        if plan is None:
            return
        if not check_tolerance(plan, order, sizes, tol):
            return
        n = len(plan)
        dev = total_deviation(plan, order, sizes)
        if n < best_lays or (n == best_lays and dev < best_dev):
            best_plan = list(plan)
            best_lays = n
            best_dev = dev

    # Seed: greedy_subtraction baseline
    try:
        seed = _greedy.solve(order, max_plies, max_pieces, tolerance_pct, max_lays, tubular)
        _update(seed)
    except Exception:
        pass

    # Greedy restarts with increasing randomization
    for restart in range(N_RESTARTS):
        rand = 0.0 if restart == 0 else min(0.6, 0.1 + restart * 0.04)
        plan = _greedy_cover(pool, order, sizes, tol, max_lays, rand)
        if plan:
            plan = _improve(plan, pool, order, sizes, max_plies, tol)
            _update(plan)

    if best_plan is None:
        return None

    best_plan.sort(key=lambda x: -x[1])
    return best_plan
