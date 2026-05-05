"""
Order Match Strategy
=====================

Minimize total deviation from order — cut exactly what was ordered.

Algorithm:
1. Generate smart candidate ply counts from order quantities (divisors, GCD multiples)
2. For each candidate base ply count P:
   a. Floor-divide order by P → base ratio (guaranteed no overcut from base)
   b. Compute remainder per size
   c. Solve remainder greedily with floor-based cleanup lays
3. Also try ceil-based single-lay solutions for small orders
4. Post-optimize: add cleanup lay to reduce remaining deviation
5. Return the plan with lowest total |cut - order| across all sizes

Key difference from ILP: ILP minimizes lays, accepts overcut.
ORDER_MATCH minimizes deviation, accepts more lays if it means less waste.
"""

import math
from typing import Dict, List, Optional, Tuple


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Order match strategy — minimize total deviation from order."""
    sizes = list(order.keys())
    n = len(sizes)
    tol = tolerance_pct / 100.0
    total_order = sum(order.values())

    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    best_plan = None
    best_deviation = float("inf")

    def _total_deviation(plan):
        totals = {s: 0 for s in sizes}
        for ratio, plies in plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        return sum(abs(totals[s] - order[s]) for s in sizes)

    def _check_tolerance(plan):
        totals = {s: 0 for s in sizes}
        for ratio, plies in plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        for s in sizes:
            if order[s] == 0:
                continue
            if abs(totals[s] - order[s]) / order[s] > tol:
                return False
        return True

    def _make_ratio_dict(ratio_list):
        return dict(zip(sizes, ratio_list))

    # --- Generate smart candidate ply counts ---
    qty_values = [v for v in order.values() if v > 0]
    candidates_set = set()

    for q in qty_values:
        for r in range(1, min(max_pieces + 1, q + 1)):
            p = q // r
            if 1 <= p <= max_plies:
                candidates_set.add(p)
            if q % r == 0:
                candidates_set.add(q // r)

    min_qty = min(qty_values)
    for d in range(1, min(min_qty + 1, max_plies + 1)):
        if min_qty % d == 0:
            candidates_set.add(d)

    for p in range(1, min(21, max_plies + 1)):
        candidates_set.add(p)

    for p in range(max(1, max_plies - 5), max_plies + 1):
        candidates_set.add(p)

    if tubular:
        candidates = sorted([p for p in candidates_set if 2 <= p <= max_plies and p % 2 == 0], reverse=True)
    else:
        candidates = sorted([p for p in candidates_set if 1 <= p <= max_plies], reverse=True)

    def _solve_remainder_greedy(remaining, depth, max_p):
        """Greedily solve remainder: pick ply that zeros the most sizes."""
        if depth >= max_lays:
            return None

        max_rem = max(remaining.values())
        if max_rem == 0:
            return []

        if all(remaining[s] <= max(1, order[s] * tol) for s in sizes) and max_rem <= 3:
            return []

        cleanup_candidates = set()
        for s in sizes:
            v = remaining[s]
            if v > 0:
                if v <= max_p:
                    cleanup_candidates.add(v)
                for r in range(1, min(max_pieces + 1, v + 1)):
                    p = v // r
                    if 1 <= p <= max_p:
                        cleanup_candidates.add(p)
                        break

        for p in range(1, min(11, max_p + 1)):
            cleanup_candidates.add(p)

        if tubular:
            cleanup_candidates = {p for p in cleanup_candidates if p % 2 == 0 and p >= 2}

        best_sub = None
        best_sub_dev = float("inf")

        for p in sorted(cleanup_candidates, reverse=True):
            if p <= 0 or p > max_p:
                continue

            ratio = [min(remaining[s] // p, max_pieces) for s in sizes]
            total_ratio = sum(ratio)
            if total_ratio == 0:
                continue
            if total_ratio > max_pieces:
                indexed = sorted(enumerate(ratio), key=lambda x: -x[1])
                new_ratio = [0] * n
                running = 0
                for idx, val in indexed:
                    if running + val <= max_pieces:
                        new_ratio[idx] = val
                        running += val
                ratio = new_ratio
                if sum(ratio) == 0:
                    continue

            new_remaining = {s: remaining[s] - ratio[i] * p for i, s in enumerate(sizes)}

            if any(v < 0 for v in new_remaining.values()):
                continue

            new_dev = sum(new_remaining.values())

            if new_dev == 0:
                return [(_make_ratio_dict(ratio), p)]

            sub = _solve_remainder_greedy(new_remaining, depth + 1, p)
            if sub is not None:
                full = [(_make_ratio_dict(ratio), p)] + sub
                act_remaining = dict(new_remaining)
                for r_dict, pl in sub:
                    for s in sizes:
                        act_remaining[s] -= r_dict.get(s, 0) * pl
                act_dev = sum(abs(v) for v in act_remaining.values())
                if act_dev < best_sub_dev:
                    best_sub_dev = act_dev
                    best_sub = full

        return best_sub

    # === Phase 1: Floor decomposition with smart ply candidates ===
    for base_plies in candidates:
        ratio = [min(order[s] // base_plies, max_pieces) for s in sizes]
        total_ratio = sum(ratio)

        if total_ratio == 0:
            continue
        if total_ratio > max_pieces:
            indexed = sorted(enumerate(ratio), key=lambda x: -x[1])
            new_ratio = [0] * n
            running = 0
            for idx, val in indexed:
                if running + val <= max_pieces:
                    new_ratio[idx] = val
                    running += val
            ratio = new_ratio
            if sum(ratio) == 0:
                continue

        remaining = {s: order[s] - ratio[i] * base_plies for i, s in enumerate(sizes)}

        if any(v < 0 for v in remaining.values()):
            continue

        if all(v == 0 for v in remaining.values()):
            plan = [(_make_ratio_dict(ratio), base_plies)]
            best_deviation = 0
            best_plan = plan
            break

        sub = _solve_remainder_greedy(remaining, 1, base_plies)
        if sub is not None:
            plan = [(_make_ratio_dict(ratio), base_plies)] + sub
            if len(plan) <= max_lays:
                dev = _total_deviation(plan)
                if _check_tolerance(plan) and dev < best_deviation:
                    best_deviation = dev
                    best_plan = plan
                    if dev == 0:
                        break

    # === Phase 2: Ceil-based single-lay ===
    for base_plies in candidates:
        ratio_ceil = [min(math.ceil(order[s] / base_plies), max_pieces) for s in sizes]
        total_ratio = sum(ratio_ceil)
        if total_ratio == 0 or total_ratio > max_pieces:
            continue

        plan = [(_make_ratio_dict(ratio_ceil), base_plies)]
        if _check_tolerance(plan):
            dev = _total_deviation(plan)
            if dev < best_deviation:
                best_deviation = dev
                best_plan = plan
                if dev == 0:
                    break

    # === Phase 3: Post-optimize — add cleanup lay ===
    if best_plan and best_deviation > 0:
        totals = {s: 0 for s in sizes}
        for ratio, plies in best_plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies

        gaps = {s: order[s] - totals[s] for s in sizes}
        max_gap = max(abs(v) for v in gaps.values())

        if max_gap > 0 and len(best_plan) < max_lays:
            cleanup_candidates = set()
            for v in gaps.values():
                if v > 0:
                    cleanup_candidates.add(v)
                    for r in range(1, min(max_pieces + 1, v + 1)):
                        cleanup_candidates.add(v // r)
                        break
            for p in range(1, min(11, max_plies + 1)):
                cleanup_candidates.add(p)

            if tubular:
                cleanup_candidates = {p for p in cleanup_candidates if p % 2 == 0 and p >= 2}

            for cp in sorted(cleanup_candidates):
                if cp <= 0 or cp > max_plies:
                    continue
                cleanup_ratio = {}
                for s in sizes:
                    if gaps[s] > 0:
                        cleanup_ratio[s] = min(round(gaps[s] / cp), max_pieces)
                    else:
                        cleanup_ratio[s] = 0

                if sum(cleanup_ratio.values()) == 0 or sum(cleanup_ratio.values()) > max_pieces:
                    continue

                test_plan = best_plan + [(cleanup_ratio, cp)]
                if len(test_plan) <= max_lays and _check_tolerance(test_plan):
                    dev = _total_deviation(test_plan)
                    if dev < best_deviation:
                        best_deviation = dev
                        best_plan = test_plan

    return best_plan
