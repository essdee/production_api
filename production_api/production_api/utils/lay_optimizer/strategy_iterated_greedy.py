"""
Iterated Greedy Strategy (HFSC — Heuristic for the Full-Size Cutting problem)
=============================================================================

Based on: Meng et al. (2019), "An iterated greedy approach for solving the
cutting order planning problem in apparel manufacturing."

CONCEPT
-------
Two-phase approach:
  Phase 1 — CONSTRUCTION: Build an initial lay plan greedily (best ratio at
            best ply count, one lay at a time).
  Phase 2 — IMPROVEMENT: Iteratively destroy and repair the plan:
            - Remove one lay (the worst-scoring)
            - Redistribute its order across remaining lays by adjusting
              their ratios and/or ply counts
            - If no improvement: try removing a different lay
            - Repeat until no improvement found in a full sweep

The improving loop is what distinguishes this from greedy_subtraction.
Greedy builds once and stops. Iterated greedy post-optimizes by
reconsidering each lay's contribution.

SCORING
-------
Plans are scored by: (number_of_lays, total_overcut, total_deviation)
Lower is better on all three. Lexicographic comparison: fewer lays wins first,
then less overcut, then less total deviation.

COMPLEXITY
----------
Construction: O(max_lays × max_plies × n_sizes)
Improvement:  O(max_iterations × n_lays² × max_plies × n_sizes)
Typical: <1s for orders up to 20K pieces.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from .common import (
    check_tolerance,
    total_deviation,
    plan_cut_totals,
    within_tolerance_totals,
)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score(plan, order, sizes, tol):
    """
    Score a plan. Returns (valid, n_lays, overcut, total_dev) tuple.
    Lower is better on all fields. Invalid plans get (False, inf, inf, inf).
    """
    if not plan:
        return (False, float("inf"), float("inf"), float("inf"))

    totals = plan_cut_totals(plan, sizes)

    for s in sizes:
        if order[s] > 0:
            if abs(totals[s] - order[s]) / order[s] > tol:
                return (False, float("inf"), float("inf"), float("inf"))

    overcut = sum(max(0, totals[s] - order[s]) for s in sizes)
    dev = sum(abs(totals[s] - order[s]) for s in sizes)
    return (True, len(plan), overcut, dev)


def _score_lt(a, b):
    """True if score a is strictly better than score b."""
    if a[0] and not b[0]:
        return True
    if not a[0]:
        return False
    # Both valid: compare (n_lays, overcut, deviation)
    return (a[1], a[2], a[3]) < (b[1], b[2], b[3])


# ---------------------------------------------------------------------------
# Ratio builder: find best ratio for given remaining order at given plies
# ---------------------------------------------------------------------------

def _best_ratio_for_plies(
    remaining: Dict[str, int],
    sizes: List[str],
    plies: int,
    max_pieces: int,
    tol: float = 0.03,
) -> Optional[Dict[str, int]]:
    """
    Build the best proportional ratio for remaining order at given plies.
    Uses ceil-then-trim approach: ceil all, then trim to fit max_pieces.
    Skips sizes where the ratio would overcut beyond tolerance.
    """
    if plies <= 0:
        return None

    # Ceil ratio — but skip sizes where overcut would be excessive
    ratio = {}
    for s in sizes:
        rem = remaining.get(s, 0)
        if rem <= 0:
            ratio[s] = 0
        else:
            r = math.ceil(rem / plies)
            # Check overcut: r * plies vs remaining
            if r * plies > rem * (1 + tol) and r > 0:
                # Try floor instead
                rf = rem // plies
                if rf > 0 and rf * plies >= rem * (1 - tol):
                    ratio[s] = rf
                elif r * plies <= rem * (1 + tol * 3):
                    # Allow moderate overcut if within 3x tolerance
                    ratio[s] = r
                else:
                    ratio[s] = 0  # Skip — too much overcut
            else:
                ratio[s] = r

    # Trim to fit max_pieces
    while sum(ratio.values()) > max_pieces:
        trimmable = [(remaining.get(s, 0), s) for s in sizes if ratio[s] > 0]
        if not trimmable:
            return None
        trimmable.sort()
        _, trim_s = trimmable[0]
        ratio[trim_s] = max(0, ratio[trim_s] - 1)

    if sum(ratio.values()) == 0:
        return None

    return ratio


def _best_ratio_floor(
    remaining: Dict[str, int],
    sizes: List[str],
    plies: int,
    max_pieces: int,
    tol: float = 0.03,
) -> Optional[Dict[str, int]]:
    """Floor ratio with bump-up for sizes with biggest deficit."""
    if plies <= 0:
        return None

    ratio = {}
    for s in sizes:
        rem = remaining.get(s, 0)
        if rem > 0:
            r = rem // plies
            # Don't include sizes where even floor=1 would overcut badly
            if r == 0 and plies > rem * (1 + tol * 3):
                ratio[s] = 0
            else:
                ratio[s] = r
        else:
            ratio[s] = 0

    # Trim if exceeds max_pieces
    while sum(ratio.values()) > max_pieces:
        trimmable = [(remaining.get(s, 0), s) for s in sizes if ratio[s] > 0]
        if not trimmable:
            return None
        trimmable.sort()
        _, trim_s = trimmable[0]
        ratio[trim_s] = max(0, ratio[trim_s] - 1)

    # Bump sizes where floor leaves biggest gap (only if bump won't overcut badly)
    budget = max_pieces - sum(ratio.values())
    if budget > 0:
        gaps = []
        for s in sizes:
            rem = remaining.get(s, 0)
            if rem > 0:
                gap = rem - ratio[s] * plies
                if gap > 0:
                    new_val = ratio[s] + 1
                    overcut_pct = (new_val * plies - rem) / rem if rem > 0 else 999
                    # Only bump if overcut stays within tolerance
                    if overcut_pct <= tol:
                        gaps.append((gap, s))
        gaps.sort(reverse=True)
        for gap, s in gaps:
            if budget <= 0:
                break
            ratio[s] += 1
            budget -= 1

    if sum(ratio.values()) == 0 or sum(ratio.values()) > max_pieces:
        return None

    return ratio


# ---------------------------------------------------------------------------
# Phase 1: CONSTRUCTION — greedy lay-by-lay
# ---------------------------------------------------------------------------

def _construct(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Build initial plan greedily:
    At each step, find the (ratio, plies) that covers the most remaining pieces.
    """
    remaining = dict(order)
    plan = []

    for _ in range(max_lays):
        total_rem = sum(max(0, remaining[s]) for s in sizes)
        if total_rem == 0:
            break

        best_lay = None
        best_coverage = -1

        # Try a range of ply counts
        # Key insight: try plies that are natural divisors of remaining quantities
        ply_candidates = set()
        for s in sizes:
            r = remaining.get(s, 0)
            if r <= 0:
                continue
            # Divisor-based candidates
            for d in range(1, min(max_pieces + 1, r + 1)):
                p = r // d
                if 0 < p <= max_plies:
                    ply_candidates.add(p)
                pc = math.ceil(r / d) if d > 0 else 0
                if 0 < pc <= max_plies:
                    ply_candidates.add(pc)

        # Also add max_plies and nearby
        for p in [max_plies, max_plies - 1, max_plies - 2, max_plies // 2]:
            if 0 < p <= max_plies:
                ply_candidates.add(p)

        # Small values
        for p in range(1, min(21, max_plies + 1)):
            ply_candidates.add(p)

        if tubular:
            ply_candidates = {p for p in ply_candidates if p % 2 == 0}

        for plies in sorted(ply_candidates, reverse=True):
            for ratio_fn in [_best_ratio_for_plies, _best_ratio_floor]:
                ratio = ratio_fn(remaining, sizes, plies, max_pieces)
                if ratio is None:
                    continue

                # Score: pieces covered (min of cut vs remaining, no negative credit)
                coverage = sum(
                    min(ratio[s] * plies, max(0, remaining[s]))
                    for s in sizes
                )
                # Slight penalty for overcut
                overcut = sum(
                    max(0, ratio[s] * plies - max(0, remaining[s]))
                    for s in sizes
                )
                score = coverage - overcut * 0.5

                if score > best_coverage:
                    best_coverage = score
                    best_lay = (ratio, plies)

            # Early exit if we found a lay covering >90% of remaining
            if best_lay and best_coverage > total_rem * 0.9:
                break

        if best_lay is None:
            break

        ratio, plies = best_lay
        plan.append((ratio, plies))
        for s in sizes:
            remaining[s] -= ratio[s] * plies

    return plan


# ---------------------------------------------------------------------------
# Phase 2: IMPROVEMENT — iterative destroy-and-repair
# ---------------------------------------------------------------------------

def _remove_and_repair(
    plan: List[Tuple[Dict[str, int], int]],
    remove_idx: int,
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Remove lay at remove_idx. Redistribute its pieces across remaining lays
    by rebuilding from the reduced plan's coverage gap.
    
    Strategy:
    1. Remove the target lay
    2. Compute what's still needed
    3. Try to absorb into existing lays by increasing their plies
    4. If not enough: add new cleanup lays via construction
    """
    n = len(plan)
    if n <= 1:
        return None  # Can't remove the only lay

    # Build plan without the removed lay
    reduced = [plan[i] for i in range(n) if i != remove_idx]

    # What's covered by reduced plan?
    covered = {s: 0 for s in sizes}
    for ratio, plies in reduced:
        for s in sizes:
            covered[s] += ratio.get(s, 0) * plies

    # What still needs to be covered?
    gap = {s: order[s] - covered[s] for s in sizes}
    total_gap = sum(max(0, gap[s]) for s in sizes)

    if total_gap == 0:
        # Reduced plan already sufficient — check tolerance
        if check_tolerance(reduced, order, sizes, tol):
            return reduced
        return None

    # Strategy A: Try increasing plies on existing lays to absorb gap
    for i in range(len(reduced)):
        ratio_i, plies_i = reduced[i]
        if plies_i >= max_plies:
            continue

        # How many extra plies would this lay need?
        extra_needed = 0
        for s in sizes:
            if ratio_i.get(s, 0) > 0 and gap[s] > 0:
                extra = math.ceil(gap[s] / ratio_i[s])
                extra_needed = max(extra_needed, extra)

        new_plies = min(max_plies, plies_i + extra_needed)
        if tubular and new_plies % 2 != 0:
            new_plies = min(max_plies, new_plies + 1)
            if new_plies % 2 != 0:
                new_plies -= 1

        if new_plies <= plies_i:
            continue

        candidate = list(reduced)
        candidate[i] = (ratio_i, new_plies)

        if check_tolerance(candidate, order, sizes, tol):
            return candidate

    # Strategy B: Construct new cleanup lays for the gap
    remaining_budget = max_lays - len(reduced)
    if remaining_budget <= 0:
        return None

    gap_positive = {s: max(0, gap[s]) for s in sizes}
    cleanup = _construct(
        gap_positive, sizes, max_plies, max_pieces, tol,
        remaining_budget, tubular,
    )

    if cleanup:
        candidate = reduced + cleanup
        if len(candidate) <= max_lays and check_tolerance(candidate, order, sizes, tol):
            return candidate

    # Strategy C: Rebuild entire residual greedily (fresh construction)
    candidate = reduced + _construct(
        gap_positive, sizes, max_plies, max_pieces, tol * 1.5,
        remaining_budget, tubular,
    )
    if len(candidate) <= max_lays and check_tolerance(candidate, order, sizes, tol):
        return candidate

    return None


def _improve(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    max_lays: int,
    tubular: bool,
    max_iterations: int = 20,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Iterated improvement loop:
    - Try removing each lay in turn
    - If any removal produces a better plan: accept it
    - Repeat until no improvement found
    """
    current = list(plan)
    current_score = _score(current, order, sizes, tol)

    for iteration in range(max_iterations):
        improved = False

        # Try removing each lay (worst-scoring first = highest overcut contribution)
        lay_scores = []
        for i in range(len(current)):
            ratio, plies = current[i]
            overcut_i = sum(
                max(0, ratio.get(s, 0) * plies - order[s])
                for s in sizes
            )
            lay_scores.append((overcut_i, i))
        lay_scores.sort(reverse=True)  # Try removing worst first

        for _, remove_idx in lay_scores:
            repaired = _remove_and_repair(
                current, remove_idx, order, sizes,
                max_plies, max_pieces, tol, max_lays, tubular,
            )
            if repaired is None:
                continue

            new_score = _score(repaired, order, sizes, tol)
            if _score_lt(new_score, current_score):
                current = repaired
                current_score = new_score
                improved = True
                break  # Restart sweep

        if not improved:
            break

        # Also try swapping ratios between lays
        for i in range(len(current)):
            for j in range(i + 1, len(current)):
                ri, pi = current[i]
                rj, pj = current[j]
                # Try swapping plies
                candidate = list(current)
                candidate[i] = (ri, pj)
                candidate[j] = (rj, pi)
                new_score = _score(candidate, order, sizes, tol)
                if _score_lt(new_score, current_score):
                    current = candidate
                    current_score = new_score

    return current


# ---------------------------------------------------------------------------
# Ratio perturbation: try adjusting ratios in each lay
# ---------------------------------------------------------------------------

def _perturb_ratios(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    max_pieces: int,
    tol: float,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Fine-tune ratios in each lay: try ±1 on each size, keep if score improves.
    """
    current = list(plan)
    current_score = _score(current, order, sizes, tol)

    for lay_idx in range(len(current)):
        ratio, plies = current[lay_idx]

        for s in sizes:
            # Try +1
            if sum(ratio.values()) < max_pieces:
                new_ratio = dict(ratio)
                new_ratio[s] = ratio.get(s, 0) + 1
                candidate = list(current)
                candidate[lay_idx] = (new_ratio, plies)
                new_score = _score(candidate, order, sizes, tol)
                if _score_lt(new_score, current_score):
                    current = candidate
                    current_score = new_score
                    ratio = new_ratio

            # Try -1
            if ratio.get(s, 0) > 0:
                new_ratio = dict(ratio)
                new_ratio[s] -= 1
                candidate = list(current)
                candidate[lay_idx] = (new_ratio, plies)
                new_score = _score(candidate, order, sizes, tol)
                if _score_lt(new_score, current_score):
                    current = candidate
                    current_score = new_score
                    ratio = new_ratio

    return current


# ---------------------------------------------------------------------------
# Ply perturbation: try adjusting ply counts
# ---------------------------------------------------------------------------

def _perturb_plies(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    tol: float,
    tubular: bool,
) -> List[Tuple[Dict[str, int], int]]:
    """
    Fine-tune plies: try ±1, ±2 on each lay.
    """
    current = list(plan)
    current_score = _score(current, order, sizes, tol)
    step = 2 if tubular else 1

    for lay_idx in range(len(current)):
        ratio, plies = current[lay_idx]

        for delta in [step, -step, 2 * step, -2 * step]:
            new_plies = plies + delta
            if new_plies <= 0 or new_plies > max_plies:
                continue
            if tubular and new_plies % 2 != 0:
                continue
            candidate = list(current)
            candidate[lay_idx] = (ratio, new_plies)
            new_score = _score(candidate, order, sizes, tol)
            if _score_lt(new_score, current_score):
                current = candidate
                current_score = new_score

    return current


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
    Iterated Greedy strategy (HFSC).

    Two phases:
    1. CONSTRUCTION: Greedy lay-by-lay planning
    2. IMPROVEMENT: Iterative destroy-and-repair + perturbation

    Returns list of (ratio_dict, plies) tuples or None.
    """
    sizes = list(order.keys())
    tol = tolerance_pct / 100.0

    eff_plies = max_plies
    if tubular and eff_plies % 2 != 0:
        eff_plies -= 1

    # Phase 1: Construction — try multiple starting points
    plans = []

    # Standard construction
    p1 = _construct(order, sizes, eff_plies, max_pieces, tol, max_lays, tubular)
    if p1 and check_tolerance(p1, order, sizes, tol):
        plans.append(p1)

    # Looser tolerance construction
    p2 = _construct(order, sizes, eff_plies, max_pieces, tol * 2, max_lays, tubular)
    if p2 and check_tolerance(p2, order, sizes, tol):
        plans.append(p2)

    # Direct max-plies-first construction: force first lay at max_plies
    # This mirrors the LP approach — one big lay + cleanup
    first_ratio_ceil = _best_ratio_for_plies(order, sizes, eff_plies, max_pieces, tol * 2)
    first_ratio_floor = _best_ratio_floor(order, sizes, eff_plies, max_pieces, tol * 2)
    for first_ratio in [first_ratio_ceil, first_ratio_floor]:
        if first_ratio and sum(first_ratio.values()) > 0:
            remaining = {s: order[s] - first_ratio[s] * eff_plies for s in sizes}
            rem_pos = {s: max(0, remaining[s]) for s in sizes}
            if sum(rem_pos.values()) > 0:
                cleanup = _construct(rem_pos, sizes, eff_plies, max_pieces, tol * 2,
                                     max_lays - 1, tubular)
                if cleanup:
                    candidate = [(first_ratio, eff_plies)] + cleanup
                    if check_tolerance(candidate, order, sizes, tol):
                        plans.append(candidate)

    if not plans:
        return None

    # Pick best starting plan
    best_score = None
    plan = None
    for p in plans:
        s = _score(p, order, sizes, tol)
        if s[0] and (best_score is None or _score_lt(s, best_score)):
            best_score = s
            plan = p

    if plan is None:
        plan = plans[0]

    # Phase 2: Improvement loop
    plan = _improve(
        plan, order, sizes, eff_plies, max_pieces, tol, max_lays, tubular,
        max_iterations=20,
    )

    # Phase 2b: Fine-tune ratios
    plan = _perturb_ratios(plan, order, sizes, max_pieces, tol)

    # Phase 2c: Fine-tune plies
    plan = _perturb_plies(plan, order, sizes, eff_plies, tol, tubular)

    # Final validation
    if not check_tolerance(plan, order, sizes, tol):
        return None

    return plan
