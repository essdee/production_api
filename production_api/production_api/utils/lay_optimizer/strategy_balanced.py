"""
Balanced Strategy
==================

Fewest lays with densest markers — trade-off between lay count and efficiency.

Algorithm:
For k = 1, 2, 3...:
  k=1: scan for single-lay covers
  k=2: DP search across (plies1, plies2) pairs, density-aware scoring
  k=3+: greedy peel — pick densest feasible lay first, recurse
  
Within each k, keep the plan with highest avg density.
Stop at first k producing avg density ≥ 60% of max_pieces.

Key difference from ILP: ILP accepts ANY 2-lay solution.
BALANCED rejects poor-density 2-lay solutions and tries 3 lays
with denser markers instead — only if the density gain justifies it.
"""

import math
import time as _time
from typing import Dict, List, Optional, Tuple

from .common import generate_candidate_ratios


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Balanced strategy — fewest lays with densest markers."""
    sizes = list(order.keys())
    n = len(sizes)
    total_order = sum(order.values())
    tol = tolerance_pct / 100.0
    density_floor = max_pieces * 0.6

    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    def _within_tolerance(cut):
        for s in sizes:
            if order[s] > 0 and abs(cut[s] - order[s]) / order[s] > tol:
                return False
        return True

    def _plan_stats(plan):
        totals = {s: 0 for s in sizes}
        for ratio, plies in plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        oc = sum(max(0, totals[s] - order[s]) for s in sizes)
        uc = sum(max(0, order[s] - totals[s]) for s in sizes)
        densities = [sum(r.values()) for r, _ in plan]
        avg_d = sum(densities) / len(densities) if densities else 0
        min_d = min(densities) if densities else 0
        return oc, uc, avg_d, min_d

    def _balanced_score(plan):
        oc, uc, avg_d, min_d = _plan_stats(plan)
        n_lays = len(plan)
        density_ratio = avg_d / max_pieces if max_pieces > 0 else 0
        return (n_lays, -density_ratio, uc * 2 + oc)

    # --- Candidate ply generation ---
    def _cand_plies():
        cands = set()
        for s in sizes:
            v = order[s]
            if v <= 0:
                continue
            for r in range(1, min(max_pieces + 1, v + 1)):
                p = v // r
                if 1 <= p <= max_plies:
                    cands.add(p)
                p2 = math.ceil(v / r) if r > 0 else 0
                if 1 <= p2 <= max_plies:
                    cands.add(p2)
        cands.add(1)
        cands.add(max_plies)
        if max_plies > 1:
            cands.add(max_plies // 2)
            cands.add(max_plies // 3)
            cands.add(max_plies // 4)
        total_o = sum(order.values())
        for r in range(max(1, max_pieces - 2), max_pieces + 1):
            p = total_o // r
            if 1 <= p <= max_plies:
                cands.add(p)
                if p > 1:
                    cands.add(p - 1)
                if p < max_plies:
                    cands.add(p + 1)
        valid = sorted(cands)
        if tubular:
            valid = [p for p in valid if p % 2 == 0]
        return valid

    ply_cands = _cand_plies()

    best_plan = None
    best_score = None

    # ===== TRY k=1 =====
    for plies in ply_cands:
        for ratio in generate_candidate_ratios(order, sizes, max_pieces, plies, mode="all"):
            cut = {s: ratio[s] * plies for s in sizes}
            if all(cut[s] >= order[s] for s in sizes) and _within_tolerance(cut):
                plan = [(ratio, plies)]
                score = _balanced_score(plan)
                if best_score is None or score < best_score:
                    best_score = score
                    best_plan = plan

    if best_plan is not None:
        return best_plan

    # ===== TRY k=2: DP approach =====
    B = max_pieces
    _k2_start = _time.monotonic()
    _K2_TIMEOUT = 3.0

    _ideal_plies = total_order // max(1, max_pieces)
    _ply_scored = sorted(ply_cands, key=lambda p: abs(p - _ideal_plies))
    _ply_cands_k2 = sorted(_ply_scored[:30])

    for plies1 in _ply_cands_k2:
        if _time.monotonic() - _k2_start > _K2_TIMEOUT:
            break
        for plies2 in _ply_cands_k2:
            if _time.monotonic() - _k2_start > _K2_TIMEOUT:
                break
            if plies2 > plies1:
                continue

            per_size = []
            feasible = True
            for s in sizes:
                if order[s] <= 0:
                    continue
                pairs = []
                seen = set()
                max_r1 = min(math.ceil(order[s] * (1 + tol) / plies1), B)
                for r1 in range(0, max_r1 + 1):
                    cut1 = r1 * plies1
                    if cut1 > order[s] * (1 + tol):
                        break
                    rem = order[s] - cut1
                    for r2_cand in [math.ceil(rem / plies2) if rem > 0 else 0,
                                    rem // plies2 if rem > 0 else 0,
                                    (rem // plies2) + 1 if rem > 0 else 0]:
                        if r2_cand < 0 or r2_cand > B or (r1, r2_cand) in seen:
                            continue
                        seen.add((r1, r2_cand))
                        total_cut = cut1 + r2_cand * plies2
                        if order[s] > 0 and abs(total_cut - order[s]) / order[s] <= tol:
                            diff = total_cut - order[s]
                            waste_score = max(0, diff) * 0.1 + max(0, -diff) * 0.5
                            pairs.append((r1, r2_cand, waste_score))
                if not pairs:
                    feasible = False
                    break
                if len(pairs) > 10:
                    pairs.sort(key=lambda x: x[2])
                    pairs = pairs[:10]
                per_size.append((s, pairs))

            if not feasible:
                continue

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
                        for r1, r2, sc in pairs:
                            nb1 = b1 + r1
                            nb2 = b2 + r2
                            if nb1 <= B and nb2 <= B:
                                new_cost = dp[b1][b2] + sc
                                if new_cost < new_dp[nb1][nb2]:
                                    new_dp[nb1][nb2] = new_cost
                                    choices[(idx, nb1, nb2)] = (r1, r2, b1, b2)
                dp = new_dp

            for b1 in range(B, -1, -1):
                for b2 in range(B, -1, -1):
                    if dp[b1][b2] == INF:
                        continue

                    ratio1 = {s: 0 for s in sizes}
                    ratio2 = {s: 0 for s in sizes}
                    cb1, cb2 = b1, b2
                    valid = True
                    for idx in range(len(per_size) - 1, -1, -1):
                        s_name = per_size[idx][0]
                        key = (idx, cb1, cb2)
                        if key not in choices:
                            valid = False
                            break
                        r1, r2, pb1, pb2 = choices[key]
                        ratio1[s_name] = r1
                        ratio2[s_name] = r2
                        cb1, cb2 = pb1, pb2

                    if not valid:
                        continue

                    plan = []
                    if any(ratio1[s] > 0 for s in sizes):
                        plan.append((ratio1, plies1))
                    if any(ratio2[s] > 0 for s in sizes):
                        plan.append((ratio2, plies2))
                    if not plan:
                        continue

                    total_cut = {s: sum(r.get(s, 0) * p for r, p in plan) for s in sizes}
                    if _within_tolerance(total_cut):
                        score = _balanced_score(plan)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_plan = plan

    if best_plan is not None:
        _, _, avg_d, _ = _plan_stats(best_plan)
        if avg_d >= density_floor:
            return best_plan

    # ===== TRY k=3+: Greedy peel with density preference =====
    _k3_start = _time.monotonic()
    _K3_TIMEOUT = 2.0

    for target_k in range(3, max_lays + 1):
        if _time.monotonic() - _k3_start > _K3_TIMEOUT:
            break
        found_at_k = _solve_balanced_greedy(
            order, sizes, max_plies, max_pieces, tol, target_k,
            ply_cands, tubular
        )
        if found_at_k is not None:
            score = _balanced_score(found_at_k)
            if best_score is None or score < best_score:
                best_score = score
                best_plan = found_at_k
            _, _, avg_d, _ = _plan_stats(found_at_k)
            if avg_d >= density_floor:
                break

    return best_plan


def _solve_balanced_greedy(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_k: int,
    ply_cands: List[int],
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Greedy peel for k=3+: at each step, pick the densest feasible lay."""

    def _within_tol(totals):
        for s in sizes:
            if order[s] > 0 and abs(totals[s] - order[s]) / order[s] > tol:
                return False
        return True

    _node_count = [0]
    _MAX_NODES = 5000

    def _solve_greedy_inner(remaining, budget):
        _node_count[0] += 1
        if _node_count[0] > _MAX_NODES:
            return None
        if budget <= 0:
            return [] if all(remaining[s] <= 0 for s in sizes) else None

        active = [s for s in sizes if remaining[s] > 0]
        if not active:
            return []

        max_rem = max(remaining[s] for s in active)
        if max_rem <= 0:
            return []

        if budget == 1:
            best_lay = None
            best_density = 0
            best_waste = float('inf')
            for plies in ply_cands:
                if plies > max_plies:
                    continue
                ratio = {s: math.ceil(remaining[s] / plies) if remaining[s] > 0 else 0 for s in sizes}
                total_r = sum(ratio.values())
                if total_r == 0 or total_r > max_pieces:
                    continue
                totals = {s: (order[s] - remaining[s]) + ratio[s] * plies for s in sizes}
                if not _within_tol(totals):
                    continue
                waste = sum(ratio[s] * plies - remaining[s] for s in sizes if remaining[s] > 0)
                if total_r > best_density or (total_r == best_density and waste < best_waste):
                    best_density = total_r
                    best_waste = waste
                    best_lay = (ratio, plies)
            return [best_lay] if best_lay else None

        best_result = None
        best_result_density = 0

        sample_plies = sorted(set(
            [p for p in ply_cands if p <= max_plies]
        ), reverse=True)
        _branch_cap = {1: 9999, 2: 15, 3: 8}.get(budget, 5)
        if len(sample_plies) > _branch_cap:
            mid = len(sample_plies) // 3
            if budget == 2:
                sample_plies = sample_plies[:10] + sample_plies[mid:mid + 3] + sample_plies[-2:]
            else:
                sample_plies = sample_plies[:_branch_cap]

        for plies in sample_plies:
            ratio = {s: remaining[s] // plies if remaining[s] > 0 else 0 for s in sizes}
            total_r = sum(ratio.values())

            if total_r == 0:
                continue
            if total_r > max_pieces:
                scale = max_pieces / total_r
                ratio = {s: max(0, int(ratio[s] * scale)) for s in sizes}
                total_r = sum(ratio.values())
                if total_r == 0:
                    continue

            while total_r < max_pieces:
                gaps = [(remaining[s] - ratio[s] * plies, s) for s in active if ratio[s] * plies < remaining[s]]
                if not gaps:
                    break
                gaps.sort(reverse=True)
                bumped = False
                for _, s in gaps:
                    if total_r + 1 <= max_pieces:
                        test_cut = (order[s] - remaining[s]) + (ratio[s] + 1) * plies
                        if order[s] > 0 and abs(test_cut - order[s]) / order[s] > tol:
                            continue
                        ratio[s] += 1
                        total_r += 1
                        bumped = True
                        break
                if not bumped:
                    break

            density = sum(ratio.values())
            if density <= best_result_density * 0.8:
                continue

            new_rem = {s: remaining[s] - ratio[s] * plies for s in sizes}
            if any(new_rem[s] < -order[s] * tol for s in sizes if order[s] > 0):
                continue

            sub = _solve_greedy_inner(new_rem, budget - 1)
            if sub is not None:
                full_plan = [(ratio, plies)] + sub
                full_density = sum(sum(r.values()) for r, _ in full_plan) / len(full_plan)
                if full_density > best_result_density:
                    best_result_density = full_density
                    best_result = full_plan

        return best_result

    result = _solve_greedy_inner(dict(order), max_k)
    if result is None:
        return None

    totals = {s: 0 for s in sizes}
    for ratio, plies in result:
        for s in sizes:
            totals[s] += ratio.get(s, 0) * plies

    for s in sizes:
        if order[s] > 0 and abs(totals[s] - order[s]) / order[s] > tol:
            return None

    return result
