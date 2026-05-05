"""
Single Ratio Strategy
======================

Find a plan where ALL lays use the SAME marker ratio (different ply counts).
Simplest for production: one marker to nest, use it for every lay.

For a fixed ratio R, total_cut[s] = R[s] × total_plies.
The ratio must be proportional to the order.
If the order is very skewed (e.g., 144 vs 996), the smallest size constrains badly.
"""

import math
from itertools import product as iter_product
from typing import Dict, List, Optional, Tuple


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """Single ratio strategy — one marker ratio for all lays."""
    sizes = list(order.keys())
    n = len(sizes)
    total_order = sum(order.values())

    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    best_plan = None
    best_score = float("inf")

    def _evaluate_ratio(ratio):
        """Given a fixed ratio, find the best total_plies and lay distribution."""
        pcs_per_ply = sum(ratio.values())
        if pcs_per_ply == 0:
            return None, float("inf")

        ideal_per_size = []
        for s in sizes:
            if ratio[s] > 0:
                ideal_per_size.append(order[s] / ratio[s])

        if not ideal_per_size:
            return None, float("inf")

        median_p = sorted(ideal_per_size)[len(ideal_per_size) // 2]
        lo = max(1, int(median_p * 0.85))
        hi = min(max_plies * max_lays, int(median_p * 1.15) + 1)

        step = 2 if tubular else 1
        if tubular and lo % 2 != 0:
            lo += 1

        best_local = None
        best_local_score = float("inf")

        for total_plies in range(lo, hi + 1, step):
            ok = True
            total_dev = 0
            for s in sizes:
                cut = ratio[s] * total_plies
                dev = abs(cut - order[s])
                pct = dev / order[s] * 100 if order[s] > 0 else 0
                if pct > tolerance_pct:
                    ok = False
                    break
                total_dev += dev

            if not ok:
                continue

            lays_plies = []
            remaining = total_plies
            for _ in range(max_lays):
                p = min(max_plies, remaining)
                if tubular and p % 2 != 0:
                    p -= 1
                if p > 0:
                    lays_plies.append(p)
                remaining -= p
                if remaining <= 0:
                    break
            if remaining > 0:
                continue

            num_lays = len(lays_plies)
            score = num_lays * 1000 + total_dev
            if score < best_local_score:
                best_local_score = score
                best_local = [(dict(ratio), p) for p in lays_plies]

        return best_local, best_local_score

    # Method 1: Proportional ratios at different scales
    for total_ratio_target in range(max(1, max_pieces // 6), max_pieces + 1):
        ratio = {}
        remaining_ratio = total_ratio_target
        sorted_sizes = sorted(sizes, key=lambda s: order[s], reverse=True)

        for i, s in enumerate(sorted_sizes):
            if i == len(sorted_sizes) - 1:
                ratio[s] = remaining_ratio
            else:
                ideal = order[s] / total_order * total_ratio_target
                r = max(0, min(remaining_ratio, round(ideal)))
                ratio[s] = r
                remaining_ratio -= r

        if sum(ratio.values()) == 0 or sum(ratio.values()) > max_pieces:
            continue

        plan, score = _evaluate_ratio(ratio)
        if plan and score < best_score:
            best_score = score
            best_plan = plan

    # Method 2: Floor/ceil variations of the proportional ratio
    for total_ratio_target in range(max(n, max_pieces // 3), max_pieces + 1):
        base_ratios = {}
        for s in sizes:
            base_ratios[s] = order[s] / total_order * total_ratio_target

        choices = []
        for s in sizes:
            f = max(0, math.floor(base_ratios[s]))
            c = math.ceil(base_ratios[s])
            choices.append([f, c] if f != c else [f])

        if len(sizes) > 10:
            continue

        for combo in iter_product(*choices):
            ratio = {sizes[i]: combo[i] for i in range(len(sizes))}
            if sum(ratio.values()) == 0 or sum(ratio.values()) > max_pieces:
                continue

            plan, score = _evaluate_ratio(ratio)
            if plan and score < best_score:
                best_score = score
                best_plan = plan

    return best_plan
