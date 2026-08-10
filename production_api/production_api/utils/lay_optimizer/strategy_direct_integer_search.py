"""Deterministic direct integer search for cutting lay plans.

This module deliberately does not depend on SciPy, OR-Tools, or another solver.
It searches bounded, ordered ply-count tuples and solves the marker-ratio
assignment for each tuple with multidimensional integer dynamic programming.

Priority is lexicographic:
1. minimum physical lays;
2. minimum weighted deviation (undercut costs twice overcut);
3. minimum absolute deviation;
4. minimum undercut, then overcut.
"""

from __future__ import annotations

import math
import time
from itertools import combinations_with_replacement, product
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Plan = List[Tuple[Dict[str, int], int]]

UNDERCUT_WEIGHT = 2
OVERCUT_WEIGHT = 1
MAX_DIRECT_LAYS = 4
MAX_PLY_CANDIDATES = {1: 140, 2: 70, 3: 40, 4: 20}
MAX_TUPLES = {1: 140, 2: 3000, 3: 12000, 4: 3500}
SEARCH_SECONDS = 18.0


def _integer_bounds(quantity: int, tolerance_pct: float) -> Tuple[int, int]:
    tolerance = tolerance_pct / 100.0
    return (
        math.ceil(quantity * (1.0 - tolerance)),
        math.floor(quantity * (1.0 + tolerance)),
    )


def _normalize_ply(value: int, max_plies: int, tubular: bool) -> Optional[int]:
    if tubular:
        value -= value % 2
        minimum = 2
    else:
        minimum = 1
    if value < minimum or value > max_plies:
        return None
    return value


