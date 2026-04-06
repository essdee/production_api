"""
PSO/GA Hybrid Strategy — Population-based metaheuristic optimization.

Combines Particle Swarm Optimization (ply tuning) with Genetic Algorithm
operators (crossover, mutation on marker ratios and lay structure).

Multi-objective fitness:
  1. Minimize number of lays (primary)
  2. Minimize total deviation from order (secondary)
  3. Penalize tolerance violations heavily

Based on cutting stock PSO/GA literature (Dyckhoff 1990, multi-objective
metaheuristics for apparel COP).

Strengths:
  - Explores diverse solution space without enumeration
  - Can escape local optima via population diversity
  - Handles large orders without exponential blowup
  - Naturally multi-objective

Weaknesses:
  - No optimality guarantee (stochastic)
  - Slower than MILP/Colgen on well-structured problems
  - Results vary between runs (mitigated by multiple restarts)
"""

import math
import random
import time
from typing import Dict, List, Optional, Tuple

from .common import (
    check_tolerance,
    total_deviation,
    generate_candidate_ratios,
    candidate_plies,
)
# Seeding: only greedy_subtraction (no colgen/milp — strategies must stand alone)
from . import strategy_greedy as _greedy


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POP_SIZE = 80           # Population size
GENERATIONS = 200       # Max generations
ELITE_FRAC = 0.1        # Top fraction preserved as elites
CROSSOVER_RATE = 0.7    # Probability of crossover
MUTATION_RATE = 0.3     # Probability of mutation per individual
PLY_MUTATION_RANGE = 5  # ±plies for ply mutation
N_RESTARTS = 3          # Independent restarts (best-of-N)
STAGNATION_LIMIT = 40   # Generations without improvement before restart

# Fitness weights
W_LAYS = 1000.0         # Weight for number of lays
W_DEVIATION = 1.0       # Weight for total deviation
W_VIOLATION = 50000.0   # Penalty per violated size


# ---------------------------------------------------------------------------
# Individual representation
# ---------------------------------------------------------------------------

class Individual:
    """
    A lay plan encoded as a list of (ratio_dict, ply_count) tuples.
    """
    __slots__ = ['lays', 'fitness', '_cut_totals']

    def __init__(self, lays: List[Tuple[Dict[str, int], int]]):
        self.lays = lays
        self.fitness = float('inf')
        self._cut_totals = None

    def copy(self) -> 'Individual':
        ind = Individual([(dict(r), p) for r, p in self.lays])
        ind.fitness = self.fitness
        return ind

    def cut_totals(self, sizes: List[str]) -> Dict[str, int]:
        if self._cut_totals is None:
            self._cut_totals = {s: 0 for s in sizes}
            for ratio, plies in self.lays:
                for s in sizes:
                    self._cut_totals[s] += ratio.get(s, 0) * plies
        return self._cut_totals

    def invalidate(self):
        self._cut_totals = None
        self.fitness = float('inf')


# ---------------------------------------------------------------------------
# Fitness evaluation
# ---------------------------------------------------------------------------

def _evaluate(
    ind: Individual,
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
) -> float:
    """
    Compute fitness (lower = better).
    
    fitness = W_LAYS * n_lays
            + W_DEVIATION * total_abs_deviation
            + W_VIOLATION * n_violated_sizes
    """
    n_lays = len(ind.lays)
    totals = ind.cut_totals(sizes)

    dev = sum(abs(totals[s] - order[s]) for s in sizes)

    violations = 0
    max_violation = 0.0
    for s in sizes:
        if order[s] > 0:
            pct = abs(totals[s] - order[s]) / order[s]
            if pct > tol:
                violations += 1
                max_violation = max(max_violation, pct - tol)

    # Penalty scales with how far over tolerance we are
    violation_penalty = violations * W_VIOLATION + max_violation * W_VIOLATION * 10

    fitness = W_LAYS * n_lays + W_DEVIATION * dev + violation_penalty
    ind.fitness = fitness
    return fitness


# ---------------------------------------------------------------------------
# Ratio pool generation
# ---------------------------------------------------------------------------

