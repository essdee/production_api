"""
Proportional Decomposition Strategy

The operator's actual process:
1. MULTIPLES: Find ratio R₁ from order proportions (the "multiples" concept)
2. PLIES: Compute total plies for R₁, split across lays if > max_plies
3. CLEANUP: Find cleanup ratio(s) for the residual
4. FEEDBACK: Check total deviation. If overcut/undercut on some sizes,
   go BACK and adjust R₁'s ply count (or tweak R₁ by ±1 on a size)
   to compensate. If that can't fix it, try different cleanup ratios.
5. Iterate until within tolerance.

This is a feedback loop — the cleanup informs the main ratio.
The algorithm treats the whole plan as a system, not a forward-only decomposition.
"""

import math
import time
from typing import Dict, List, Optional, Tuple
from functools import reduce
from math import gcd
from itertools import combinations

from .common import _SolverTimeout


# ---------------------------------------------------------------------------
# Ratio generation
# ---------------------------------------------------------------------------

def _generate_proportional_ratios(order_vals, max_pieces):
    """Generate candidate ratios that approximate the order vector's proportion."""
    n = len(order_vals)
    total = sum(order_vals)
    if total == 0:
        return []

    candidates = set()

    # Scale proportionally to different target sums
    for target_sum in range(max_pieces, max(1, max_pieces // 3) - 1, -1):
        ideal = [order_vals[i] / total * target_sum for i in range(n)]
        floors = [int(math.floor(x)) for x in ideal]
        fracs = sorted(range(n), key=lambda i: ideal[i] - floors[i], reverse=True)
        ratio = list(floors)
        rem = target_sum - sum(ratio)
        for idx in fracs:
            if rem <= 0:
                break
            ratio[idx] += 1
            rem -= 1
        if sum(ratio) <= max_pieces and any(r > 0 for r in ratio):
            candidates.add(tuple(ratio))

    # GCD-based exact ratio
    nonzero = [x for x in order_vals if x > 0]
    if nonzero:
        g = reduce(gcd, nonzero)
        exact = tuple(x // g for x in order_vals)
        if sum(exact) <= max_pieces:
            candidates.add(exact)

    # Divide by various factors
    for divisor in range(2, max(order_vals) + 1):
        ratio = tuple(round(x / divisor) for x in order_vals)
        if 0 < sum(ratio) <= max_pieces:
            candidates.add(ratio)
        if sum(ratio) <= 1:
            break

    # ±1 variations
    base_list = list(candidates)[:12]
    for base in base_list:
        for i in range(n):
            for delta in [-1, 1]:
                variant = list(base)
                variant[i] = max(0, variant[i] + delta)
                if 0 < sum(variant) <= max_pieces:
                    candidates.add(tuple(variant))

    # Zero out small sizes
    for base in base_list[:5]:
        for num_zero in range(1, min(n - 1, 3)):
            indexed = sorted(range(n), key=lambda i: base[i])
            for combo in combinations(indexed[:num_zero + 1], num_zero):
                variant = list(base)
                for idx in combo:
                    variant[idx] = 0
                if 0 < sum(variant) <= max_pieces:
                    candidates.add(tuple(variant))

    return [c for c in candidates if any(v > 0 for v in c)]


def _generate_cleanup_ratios(residual, max_pieces):
    """Generate cleanup ratios targeting the residual vector."""
    n = len(residual)
    pos = [max(0, r) for r in residual]
    total_pos = sum(pos)
    if total_pos == 0:
        return []

    candidates = set()

    # Direct proportional to residual
    for target_sum in range(max_pieces, max(1, max_pieces // 4) - 1, -1):
        if total_pos == 0:
            break
        ideal = [pos[i] / total_pos * target_sum for i in range(n)]
        floors = [int(math.floor(x)) for x in ideal]
        fracs = sorted(range(n), key=lambda i: ideal[i] - floors[i], reverse=True)
        ratio = list(floors)
        rem = target_sum - sum(ratio)
        for idx in fracs:
            if rem <= 0:
                break
            ratio[idx] += 1
            rem -= 1
        if 0 < sum(ratio) <= max_pieces:
            candidates.add(tuple(ratio))

    # Exact residual / GCD
    nonzero_pos = [x for x in pos if x > 0]
    if nonzero_pos:
        g = reduce(gcd, nonzero_pos)
        exact = tuple(x // g for x in pos)
        if 0 < sum(exact) <= max_pieces:
            candidates.add(exact)

    # ±1 variations
    base_list = list(candidates)[:8]
    for base in base_list:
        for i in range(n):
            for delta in [-1, 1]:
                variant = list(base)
                variant[i] = max(0, variant[i] + delta)
                if 0 < sum(variant) <= max_pieces:
                    candidates.add(tuple(variant))

    # Focus ratios: only the sizes with positive residual
    active = [i for i in range(n) if pos[i] > 0]
    if len(active) < n:
        for base in base_list[:4]:
            variant = list(base)
            for i in range(n):
                if i not in active:
                    variant[i] = 0
            if 0 < sum(variant) <= max_pieces:
                candidates.add(tuple(variant))

    return [c for c in candidates if any(v > 0 for v in c)]


# ---------------------------------------------------------------------------
# Core: find best cleanup for a given main ratio + total plies
# ---------------------------------------------------------------------------

def _find_cleanup(residual, n, max_plies, max_pieces, tol_fracs, deadline, max_cleanup_lays=3):
    """
    Given a residual vector, find cleanup lays that bring it within tolerance.
    Minimizes number of cleanup lays first, then deviation.
    Returns (cleanup_plan, final_deviation) or (None, inf).
    cleanup_plan is list of (ratio_tuple, plies).
    """
    best_plan = None
    best_n_lays = float('inf')
    best_dev = float('inf')

    if all(abs(residual[i]) <= tol_fracs[i] for i in range(n)):
        return [], 0

    cleanup_ratios = _generate_cleanup_ratios(residual, max_pieces)

    for ratio in cleanup_ratios:
        if time.time() > deadline:
            break

        # Upper bound on plies
        upper = max_plies
        for i in range(n):
            if ratio[i] > 0:
                max_cut = residual[i] + tol_fracs[i]
                if max_cut <= 0:
                    upper = 0
                    break
                upper = min(upper, int(max_cut / ratio[i]))

        if upper <= 0:
            continue

        # Candidate ply counts
        ply_candidates = set()
        for i in range(n):
            if ratio[i] > 0 and residual[i] > 0:
                p = residual[i] // ratio[i]
                if 0 < p <= upper:
                    ply_candidates.add(p)
                p2 = math.ceil(residual[i] / ratio[i])
                if 0 < p2 <= upper:
                    ply_candidates.add(p2)
        ideals = [residual[i] / ratio[i] for i in range(n) if ratio[i] > 0 and residual[i] > 0]
        if ideals:
            avg = sum(ideals) / len(ideals)
            for delta in range(-3, 4):
                p = max(1, min(upper, round(avg + delta)))
                ply_candidates.add(p)
        ply_candidates.add(upper)

        for plies in ply_candidates:
            if plies <= 0 or plies > upper:
                continue
            new_res = [residual[i] - ratio[i] * plies for i in range(n)]

            if all(abs(new_res[i]) <= tol_fracs[i] for i in range(n)):
                dev = sum(abs(new_res[i]) for i in range(n))
                n_lays = 1
                if _is_better(n_lays, dev, best_n_lays, best_dev):
                    best_dev = dev
                    best_n_lays = n_lays
                    best_plan = [(ratio, plies)]
            elif max_cleanup_lays > 1 and 1 < best_n_lays:
                # Only recurse if we could beat current best lay count
                sub_plan, sub_dev = _find_cleanup(
                    new_res, n, max_plies, max_pieces, tol_fracs, deadline,
                    min(max_cleanup_lays - 1, best_n_lays - 2)  # prune deeper than needed
                )
                if sub_plan is not None:
                    final_res = list(new_res)
                    for sr, sp in sub_plan:
                        for i in range(n):
                            final_res[i] -= sr[i] * sp
                    total_dev = sum(abs(final_res[i]) for i in range(n))
                    n_lays = 1 + len(sub_plan)
                    if _is_better(n_lays, total_dev, best_n_lays, best_dev):
                        best_dev = total_dev
                        best_n_lays = n_lays
                        best_plan = [(ratio, plies)] + sub_plan

    return best_plan, best_dev


# ---------------------------------------------------------------------------
# Plan comparison: LAYS first, then deviation (operator cares about fewer lays)
# ---------------------------------------------------------------------------

def _is_better(new_lays, new_dev, old_lays, old_dev):
    """Compare two plans. Fewer lays wins. Same lays → lower deviation wins."""
    if new_lays < old_lays:
        return True
    if new_lays == old_lays and new_dev < old_dev:
        return True
    return False


# ---------------------------------------------------------------------------
# Main solver: multiples → cleanup → feedback adjustment
# ---------------------------------------------------------------------------

def _solve_with_feedback(order_vals, sizes, max_plies, max_pieces, tol_pct, max_lays, deadline):
    """
    Method:
    1. Pick main ratio R₁ from order multiples
    2. Pick total plies for R₁
    3. Find cleanup ratios for residual
    4. FEEDBACK: adjust R₁ plies (±1, ±2...) to reduce cleanup deviation
    5. Also try R₁ variants (±1 on each size position)
    6. Pick the plan with fewest lays and lowest deviation
    """
    n = len(order_vals)
    tol_fracs = [math.floor(order_vals[i] * tol_pct / 100) for i in range(n)]

    # Generate main ratio candidates from order proportions
    main_ratios = _generate_proportional_ratios(order_vals, max_pieces)

    # Score by proportional alignment — prefer ratios that mirror the order
    total_order = sum(order_vals)
    def alignment_score(ratio):
        rs = sum(ratio)
        if rs == 0 or total_order == 0:
            return 0
        return -sum(abs(ratio[i] / rs - order_vals[i] / total_order) for i in range(n))

    main_ratios.sort(key=alignment_score, reverse=True)
    # Take top candidates
    main_ratios = main_ratios[:20]

    best_plan = None
    best_total_lays = float('inf')
    best_total_dev = float('inf')

    for main_ratio in main_ratios:
        if time.time() > deadline:
            break

        # Compute ideal total plies for this ratio
        ideals = []
        for i in range(n):
            if main_ratio[i] > 0 and order_vals[i] > 0:
                ideals.append(order_vals[i] / main_ratio[i])

        if not ideals:
            continue

        avg_ideal = sum(ideals) / len(ideals)

        # Upper bound on total plies (don't exceed order + tolerance)
        max_total = int(avg_ideal * 1.5)
        for i in range(n):
            if main_ratio[i] > 0:
                limit = (order_vals[i] + tol_fracs[i]) / main_ratio[i]
                max_total = min(max_total, int(limit))

        if max_total <= 0:
            continue

        # Try a range of total plies around EACH size's ideal
        # This is the FEEDBACK: we don't lock the ply count,
        # we try multiple and see which gives the best cleanup.
        # Operator thinks: "how many plies until S runs out? Until M?"
        # So we explore ±5 around each size's ideal, not just the average.
        ply_range = set()

        # Plies near each size's ideal (order[i] / ratio[i])
        for i in range(n):
            if main_ratio[i] > 0 and order_vals[i] > 0:
                size_ideal = order_vals[i] / main_ratio[i]
                for delta in range(-5, 6):
                    p = max(1, round(size_ideal + delta))
                    if 0 < p <= max_total:
                        ply_range.add(p)

        # Also around the average
        base_ply = max(1, round(avg_ideal))
        for delta in range(-5, 6):
            p = base_ply + delta
            if 0 < p <= max_total:
                ply_range.add(p)

        for total_plies in sorted(ply_range):
            if time.time() > deadline:
                break

            # How many lays for the main ratio?
            main_lays = math.ceil(total_plies / max_plies)
            if main_lays >= best_total_lays:
                continue
            max_cleanup = max_lays - main_lays
            if max_cleanup < 0:
                continue

            # Residual after main ratio
            residual = [order_vals[i] - main_ratio[i] * total_plies for i in range(n)]

            # Is residual already within tolerance?
            if all(abs(residual[i]) <= tol_fracs[i] for i in range(n)):
                dev = sum(abs(residual[i]) for i in range(n))
                total_lays_here = main_lays
                if _is_better(total_lays_here, dev, best_total_lays, best_total_dev):
                    # Build the plan
                    plan = []
                    plies_left = total_plies
                    ratio_dict = {sizes[i]: main_ratio[i] for i in range(n)}
                    # Smart split
                    splits = _smart_split(total_plies, max_plies, main_ratio, order_vals, n)
                    for sp in splits:
                        plan.append((dict(ratio_dict), sp))
                    best_plan = plan
                    best_total_lays = total_lays_here
                    best_total_dev = dev
                continue

            # Find cleanup
            if max_cleanup <= 0:
                continue

            cleanup, cleanup_dev = _find_cleanup(
                residual, n, max_plies, max_pieces, tol_fracs, deadline,
                min(max_cleanup, 3)
            )

            if cleanup is None:
                continue

            total_lays_here = main_lays + len(cleanup)
            if not _is_better(total_lays_here, cleanup_dev, best_total_lays, best_total_dev):
                continue

            # Build full plan
            plan = []
            ratio_dict = {sizes[i]: main_ratio[i] for i in range(n)}
            splits = _smart_split(total_plies, max_plies, main_ratio, order_vals, n)
            for sp in splits:
                plan.append((dict(ratio_dict), sp))
            for cr, cp in cleanup:
                cr_dict = {sizes[i]: cr[i] for i in range(n)}
                plan.append((cr_dict, cp))

            best_plan = plan
            best_total_lays = total_lays_here
            best_total_dev = cleanup_dev

    # --- PHASE 2: Try adjusting the best plan's main ratio by ±1 on each size ---
    if best_plan and len(best_plan) >= 2 and time.time() < deadline:
        # Extract the main ratio from best plan
        first_ratio = best_plan[0][0]
        main_r = tuple(first_ratio[sizes[i]] for i in range(n))
        # Count main lays (same ratio)
        main_lay_count = 0
        main_total_plies = 0
        for rd, pl in best_plan:
            r_tuple = tuple(rd[sizes[i]] for i in range(n))
            if r_tuple == main_r:
                main_lay_count += 1
                main_total_plies += pl
            else:
                break

        # Try ±1 adjustments on each size
        for i in range(n):
            for delta in [-1, 1]:
                if time.time() > deadline:
                    break
                adjusted = list(main_r)
                adjusted[i] = max(0, adjusted[i] + delta)
                if sum(adjusted) == 0 or sum(adjusted) > max_pieces:
                    continue
                adj_tuple = tuple(adjusted)

                # Recompute plies range for adjusted ratio — near each size's ideal
                adj_ideals = [order_vals[j] / adj_tuple[j] for j in range(n) if adj_tuple[j] > 0 and order_vals[j] > 0]
                if not adj_ideals:
                    continue

                adj_ply_candidates = set()
                for j in range(n):
                    if adj_tuple[j] > 0 and order_vals[j] > 0:
                        si = order_vals[j] / adj_tuple[j]
                        for d2 in range(-3, 4):
                            adj_ply_candidates.add(max(1, round(si + d2)))
                adj_avg = sum(adj_ideals) / len(adj_ideals)
                for d2 in range(-3, 4):
                    adj_ply_candidates.add(max(1, round(adj_avg + d2)))

                for tp in adj_ply_candidates:
                    tp = tp  # already computed
                    # Cap
                    for j in range(n):
                        if adj_tuple[j] > 0:
                            limit = (order_vals[j] + tol_fracs[j]) / adj_tuple[j]
                            tp = min(tp, int(limit))
                    if tp <= 0:
                        continue

                    adj_main_lays = math.ceil(tp / max_plies)
                    if adj_main_lays >= best_total_lays:
                        continue

                    residual = [order_vals[j] - adj_tuple[j] * tp for j in range(n)]
                    if all(abs(residual[j]) <= tol_fracs[j] for j in range(n)):
                        dev = sum(abs(residual[j]) for j in range(n))
                        if _is_better(adj_main_lays, dev, best_total_lays, best_total_dev):
                            plan = []
                            ratio_dict = {sizes[j]: adj_tuple[j] for j in range(n)}
                            splits = _smart_split(tp, max_plies, adj_tuple, order_vals, n)
                            for sp in splits:
                                plan.append((dict(ratio_dict), sp))
                            best_plan = plan
                            best_total_lays = adj_main_lays
                            best_total_dev = dev
                        continue

                    max_cleanup = max_lays - adj_main_lays
                    if max_cleanup <= 0:
                        continue

                    cleanup, cleanup_dev = _find_cleanup(
                        residual, n, max_plies, max_pieces, tol_fracs, deadline,
                        min(max_cleanup, 2)
                    )
                    if cleanup is None:
                        continue

                    total_here = adj_main_lays + len(cleanup)
                    if _is_better(total_here, cleanup_dev, best_total_lays, best_total_dev):
                        plan = []
                        ratio_dict = {sizes[j]: adj_tuple[j] for j in range(n)}
                        splits = _smart_split(tp, max_plies, adj_tuple, order_vals, n)
                        for sp in splits:
                            plan.append((dict(ratio_dict), sp))
                        for cr, cp in cleanup:
                            cr_dict = {sizes[j]: cr[j] for j in range(n)}
                            plan.append((cr_dict, cp))
                        best_plan = plan
                        best_total_lays = total_here
                        best_total_dev = cleanup_dev

    return best_plan


def _smart_split(total_plies, max_plies, ratio, order_vals, n):
    """
    Split total_plies into individual lays of ≤ max_plies.
    Try to find splits where one lay hits an exact size count.
    Falls back to even split.
    """
    if total_plies <= max_plies:
        return [total_plies]

    num_splits = math.ceil(total_plies / max_plies)

    # Even split as baseline
    base = total_plies // num_splits
    best_split = [base] * num_splits
    remainder = total_plies - sum(best_split)
    for j in range(remainder):
        best_split[j] += 1

    best_dev = float('inf')

    # Try splits targeting exact size quantities
    for i in range(n):
        if ratio[i] > 0 and order_vals[i] > 0:
            target_ply = order_vals[i] // ratio[i]
            if 0 < target_ply <= max_plies:
                other_p = total_plies - target_ply
                if other_p > 0:
                    splits_try = [target_ply]
                    o_left = other_p
                    while o_left > 0:
                        sp = min(o_left, max_plies)
                        splits_try.append(sp)
                        o_left -= sp
                    if all(0 < s <= max_plies for s in splits_try) and len(splits_try) == num_splits:
                        # Score: how many sizes are exactly hit
                        exact_hits = 0
                        for ii in range(n):
                            if ratio[ii] > 0:
                                for s in splits_try:
                                    if ratio[ii] * s == order_vals[ii]:
                                        exact_hits += 1
                                        break
                        dev = -exact_hits  # more exact hits = better
                        if dev < best_dev:
                            best_dev = dev
                            best_split = splits_try

    return best_split


# ---------------------------------------------------------------------------
# Public API
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
    Proportional Decomposition strategy.

    1. Find main ratio from order multiples
    2. Find cleanup ratios for residual
    3. FEEDBACK: adjust main ratio plies/shape to minimize cleanup deviation
    4. Pick plan with fewest lays + lowest deviation

    Returns list of (ratio_dict, plies) or None.
    """
    sizes = list(order.keys())
    order_vals = [order[s] for s in sizes]

    deadline = time.time() + 18.0

    try:
        plan = _solve_with_feedback(order_vals, sizes, max_plies, max_pieces, tolerance_pct, max_lays, deadline)
    except _SolverTimeout:
        plan = None

    if plan is None:
        return None

    # Tubular: force even plies
    if tubular:
        adjusted = []
        for ratio_dict, plies in plan:
            if plies % 2 != 0:
                plies = plies + 1 if plies + 1 <= max_plies else max(plies - 1, 2)
            adjusted.append((ratio_dict, plies))
        plan = adjusted

    # Final tolerance check
    totals = {s: 0 for s in sizes}
    for ratio_dict, plies in plan:
        for s in sizes:
            totals[s] += ratio_dict.get(s, 0) * plies

    for s in sizes:
        if order[s] > 0:
            if abs(totals[s] - order[s]) / order[s] > tolerance_pct / 100:
                return None

    return plan