def _candidate_plies(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float,
    tubular: bool,
    lay_count: int,
) -> List[int]:
    """Build a deterministic, demand-derived pool of useful ply counts."""
    step = 2 if tubular else 1
    minimum = step
    effective_max = _normalize_ply(max_plies, max_plies, tubular)
    if effective_max is None:
        return []
    candidates = set(range(minimum, max_plies + 1, step))

    # Rank every legal ply count by how many size/ratio combinations it can
    # represent closely. Demand-derived floor/ceil counts receive extra weight.
    support = {p: 0 for p in candidates}
    derived = set()
    for quantity in order.values():
        for ratio in range(1, max_pieces + 1):
            raw_values = (quantity // ratio, math.ceil(quantity / ratio))
            for raw in raw_values:
                for delta in (-step, 0, step):
                    normalized = _normalize_ply(raw + delta, max_plies, tubular)
                    if normalized is not None:
                        derived.add(normalized)
            for p in candidates:
                deviation = abs(p * ratio - quantity)
                if deviation <= max(1, math.floor(quantity * tolerance_pct / 100.0)):
                    support[p] += 1

    for p in derived:
        support[p] += 4
    support[effective_max] += 8

    limit = MAX_PLY_CANDIDATES.get(lay_count, 20)
    ranked = sorted(candidates, key=lambda p: (-support[p], -p))
    selected = set(ranked[:limit])
    selected.add(effective_max)
    return sorted(selected, reverse=True)


def _ply_tuples(
    candidates: Sequence[int],
    lay_count: int,
    minimum_total_cut: int,
    max_pieces: int,
) -> Iterable[Tuple[int, ...]]:
    """Yield ordered tuples, prioritizing plausible total ply capacity."""
    raw = []
    for ascending in combinations_with_replacement(sorted(candidates), lay_count):
        plies = tuple(reversed(ascending))
        capacity = sum(plies) * max_pieces
        if capacity < minimum_total_cut:
            continue
        # Full markers would need approximately this many total plies.
        excess_capacity = capacity - minimum_total_cut
        raw.append((excess_capacity, -sum(plies), plies))
    raw.sort()
    for _, _, plies in raw[: MAX_TUPLES.get(lay_count, 2000)]:
        yield plies


def _ratio_options(
    plies: Sequence[int],
    lower: int,
    upper: int,
    quantity: int,
    max_pieces: int,
) -> List[Tuple[Tuple[int, ...], Tuple[int, int, int, int]]]:
    """Enumerate feasible ratios for one size, deriving the last ratio bound."""
    options = []
    prefix_count = len(plies) - 1
    prefix_ranges = [range(max_pieces + 1)] * prefix_count

    for prefix in product(*prefix_ranges):
        prefix_cut = sum(ratio * ply for ratio, ply in zip(prefix, plies))
        final_ply = plies[-1]
        min_final = max(0, math.ceil((lower - prefix_cut) / final_ply))
        max_final = min(max_pieces, math.floor((upper - prefix_cut) / final_ply))
        if min_final > max_final:
            continue
        for final_ratio in range(min_final, max_final + 1):
            ratios = tuple(prefix) + (final_ratio,)
            cut = prefix_cut + final_ratio * final_ply
            diff = cut - quantity
            undercut = max(0, -diff)
            overcut = max(0, diff)
            score = (
                UNDERCUT_WEIGHT * undercut + OVERCUT_WEIGHT * overcut,
                abs(diff),
                undercut,
                overcut,
            )
            options.append((ratios, score))

    options.sort(key=lambda item: (item[1], item[0]))
    return options


def _add_score(left: Tuple[int, ...], right: Tuple[int, ...]) -> Tuple[int, ...]:
    return tuple(a + b for a, b in zip(left, right))


def _solve_ratios(
    plies: Sequence[int],
    order: Dict[str, int],
    sizes: Sequence[str],
    max_pieces: int,
    tolerance_pct: float,
) -> Optional[Tuple[Tuple[int, int, int, int], Plan]]:
    """Assign all size ratios using capacity-state dynamic programming."""
    option_sets = []
    for size in sizes:
        lower, upper = _integer_bounds(order[size], tolerance_pct)
        options = _ratio_options(plies, lower, upper, order[size], max_pieces)
        if not options:
            return None
        option_sets.append(options)

    # state -> (score, chosen ratio tuple per processed size)
    origin = (0,) * len(plies)
    states = {origin: ((0, 0, 0, 0), ())}

    for options in option_sets:
        next_states = {}
        for used, (base_score, path) in states.items():
            for ratios, option_score in options:
                new_used = tuple(a + b for a, b in zip(used, ratios))
                if any(value > max_pieces for value in new_used):
                    continue
                score = _add_score(base_score, option_score)
                candidate = (score, path + (ratios,))
                current = next_states.get(new_used)
                if current is None or candidate < current:
                    next_states[new_used] = candidate
        if not next_states:
            return None
        states = next_states

    feasible = [
        (score, used, path)
        for used, (score, path) in states.items()
        if all(value > 0 for value in used)
    ]
    if not feasible:
        return None
    score, _, path = min(feasible)

    plan = []
    for lay_index, ply_count in enumerate(plies):
        ratio = {size: path[size_index][lay_index] for size_index, size in enumerate(sizes)}
        plan.append((ratio, ply_count))
    return score, plan


def solve(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[Plan]:
    """Find the minimum lay count, then the lowest weighted deviation found."""
    effective_max_plies = _normalize_ply(max_plies, max_plies, tubular)
    if effective_max_plies is None:
        return None
    sizes = list(order)
    lower_bounds = [_integer_bounds(order[size], tolerance_pct)[0] for size in sizes]
    minimum_total_cut = sum(lower_bounds)
    lay_capacity = effective_max_plies * max_pieces
    lower_lays = max(1, math.ceil(minimum_total_cut / lay_capacity))
    upper_lays = min(max_lays, MAX_DIRECT_LAYS)
    deadline = time.monotonic() + SEARCH_SECONDS

    for lay_count in range(lower_lays, upper_lays + 1):
        candidates = _candidate_plies(
            order, max_plies, max_pieces, tolerance_pct, tubular, lay_count,
        )
        best = None
        for plies in _ply_tuples(candidates, lay_count, minimum_total_cut, max_pieces):
            if time.monotonic() >= deadline:
                break
            solved = _solve_ratios(
                plies, order, sizes, max_pieces, tolerance_pct,
            )
            if solved is not None:
                score, plan = solved
                plan_key = tuple(
                    (ply_count, tuple(ratio[size] for size in sizes))
                    for ratio, ply_count in plan
                )
                candidate = (score, plan_key, plan)
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
                if solved[0] == (0, 0, 0, 0):
                    break
        if best is not None:
            return best[2]
        if time.monotonic() >= deadline:
            break
    return None
