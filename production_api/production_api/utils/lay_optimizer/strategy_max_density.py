"""
Max Density Strategy
=====================

Pack markers close to max_pieces per ply, minimize unique markers.

Algorithm:
1. Build the densest ratio that fits max_pieces by scaling order proportions
2. Use that ratio at max_plies, then handle remainder
3. Try multiple scale factors to find best density vs waste trade-off
4. Prefer plans with fewer unique markers and higher avg density

Goal: Every marker should be as close to max_pieces as possible.
This minimizes the number of unique markers the CAD team needs to draft
and maximizes fabric utilization within each marker.
"""

import math
from typing import Dict, List, Optional, Tuple

from .common import check_tolerance, total_deviation


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Max density strategy — maximize pieces per marker."""
    sizes = list(order.keys())
    n = len(sizes)
    tol = tolerance_pct / 100.0
    total_order = sum(order.values())

    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    def _check_tol(plan):
        return check_tolerance(plan, order, sizes, tol)

    def _total_dev(plan):
        return total_deviation(plan, order, sizes)

    def _avg_density(plan):
        if not plan:
            return 0
        return sum(sum(r.values()) for r, _ in plan) / len(plan)

    def _unique_markers(plan):
        seen = set()
        for r, _ in plan:
            key = tuple(sorted(r.items()))
            seen.add(key)
        return len(seen)

    best_plan = None
    best_score = None

    def _build_dense_ratio(sizes_subset, order_subset, target_density):
        """Build a ratio proportional to order for given sizes, summing to target_density."""
        sub_total = sum(order_subset[s] for s in sizes_subset)
        if sub_total == 0:
            return None
        raw = {s: order_subset[s] / sub_total * target_density for s in sizes_subset}
        ratio = {s: max(0, round(raw[s])) for s in sizes_subset}

        total_r = sum(ratio.values())
        attempts = 0
        while total_r > target_density and attempts < 50:
            s_min = min((s for s in sizes_subset if ratio[s] > 0),
                        key=lambda s: order_subset[s] / max(ratio[s], 1))
            ratio[s_min] = max(0, ratio[s_min] - 1)
            total_r -= 1
            attempts += 1
        while total_r < target_density and attempts < 100:
            s_max = max(sizes_subset,
                        key=lambda s: order_subset[s] / max(ratio[s], 1) if ratio[s] > 0 else float('inf'))
            ratio[s_max] += 1
            total_r += 1
            attempts += 1

        if sum(ratio.values()) == 0 or sum(ratio.values()) > max_pieces:
            return None
        return ratio

    def _tile_ratio(ratio, remaining, plan_so_far):
        """Tile a ratio across lays at max_plies."""
        plan_add = []
        rem = dict(remaining)

        while len(plan_so_far) + len(plan_add) < max_lays:
            plies = max_plies
            can_add = False
            for s in sizes:
                r = ratio.get(s, 0)
                if r > 0 and rem[s] > 0:
                    can_add = True
                    plies = min(plies, rem[s] // r)

            if not can_add or plies <= 0:
                break
            if tubular and plies % 2 != 0:
                plies = max(0, plies - 1)
            if plies <= 0:
                break

            plan_add.append((dict(ratio), plies))
            for s in sizes:
                rem[s] -= ratio.get(s, 0) * plies

        return plan_add, rem

    def _add_cleanup_lays(remaining, plan_so_far):
        """Add cleanup lays for remainder, maximizing density per lay."""
        plan_add = []
        rem = dict(remaining)

        for _ in range(max_lays - len(plan_so_far) - len(plan_add)):
            active = [s for s in sizes if rem[s] > 0]
            if not active:
                break

            max_rem = max(rem[s] for s in active)
            if max_rem == 0:
                break

            cleanup_candidates = set()
            for s in active:
                v = rem[s]
                if v <= 0:
                    continue
                cleanup_candidates.add(v)
                for r in range(1, min(max_pieces + 1, v + 1)):
                    p = v // r
                    if 1 <= p <= max_plies:
                        cleanup_candidates.add(p)
                    if r >= 8:
                        break

            for p in range(1, min(21, max_plies + 1)):
                cleanup_candidates.add(p)

            if tubular:
                cleanup_candidates = {p for p in cleanup_candidates if p % 2 == 0 and p >= 2}

            best_cp = None
            best_cp_score = None

            for cp in sorted(cleanup_candidates, reverse=True):
                if cp <= 0 or cp > max_plies:
                    continue

                c_ratio = {}
                for s in sizes:
                    if rem[s] > 0:
                        c_ratio[s] = min(rem[s] // cp, max_pieces)
                    else:
                        c_ratio[s] = 0

                c_total = sum(c_ratio.values())
                if c_total == 0 or c_total > max_pieces:
                    continue

                # Try bumping some to ceil without exceeding tolerance
                for s in active:
                    if c_ratio[s] * cp < rem[s]:
                        bumped = c_ratio[s] + 1
                        if bumped <= max_pieces and c_total - c_ratio[s] + bumped <= max_pieces:
                            total_for_s = sum(r.get(s, 0) * p for r, p in plan_so_far + plan_add) + bumped * cp
                            if order[s] > 0 and abs(total_for_s - order[s]) / order[s] <= tol:
                                c_ratio[s] = bumped
                                c_total = sum(c_ratio.values())

                if c_total == 0 or c_total > max_pieces:
                    continue

                covered = sum(c_ratio[s] * cp for s in sizes)
                score = (-c_total, -covered)

                if best_cp_score is None or score < best_cp_score:
                    test_plan = plan_so_far + plan_add + [(c_ratio, cp)]
                    if _check_tol(test_plan):
                        best_cp_score = score
                        best_cp = (c_ratio, cp)

            if best_cp:
                plan_add.append(best_cp)
                c_r, c_p = best_cp
                for s in sizes:
                    rem[s] -= c_r.get(s, 0) * c_p
            else:
                max_r = max(rem[s] for s in active) if active else 0
                if max_r > 0 and max_r <= 20:
                    for cp in range(max_r, 0, -1):
                        if tubular and cp % 2 != 0:
                            continue
                        c_ratio = {s: min(math.ceil(rem[s] / cp), max_pieces) if rem[s] > 0 else 0 for s in sizes}
                        c_total = sum(c_ratio.values())
                        if 0 < c_total <= max_pieces:
                            test_plan = plan_so_far + plan_add + [(c_ratio, cp)]
                            if _check_tol(test_plan):
                                plan_add.append((c_ratio, cp))
                                break
                break

        return plan_add

    def _evaluate_plan(plan):
        """Score a plan — lower is better."""
        if not plan or not _check_tol(plan):
            return None
        dev = _total_dev(plan)
        avg_d = _avg_density(plan)
        uniq = _unique_markers(plan)
        return (-avg_d, uniq, dev)

    # --- Strategy A: Dense proportional ratio, tile + cleanup ---
    for target_density in range(max_pieces, max(0, max_pieces - 6), -1):
        ratio = _build_dense_ratio(sizes, order, target_density)
        if ratio is None:
            continue

        plan_add, remaining = _tile_ratio(ratio, dict(order), [])
        if not plan_add:
            continue

        plan = list(plan_add)
        cleanups = _add_cleanup_lays(remaining, plan)
        plan.extend(cleanups)

        if len(plan) <= max_lays:
            score = _evaluate_plan(plan)
            if score is not None and (best_score is None or score < best_score):
                best_score = score
                best_plan = plan

    # --- Strategy B: Exclude small sizes from main marker ---
    if n >= 4:
        sorted_by_qty = sorted(sizes, key=lambda s: order[s])
        for exclude_count in range(1, min(3, n - 2)):
            excluded = sorted_by_qty[:exclude_count]
            included = [s for s in sizes if s not in excluded]

            for target_density in range(max_pieces, max(max_pieces - 4, len(included)), -1):
                sub_order = {s: order[s] for s in included}
                ratio = _build_dense_ratio(included, sub_order, min(target_density, max_pieces))
                if ratio is None:
                    continue

                full_ratio = {s: ratio.get(s, 0) for s in sizes}

                plan_add, remaining = _tile_ratio(full_ratio, dict(order), [])
                if not plan_add:
                    continue

                plan = list(plan_add)
                cleanups = _add_cleanup_lays(remaining, plan)
                plan.extend(cleanups)

                if len(plan) <= max_lays:
                    score = _evaluate_plan(plan)
                    if score is not None and (best_score is None or score < best_score):
                        best_score = score
                        best_plan = plan

    # --- Strategy C: Single full-density marker ---
    ratio = _build_dense_ratio(sizes, order, max_pieces)
    if ratio and sum(ratio.values()) == max_pieces:
        plan_add, remaining = _tile_ratio(ratio, dict(order), [])
        if plan_add:
            plan = list(plan_add)
            cleanups = _add_cleanup_lays(remaining, plan)
            plan.extend(cleanups)

            if len(plan) <= max_lays:
                score = _evaluate_plan(plan)
                if score is not None and (best_score is None or score < best_score):
                    best_score = score
                    best_plan = plan

    return best_plan
