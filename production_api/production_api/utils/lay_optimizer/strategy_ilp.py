"""
ILP (Integer Linear Programming) Strategy
==========================================

Finds the absolute minimum number of lays via set cover with bounded enumeration.

Algorithm:
- k=1: single lay with one ratio × one ply count. Simple scan.
- k=2: DP search across (plies1, plies2) pairs. Per-size feasible (r1,r2) pairs
  enumerated, then DP finds best assignment within marker capacity.
- k=3+: greedy decomposition — pick best lay 1, then solve k-1 for remainder.

Overcut is allowed within tolerance_pct per size.
"""

import math
from typing import Dict, List, Optional, Tuple

from .common import generate_candidate_ratios, candidate_plies


def _solve_ilp_greedy(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    target_k: int,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Greedy solver for k lays: pick the best lay, recurse for k-1.
    'Best' = covers the most total quantity while keeping remainder solvable.
    """
    if target_k <= 0:
        return [] if all(order[s] <= 0 for s in sizes) else None

    active = [s for s in sizes if order[s] > 0]
    if not active:
        return []

    cands = set()
    max_rem = max(order[s] for s in active)
    min_rem = min(order[s] for s in active)

    cands.add(min_rem)
    cands.add(max_rem)
    for s in active:
        r = order[s]
        cands.add(r)
        for d in range(1, min(int(math.sqrt(r)) + 1, max_plies + 1)):
            if r % d == 0:
                cands.add(d)
                cands.add(r // d)
        for rv in range(1, min(max_pieces + 1, r + 1)):
            p = r // rv
            if p > 0:
                cands.add(p)

    valid_plies = sorted(c for c in cands if 0 < c <= max_plies)
    if tubular:
        valid_plies = [c for c in valid_plies if c % 2 == 0]

    best_result = None
    best_score = None

    for plies in valid_plies:
        for ratio in generate_candidate_ratios(order, sizes, max_pieces, plies, mode="all"):
            cut = {s: ratio[s] * plies for s in sizes}

            skip = False
            for s in sizes:
                if order[s] > 0 and cut[s] > order[s] * (1 + tol):
                    skip = True
                    break
            if skip:
                continue

            rem = {s: max(0, order[s] - cut[s]) for s in sizes}
            covered = sum(min(cut[s], order[s]) for s in sizes)
            overcut = sum(max(0, cut[s] - order[s]) for s in sizes)

            if target_k == 1:
                if all(rem[s] == 0 for s in sizes):
                    total_cut = cut
                    if all(abs(total_cut[s] - order[s]) / order[s] <= tol for s in sizes if order[s] > 0):
                        score = (-covered, overcut)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_result = [(ratio, plies)]
            else:
                sub = _solve_ilp_greedy(rem, sizes, max_plies, max_pieces, tol, target_k - 1, tubular)
                if sub is not None:
                    full_plan = [(ratio, plies)] + sub
                    total_cut = {s: 0 for s in sizes}
                    for r, p in full_plan:
                        for s in sizes:
                            total_cut[s] += r[s] * p
                    if all(abs(total_cut[s] - order[s]) / order[s] <= tol for s in sizes if order[s] > 0):
                        total_oc = sum(max(0, total_cut[s] - order[s]) for s in sizes)
                        score = (-covered, total_oc)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_result = full_plan

    return best_result


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Find the absolute minimum number of lays by searching variable ply counts.
    """
    sizes = list(order.keys())
    n = len(sizes)
    tol = tolerance_pct / 100.0

    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    def _within_tolerance(cut):
        for s in sizes:
            diff = cut[s] - order[s]
            if order[s] > 0 and abs(diff) / order[s] > tol:
                return False
        return True

    # ===== TRY k=1 =====
    for plies in candidate_plies(order, sizes, max_plies, max_pieces, tubular):
        for ratio in generate_candidate_ratios(order, sizes, max_pieces, plies, mode="all"):
            cut = {s: ratio[s] * plies for s in sizes}
            if all(cut[s] >= order[s] for s in sizes) and _within_tolerance(cut):
                return [(ratio, plies)]

    # ===== TRY k=2 (DP) =====
    best_2 = None
    best_2_score = float("inf")

    all_ply_cands = candidate_plies(order, sizes, max_plies, max_pieces, tubular)
    B = max_pieces

    def _solve_k2_dp(plies1, plies2):
        """For fixed (plies1, plies2), find ratio1 and ratio2 using DP."""
        active = [s for s in sizes if order[s] > 0]

        per_size = []
        for s in active:
            pairs = []
            seen_pairs = set()
            max_r1 = min(math.ceil(order[s] * (1 + tol) / plies1), B)
            for r1 in range(0, max_r1 + 1):
                cut1 = r1 * plies1
                if cut1 > order[s] * (1 + tol):
                    break
                rem = order[s] - cut1
                for r2 in [math.ceil(rem / plies2) if rem > 0 else 0,
                           rem // plies2 if rem > 0 else 0,
                           (rem // plies2) + 1 if rem > 0 else 0]:
                    if r2 < 0 or r2 > B or (r1, r2) in seen_pairs:
                        continue
                    seen_pairs.add((r1, r2))
                    total_cut = cut1 + r2 * plies2
                    dev = abs(total_cut - order[s])
                    if order[s] > 0 and dev / order[s] <= tol:
                        diff = total_cut - order[s]
                        score = max(0, diff) * 0.1 + max(0, -diff) * 0.5
                        pairs.append((r1, r2, score))
            if not pairs:
                return None
            per_size.append((s, pairs))

        INF = float('inf')
        dp = [[INF] * (B + 1) for _ in range(B + 1)]
        dp[0][0] = 0
        choices = {}

        for idx, (s, pairs) in enumerate(per_size):
            new_dp = [[INF] * (B + 1) for _ in range(B + 1)]
            for b1 in range(B + 1):
                for b2 in range(B + 1):
                    if dp[b1][b2] == INF:
                        continue
                    for r1, r2, oc in pairs:
                        nb1 = b1 + r1
                        nb2 = b2 + r2
                        if nb1 <= B and nb2 <= B:
                            new_cost = dp[b1][b2] + oc
                            if new_cost < new_dp[nb1][nb2]:
                                new_dp[nb1][nb2] = new_cost
                                choices[(idx, nb1, nb2)] = (r1, r2, b1, b2)
            dp = new_dp

        best_cost = INF
        best_b1 = best_b2 = -1
        for b1 in range(B + 1):
            for b2 in range(B + 1):
                if dp[b1][b2] < best_cost:
                    best_cost = dp[b1][b2]
                    best_b1, best_b2 = b1, b2

        if best_cost == INF:
            return None

        ratio1 = {s: 0 for s in sizes}
        ratio2 = {s: 0 for s in sizes}
        b1, b2 = best_b1, best_b2
        for idx in range(len(per_size) - 1, -1, -1):
            s = per_size[idx][0]
            key = (idx, b1, b2)
            if key not in choices:
                return None
            r1, r2, pb1, pb2 = choices[key]
            ratio1[s] = r1
            ratio2[s] = r2
            b1, b2 = pb1, pb2

        plan = [(ratio1, plies1)]
        if any(ratio2[s] > 0 for s in sizes):
            plan.append((ratio2, plies2))

        total_cut = {s: ratio1[s] * plies1 + ratio2[s] * plies2 for s in sizes}
        if _within_tolerance(total_cut):
            return plan
        return None

    for plies1 in all_ply_cands:
        for plies2 in all_ply_cands:
            plan = _solve_k2_dp(plies1, plies2)
            if plan:
                total_cut = {s: sum(r.get(s, 0) * p for r, p in plan) for s in sizes}
                oc = sum(max(0, total_cut[s] - order[s]) for s in sizes)
                uc = sum(max(0, order[s] - total_cut[s]) for s in sizes)
                score = uc * 2 + oc * 1
                if score < best_2_score:
                    best_2_score = score
                    best_2 = plan

    if best_2 is not None:
        return best_2

    # ===== TRY k=3+ (recursive/greedy) =====
    for target_k in range(3, max_lays + 1):
        result = _solve_ilp_greedy(order, sizes, max_plies, max_pieces, tol, target_k, tubular)
        if result is not None:
            return result

    return None
