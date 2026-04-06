"""
Greedy Subtraction Strategy
============================

Iterative peel-off with variable plies per lay.
Matches how CAD operators manually plan lays.

Algorithm:
1. Lay 1: plies = min(remaining), threshold ratio capped at 2
2. Subsequent lays: try floor/ceil/threshold ratios, pick whichever zeros the most sizes
3. Closing lay when max remainder ≤ threshold: ceil-based single lay to finish
4. Post-optimization: merge last N lays into 1 if possible

Recommended as default — most intuitive, matches operator workflow.
"""

import math
from typing import Dict, List, Optional, Tuple


def _thresh_ratio(remaining: int, plies: int) -> int:
    """Threshold-based ratio matching operator heuristic (2.25x breakpoints)."""
    if remaining <= 0 or plies <= 0:
        return 0
    m = remaining / plies
    if m < 0.5:
        return 0
    if m < 2.25:
        return 1
    return 2


def _solve_greedy_subtraction_inner(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    max_lays: int,
    tubular: bool,
    close_threshold: int,
    overcut_per_size: int,
    max_total_overcut: int,
    lay2_mode: str = "floor",
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Core greedy solver. lay2_mode controls ratio strategy for lay 2+:
    - "floor": use floor division (maximize pieces per lay)
    - "threshold": use threshold-capped ratios (operator style, simpler markers)
    - "best": try both and pick whichever zeros more sizes
    """
    remaining = {s: order[s] for s in sizes}
    plan = []

    def _try_ceil_close(rem, act):
        """Try to close ALL remaining sizes in one ceil-based lay."""
        max_r = max(rem[s] for s in act) if act else 0
        if max_r == 0:
            return None
        best = None
        for p in range(max_r, 0, -1):
            if tubular and p % 2 != 0:
                continue
            ratio = {}
            total_oc = 0
            ok = True
            for s in sizes:
                if rem[s] <= 0:
                    ratio[s] = 0
                    continue
                r = math.ceil(rem[s] / p)
                oc = r * p - rem[s]
                if oc > overcut_per_size:
                    ok = False
                    break
                ratio[s] = r
                total_oc += oc
            if not ok:
                continue
            total_r = sum(ratio.values())
            if total_r == 0 or total_r > max_pieces:
                continue
            if total_oc > max_total_overcut:
                continue
            if best is None or p > best[1]:
                best = (ratio, p)
        return best

    for lay_num in range(max_lays):
        active = [s for s in sizes if remaining[s] > 0]
        if not active:
            break

        max_rem = max(remaining[s] for s in active)

        # Closing lay check
        if max_rem <= close_threshold:
            close = _try_ceil_close(remaining, active)
            if close:
                plan.append(close)
                for s in sizes:
                    remaining[s] -= close[0][s] * close[1]
                break

        active = [s for s in sizes if remaining[s] > 0]
        if not active:
            break

        if lay_num == 0:
            plies = min(remaining[s] for s in active)
            plies = min(plies, max_plies)
            if tubular and plies % 2 != 0:
                plies = max(2, plies - 1)
            ratio = {s: _thresh_ratio(remaining[s], plies) for s in sizes}
        else:
            ceil_close = _try_ceil_close(remaining, active)
            if ceil_close:
                ratio, plies = ceil_close
                plan.append((ratio, plies))
                for s in sizes:
                    remaining[s] -= ratio[s] * plies
                break

            cands: set = set()
            for s in active:
                r = remaining[s]
                cands.add(r)
                for d in range(1, int(math.sqrt(r)) + 1):
                    if r % d == 0:
                        cands.add(d)
                        cands.add(r // d)
                for rv in range(1, min(max_pieces + 1, r + 1)):
                    p = r // rv
                    if p > 0:
                        cands.add(p)
            cands.add(min(remaining[s] for s in active))

            cands_sorted = sorted(c for c in cands if 0 < c <= max_plies)
            if tubular:
                cands_sorted = [c for c in cands_sorted if c % 2 == 0]
            if not cands_sorted:
                cands_sorted = [min(remaining[s] for s in active)]

            best_ratio = None
            best_plies = 0
            best_score = None

            for p in cands_sorted:
                candidates = []

                if lay2_mode in ("floor", "best"):
                    ratio_t = {s: remaining[s] // p if remaining[s] > 0 else 0 for s in sizes}
                    total_r = sum(ratio_t.values())
                    while total_r > max_pieces:
                        rs = max((s for s in sizes if ratio_t[s] > 0), key=lambda s: ratio_t[s])
                        ratio_t[rs] -= 1
                        total_r -= 1
                    if total_r > 0:
                        candidates.append(ratio_t)

                if lay2_mode in ("threshold", "best"):
                    ratio_thresh = {s: _thresh_ratio(remaining[s], p) for s in sizes}
                    total_rt = sum(ratio_thresh.values())
                    if 0 < total_rt <= max_pieces:
                        after_t = {s: remaining[s] - ratio_thresh[s] * p for s in sizes}
                        if all(v >= 0 for v in after_t.values()):
                            candidates.append(ratio_thresh)

                ratio_ceil = {}
                ceil_ok = True
                ceil_total_oc = 0
                for s in sizes:
                    if remaining[s] <= 0:
                        ratio_ceil[s] = 0
                        continue
                    r = math.ceil(remaining[s] / p)
                    oc = r * p - remaining[s]
                    if oc > overcut_per_size:
                        ceil_ok = False
                        break
                    ratio_ceil[s] = r
                    ceil_total_oc += oc
                if ceil_ok and 0 < sum(ratio_ceil.values()) <= max_pieces:
                    if ceil_total_oc <= max_total_overcut:
                        candidates.append(ratio_ceil)

                for cand in candidates:
                    after = {s: remaining[s] - cand.get(s, 0) * p for s in sizes}
                    if any(after[s] < 0 for s in sizes):
                        zeroed = len(active)
                        still = 0
                        total_after = 0
                    else:
                        zeroed = sum(1 for s in active if after[s] == 0)
                        still = sum(1 for s in sizes if after[s] > 0)
                        total_after = sum(after[s] for s in sizes if after[s] > 0)

                    sc = (-zeroed, still, total_after)
                    if best_score is None or sc < best_score:
                        best_score = sc
                        best_ratio = dict(cand)
                        best_plies = p

            if best_ratio is None:
                break
            ratio, plies = best_ratio, best_plies

        # Clamp and apply
        total_r = sum(ratio.values())
        while total_r > max_pieces:
            rs = max((s for s in sizes if ratio[s] > 0), key=lambda s: ratio[s])
            ratio[rs] -= 1
            total_r -= 1
        if total_r == 0:
            break

        for s in sizes:
            remaining[s] -= ratio[s] * plies
        plan.append((ratio, plies))

    # Final residual
    if any(remaining.get(s, 0) > 0 for s in sizes):
        for p in range(1, max(remaining.get(s, 1) for s in sizes) + 2):
            if tubular and p % 2 != 0:
                continue
            ratio = {s: math.ceil(remaining[s] / p) if remaining[s] > 0 else 0 for s in sizes}
            if 0 < sum(ratio.values()) <= max_pieces:
                plan.append((ratio, p))
                break

    # Post-optimization: merge last N lays into 1 ceil-based lay
    if len(plan) >= 2:
        for merge_count in [3, 2]:
            if len(plan) < merge_count:
                continue
            merge_remaining = {s: 0 for s in sizes}
            for ratio_m, plies_m in plan[-merge_count:]:
                for s in sizes:
                    merge_remaining[s] += ratio_m.get(s, 0) * plies_m
            merge_active = [s for s in sizes if merge_remaining[s] > 0]
            if not merge_active:
                continue
            merged = _try_ceil_close(merge_remaining, merge_active)
            if merged:
                m_ratio, m_plies = merged
                m_overcut = sum(
                    m_ratio[s] * m_plies - merge_remaining[s]
                    for s in sizes if merge_remaining[s] > 0
                )
                if m_overcut <= max_total_overcut:
                    plan = plan[:-merge_count] + [merged]
                    break

    return plan if plan else None


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 12,
    tubular: bool = False,
    close_threshold: int = 50,
    overcut_per_size: int = 5,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Greedy subtraction strategy — runs multiple variants (floor, threshold, best)
    and picks the plan with fewest lays, then fewest overcut as tiebreaker.
    """
    sizes = list(order.keys())
    total_order = sum(order.values())
    max_total_overcut = max(int(total_order * tolerance_pct / 100), len(sizes) * overcut_per_size)

    best_plan = None
    best_key = None

    for mode in ["floor", "threshold", "best"]:
        plan = _solve_greedy_subtraction_inner(
            order, sizes, max_plies, max_pieces, max_lays, tubular,
            close_threshold, overcut_per_size, max_total_overcut, lay2_mode=mode,
        )
        if plan is None:
            continue
        totals = {s: 0 for s in sizes}
        for ratio, plies in plan:
            for s in sizes:
                totals[s] += ratio.get(s, 0) * plies
        overcut = sum(max(0, totals[s] - order[s]) for s in sizes)
        key = (len(plan), overcut)
        if best_key is None or key < best_key:
            best_key = key
            best_plan = plan

    return best_plan