def _build_ratio_pool(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
) -> List[Dict[str, int]]:
    """
    Build a diverse pool of marker ratios for the GA to draw from.
    """
    pool_set = set()
    pool = []

    def add(ratio):
        key = tuple(ratio.get(s, 0) for s in sizes)
        total = sum(key)
        if total > 0 and total <= max_pieces and key not in pool_set:
            pool_set.add(key)
            pool.append(dict(ratio))

    # Generate ratios at key ply counts
    active_sizes = [s for s in sizes if order[s] > 0]
    total_qty = sum(order[s] for s in active_sizes)

    key_plies = set()
    key_plies.add(max_plies)
    key_plies.add(max_plies // 2)
    key_plies.add(max_plies // 3)
    for s in active_sizes:
        q = order[s]
        for r in range(1, min(max_pieces + 1, q + 1)):
            p = q // r
            if 0 < p <= max_plies:
                key_plies.add(p)
            if r > 0:
                p2 = math.ceil(q / r)
                if 0 < p2 <= max_plies:
                    key_plies.add(p2)

    for plies in sorted(key_plies):
        if plies <= 0:
            continue
        ratios = generate_candidate_ratios(order, sizes, max_pieces, plies, mode="all")
        for r in ratios:
            add(r)

    # Single-size ratios (for cleanup lays)
    for s in active_sizes:
        for r_val in range(1, min(max_pieces + 1, order[s] + 1)):
            d = {sz: 0 for sz in sizes}
            d[s] = r_val
            add(d)

    # Proportional ratios at various densities
    for density in range(max(1, max_pieces - 3), max_pieces + 1):
        ratio = {}
        budget = density
        sorted_s = sorted(active_sizes, key=lambda s: -order[s])
        for s in sorted_s:
            if budget <= 0:
                break
            prop = order[s] / total_qty if total_qty > 0 else 0
            r = max(0, min(budget, round(prop * density)))
            ratio[s] = r
            budget -= r
        for s in sorted_s:
            if budget <= 0:
                break
            if ratio.get(s, 0) == 0 and order[s] > 0:
                ratio[s] = 1
                budget -= 1
        add(ratio)

    return pool


# ---------------------------------------------------------------------------
# Random individual generation
# ---------------------------------------------------------------------------

def _random_individual(
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tol: float,
    ratio_pool: List[Dict[str, int]],
    tubular: bool,
) -> Individual:
    """
    Generate a random individual via greedy construction with randomization.
    Uses a 'peel-off' approach: pick a high-ply ratio, subtract from remaining, repeat.
    """
    remaining = dict(order)
    lays = []
    max_tries = 10  # max lays before giving up

    for _ in range(max_tries):
        active = [s for s in sizes if remaining[s] > 0]
        if not active:
            break

        max_rem = max(remaining[s] for s in active)
        if max_rem <= 0:
            break

        # Pick ply count: bias toward covering the largest remaining size
        # with some randomization
        target_plies = min(max_plies, max_rem)
        jitter = random.uniform(0.6, 1.0)
        p = max(1, int(target_plies * jitter))
        if tubular:
            p = max(2, p - (p % 2))

        # Build a ratio for this ply count that covers remaining well
        # Strategy varies randomly for diversity
        strategy = random.choice(['floor', 'ceil', 'pool'])

        if strategy == 'floor':
            ratio = {s: remaining[s] // p if remaining[s] > 0 else 0 for s in sizes}
            # Trim to max_pieces
            while sum(ratio.values()) > max_pieces:
                min_s = min(sizes, key=lambda s: ratio[s] if ratio[s] > 0 else float('inf'))
                if ratio[min_s] > 0:
                    ratio[min_s] -= 1
                else:
                    break
        elif strategy == 'ceil':
            ratio = {s: min(math.ceil(remaining[s] / p), remaining[s])
                     if remaining[s] > 0 else 0 for s in sizes}
            while sum(ratio.values()) > max_pieces:
                # Trim smallest contribution
                trimmable = [(ratio[s], s) for s in sizes if ratio[s] > 0]
                trimmable.sort()
                ratio[trimmable[0][1]] -= 1
        else:
            # Pick from pool
            best_ratio = None
            best_score = -1
            sample = random.sample(ratio_pool, min(20, len(ratio_pool)))
            for r in sample:
                score = 0
                for s in sizes:
                    cut = r.get(s, 0) * p
                    if remaining[s] > 0 and cut > 0:
                        # Score by how much demand this covers
                        score += min(cut, remaining[s])
                    if cut > remaining[s] * (1 + tol) and remaining[s] > 0:
                        score -= cut  # penalize overcut
                if score > best_score:
                    best_score = score
                    best_ratio = r
            ratio = dict(best_ratio) if best_ratio else {s: 0 for s in sizes}

        if sum(ratio.values()) == 0:
            continue

        lays.append((ratio, p))

        # Update remaining
        for s in sizes:
            remaining[s] -= ratio.get(s, 0) * p

    if not lays:
        # Fallback: single proportional lay
        ratio = {s: max(0, min(math.ceil(order[s] / max_plies), max_pieces))
                 for s in sizes}
        total = sum(ratio.values())
        while total > max_pieces:
            min_s = min(sizes, key=lambda s: ratio[s] if ratio[s] > 0 else float('inf'))
            if ratio[min_s] > 0:
                ratio[min_s] -= 1
                total -= 1
            else:
                break
        lays.append((ratio, max_plies))

    return Individual(lays)


# ---------------------------------------------------------------------------
# Genetic operators
# ---------------------------------------------------------------------------

def _crossover(
    parent1: Individual,
    parent2: Individual,
) -> Tuple[Individual, Individual]:
    """
    Two-point crossover on lay lists.
    """
    l1 = [(dict(r), p) for r, p in parent1.lays]
    l2 = [(dict(r), p) for r, p in parent2.lays]

    if len(l1) < 2 or len(l2) < 2:
        # Single-lay: swap one lay
        child1_lays = l1[:1] + l2[1:] if len(l2) > 1 else l1
        child2_lays = l2[:1] + l1[1:] if len(l1) > 1 else l2
    else:
        # Two-point crossover
        pt1 = random.randint(0, len(l1) - 1)
        pt2 = random.randint(0, len(l2) - 1)
        child1_lays = l1[:pt1] + l2[pt2:]
        child2_lays = l2[:pt2] + l1[pt1:]

    return Individual(child1_lays), Individual(child2_lays)


def _mutate(
    ind: Individual,
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    ratio_pool: List[Dict[str, int]],
    tubular: bool,
):
    """
    Apply one random mutation:
    1. Adjust ply count on a random lay (PSO-inspired velocity)
    2. Replace a ratio with another from the pool
    3. Add a new lay
    4. Remove a lay (if > 1)
    5. Split a lay into two
    6. Merge two lays
    """
    op = random.choices(
        ['ply_adjust', 'ratio_swap', 'add_lay', 'remove_lay', 'split_lay',
         'merge_lays', 'redistribute'],
        weights=[25, 20, 10, 10, 5, 5, 25],
        k=1,
    )[0]

    if op == 'ply_adjust' and ind.lays:
        idx = random.randint(0, len(ind.lays) - 1)
        ratio, plies = ind.lays[idx]
        delta = random.randint(-PLY_MUTATION_RANGE, PLY_MUTATION_RANGE)
        new_plies = plies + delta
        if tubular:
            new_plies = max(2, min(max_plies, new_plies))
            if new_plies % 2 != 0:
                new_plies += 1 if new_plies < max_plies else -1
        else:
            new_plies = max(1, min(max_plies, new_plies))
        ind.lays[idx] = (ratio, new_plies)

    elif op == 'ratio_swap' and ind.lays and ratio_pool:
        idx = random.randint(0, len(ind.lays) - 1)
        _, plies = ind.lays[idx]
        new_ratio = random.choice(ratio_pool)
        ind.lays[idx] = (dict(new_ratio), plies)

    elif op == 'add_lay' and len(ind.lays) < 12:
        ratio = random.choice(ratio_pool) if ratio_pool else {s: 1 for s in sizes}
        p = random.randint(1, max(1, max_plies // 3))
        if tubular and p % 2 != 0:
            p = max(2, p + 1)
        ind.lays.append((dict(ratio), p))

    elif op == 'remove_lay' and len(ind.lays) > 1:
        idx = random.randint(0, len(ind.lays) - 1)
        ind.lays.pop(idx)

    elif op == 'split_lay' and ind.lays:
        idx = random.randint(0, len(ind.lays) - 1)
        ratio, plies = ind.lays[idx]
        if plies >= 4:
            split_at = random.randint(2, plies - 2)
            if tubular:
                split_at = split_at - (split_at % 2)
                if split_at < 2:
                    split_at = 2
            ind.lays[idx] = (dict(ratio), split_at)
            ind.lays.append((dict(ratio), plies - split_at))

    elif op == 'merge_lays' and len(ind.lays) >= 2:
        i, j = random.sample(range(len(ind.lays)), 2)
        r1, p1 = ind.lays[i]
        r2, p2 = ind.lays[j]
        # Merge: average ratios, sum plies (cap at max_plies)
        merged_r = {}
        for s in sizes:
            merged_r[s] = max(r1.get(s, 0), r2.get(s, 0))
        total = sum(merged_r.values())
        while total > max_pieces:
            min_s = min(sizes, key=lambda s: merged_r[s] if merged_r[s] > 0 else float('inf'))
            if merged_r[min_s] > 0:
                merged_r[min_s] -= 1
                total -= 1
            else:
                break
        merged_p = min(p1 + p2, max_plies)
        if tubular and merged_p % 2 != 0:
            merged_p -= 1
        # Remove higher index first
        for idx in sorted([i, j], reverse=True):
            ind.lays.pop(idx)
        ind.lays.append((merged_r, merged_p))

    elif op == 'redistribute' and len(ind.lays) >= 2:
        # Try to redistribute: remove smallest lay, boost others' plies to compensate
        # This is the key operator for reducing lay count
        sorted_by_pieces = sorted(range(len(ind.lays)),
                                   key=lambda i: ind.lays[i][1])
        victim = sorted_by_pieces[0]
        v_ratio, v_plies = ind.lays[victim]

        # Remove victim
        new_lays = [lay for i, lay in enumerate(ind.lays) if i != victim]

        # Try to absorb victim's contribution by increasing other lays' plies
        for i in range(len(new_lays)):
            r, p = new_lays[i]
            headroom = max_plies - p
            if headroom <= 0:
                continue
            bump = random.randint(1, min(5, headroom))
            new_p = min(max_plies, p + bump)
            if tubular and new_p % 2 != 0:
                new_p -= 1
            new_lays[i] = (r, new_p)

        ind.lays = new_lays

    ind.invalidate()


# ---------------------------------------------------------------------------
# Local search refinement
# ---------------------------------------------------------------------------

def _local_search(
    ind: Individual,
    order: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    tol: float,
    tubular: bool,
    steps: int = 20,
) -> Individual:
    """
    Hill-climbing on ply counts to minimize deviation while staying feasible.
    """
    best = ind.copy()
    _evaluate(best, order, sizes, tol)

    for _ in range(steps):
        candidate = best.copy()
        if not candidate.lays:
            break

        idx = random.randint(0, len(candidate.lays) - 1)
        ratio, plies = candidate.lays[idx]

        # Try ±1, ±2
        for delta in [-2, -1, 1, 2]:
            new_p = plies + delta
            if new_p < 1 or new_p > max_plies:
                continue
            if tubular and new_p % 2 != 0:
                continue

            trial = best.copy()
            trial.lays[idx] = (dict(ratio), new_p)
            trial.invalidate()
            _evaluate(trial, order, sizes, tol)

            if trial.fitness < best.fitness:
                best = trial
                break

    return best


# ---------------------------------------------------------------------------
# Main solver
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
    PSO/GA hybrid solver for lay planning.

    Returns list of (ratio_dict, plies) tuples, or None if no feasible solution found.
    """
    sizes = list(order.keys())
    tol = tolerance_pct / 100.0
    n = len(sizes)
    if n == 0:
        return None

    # Build ratio pool
    ratio_pool = _build_ratio_pool(order, sizes, max_plies, max_pieces)
    if not ratio_pool:
        return None

    global_best = None
    global_best_fitness = float('inf')

    # Seed plans from other strategies (gives GA a strong starting point)
    seed_plans = []
    for solver in [_greedy]:
        try:
            plan = solver.solve(order, max_plies, max_pieces, tolerance_pct,
                                max_lays, tubular)
            if plan:
                seed_plans.append(plan)
        except Exception:
            pass

    for restart in range(N_RESTARTS):
        # Initialize population
        population = []

        # Add seeds (with ply perturbations for diversity)
        for plan in seed_plans:
            # Original seed
            ind = Individual([(dict(r), p) for r, p in plan])
            _evaluate(ind, order, sizes, tol)
            population.append(ind)

            # Perturbed copies
            for _ in range(3):
                perturbed = Individual([(dict(r), p) for r, p in plan])
                for i in range(len(perturbed.lays)):
                    r, p = perturbed.lays[i]
                    delta = random.randint(-3, 3)
                    new_p = max(1, min(max_plies, p + delta))
                    if tubular and new_p % 2 != 0:
                        new_p += 1 if new_p < max_plies else -1
                    perturbed.lays[i] = (r, new_p)
                perturbed.invalidate()
                _evaluate(perturbed, order, sizes, tol)
                population.append(perturbed)

        # Fill rest with smart random construction
        while len(population) < POP_SIZE:
            ind = _random_individual(order, sizes, max_plies, max_pieces, tol,
                                     ratio_pool, tubular)
            _evaluate(ind, order, sizes, tol)
            population.append(ind)

        # Sort by fitness
        population.sort(key=lambda x: x.fitness)
        best = population[0].copy()
        stagnation = 0

        for gen in range(GENERATIONS):
            n_elite = max(2, int(POP_SIZE * ELITE_FRAC))
            new_pop = [ind.copy() for ind in population[:n_elite]]

            # Tournament selection + crossover + mutation
            while len(new_pop) < POP_SIZE:
                # Tournament selection (size 3)
                t1 = min(random.sample(population, min(3, len(population))),
                         key=lambda x: x.fitness)
                t2 = min(random.sample(population, min(3, len(population))),
                         key=lambda x: x.fitness)

                if random.random() < CROSSOVER_RATE:
                    c1, c2 = _crossover(t1, t2)
                else:
                    c1, c2 = t1.copy(), t2.copy()

                for child in [c1, c2]:
                    if random.random() < MUTATION_RATE:
                        _mutate(child, order, sizes, max_plies, max_pieces,
                                ratio_pool, tubular)

                    # Remove empty lays
                    child.lays = [(r, p) for r, p in child.lays
                                  if p > 0 and sum(r.values()) > 0]
                    if not child.lays:
                        child = _random_individual(order, sizes, max_plies, max_pieces,
                                                    tol, ratio_pool, tubular)

                    _evaluate(child, order, sizes, tol)
                    new_pop.append(child)

                    if len(new_pop) >= POP_SIZE:
                        break

            # Apply local search to top 10%
            for i in range(min(n_elite, len(new_pop))):
                refined = _local_search(new_pop[i], order, sizes, max_plies,
                                        tol, tubular, steps=15)
                if refined.fitness < new_pop[i].fitness:
                    new_pop[i] = refined

            population = sorted(new_pop, key=lambda x: x.fitness)[:POP_SIZE]

            if population[0].fitness < best.fitness:
                best = population[0].copy()
                stagnation = 0
            else:
                stagnation += 1

            # Early termination on stagnation
            if stagnation >= STAGNATION_LIMIT:
                break

        # Update global best
        if best.fitness < global_best_fitness:
            global_best = best
            global_best_fitness = best.fitness

    if global_best is None:
        return None

    # Extract plan and validate
    plan = [(dict(r), p) for r, p in global_best.lays if p > 0 and sum(r.values()) > 0]

    if not plan:
        return None

    if not check_tolerance(plan, order, sizes, tol):
        return None

    # Sort by ply count descending
    plan.sort(key=lambda x: -x[1])

    return plan
