"""
Common utilities shared across all lay optimizer strategies.

Contains:
- Timeout management (_SolverTimeout, _SolverTimer, _with_timeout)
- Ratio generation (_generate_candidate_ratios)
- Ratio distribution (_distribute_ratios)
- Plan validation helpers
"""

import math
import importlib
import multiprocessing as mp
import queue
import traceback
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Timeout management
# ---------------------------------------------------------------------------

class _SolverTimeout(Exception):
    """Raised inside any solver when a per-solver wall-clock budget is exceeded."""
    pass


class _SolverTimer:
    """Compatibility no-op for older strategies that manage their own deadline."""

    def __init__(self, budget_secs: float):
        self._budget = budget_secs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return exc_type is _SolverTimeout


def _solver_process_entry(module_name, result_queue, args, kwargs):
    """Import and execute one solver inside an isolated child process."""
    try:
        module = importlib.import_module(module_name)
        result_queue.put({"status": "ok", "plan": module.solve(*args, **kwargs)})
    except BaseException as exc:  # child failures must be reported to the parent
        result_queue.put({
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        })


def run_solver_process(module_name, budget_secs: float, *args, **kwargs):
    """Run a strategy in a killable process and return (plan, status, error)."""
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_solver_process_entry,
        args=(module_name, result_queue, args, kwargs),
        daemon=True,
    )
    process.start()
    process.join(max(0.1, float(budget_secs)))

    if process.is_alive():
        process.terminate()
        process.join(2.0)
        result_queue.cancel_join_thread()
        result_queue.close()
        process.close()
        return None, "timeout", f"Timed out after {budget_secs:.1f}s"

    try:
        payload = result_queue.get(timeout=1.0)
    except queue.Empty:
        return None, "error", f"Strategy process exited with code {process.exitcode} without a result"
    finally:
        result_queue.close()
        result_queue.join_thread()
        process.close()

    if payload.get("status") == "ok":
        return payload.get("plan"), "ok", None
    return None, "error", payload.get("error", "Unknown strategy error")


def with_timeout(fn, budget_secs: float, *args, **kwargs):
    """Backward-compatible wrapper using safe process isolation."""
    plan, status, _ = run_solver_process(fn.__module__, budget_secs, *args, **kwargs)
    return plan if status == "ok" else None


def validate_inputs(order, max_plies, max_pieces, tolerance_pct, max_lays):
    """Raise ValueError for malformed or physically meaningless inputs."""
    if not isinstance(order, dict) or not order:
        raise ValueError("Order must contain at least one size")
    if any(not str(size).strip() for size in order):
        raise ValueError("Every size must have a non-empty name")
    if any(isinstance(qty, bool) or int(qty) != qty or int(qty) < 0 for qty in order.values()):
        raise ValueError("Order quantities must be non-negative integers")
    if sum(int(qty) for qty in order.values()) <= 0:
        raise ValueError("At least one order quantity must be greater than zero")
    if isinstance(max_plies, bool) or int(max_plies) != max_plies or int(max_plies) <= 0:
        raise ValueError("Maximum plies must be a positive integer")
    if isinstance(max_pieces, bool) or int(max_pieces) != max_pieces or int(max_pieces) <= 0:
        raise ValueError("Maximum pieces per marker must be a positive integer")
    if isinstance(max_lays, bool) or int(max_lays) != max_lays or int(max_lays) <= 0:
        raise ValueError("Maximum lays must be a positive integer")
    if not 0 <= float(tolerance_pct) <= 100:
        raise ValueError("Tolerance must be between 0 and 100 percent")


def validate_plan(plan, order, max_plies, max_pieces, tolerance_pct, max_lays, tubular=False):
    """Return a list of every hard-constraint violation in a proposed plan."""
    errors = []
    sizes = list(order.keys())
    if not isinstance(plan, list) or not plan:
        return ["plan is empty"]
    if len(plan) > max_lays:
        errors.append(f"uses {len(plan)} lays; maximum is {max_lays}")

    totals = {s: 0 for s in sizes}
    for lay_no, lay in enumerate(plan, 1):
        if not isinstance(lay, (tuple, list)) or len(lay) != 2:
            errors.append(f"lay {lay_no} is not a (ratio, plies) pair")
            continue
        ratio, plies = lay
        if isinstance(plies, bool) or not isinstance(plies, int):
            errors.append(f"lay {lay_no} plies must be an integer")
            continue
        if not 1 <= plies <= max_plies:
            errors.append(f"lay {lay_no} has {plies} plies; allowed range is 1..{max_plies}")
        if tubular and plies % 2:
            errors.append(f"lay {lay_no} has odd plies ({plies}) for tubular fabric")
        if not isinstance(ratio, dict):
            errors.append(f"lay {lay_no} ratio must be a mapping")
            continue
        unknown = set(ratio) - set(sizes)
        if unknown:
            errors.append(f"lay {lay_no} contains unknown sizes: {', '.join(sorted(unknown))}")
        marker_total = 0
        for s in sizes:
            value = ratio.get(s, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"lay {lay_no} ratio for {s} must be a non-negative integer")
                continue
            marker_total += value
            totals[s] += value * plies
        if not 1 <= marker_total <= max_pieces:
            errors.append(
                f"lay {lay_no} has {marker_total} pieces per marker; allowed range is 1..{max_pieces}"
            )

    tol = float(tolerance_pct) / 100.0
    for s, target in order.items():
        if target == 0:
            if totals[s] != 0:
                errors.append(f"size {s} has zero demand but cuts {totals[s]}")
        elif abs(totals[s] - target) / target > tol + 1e-12:
            pct = abs(totals[s] - target) / target * 100
            errors.append(f"size {s} deviation is {pct:.2f}%; tolerance is {tolerance_pct}%")
    return errors


# ---------------------------------------------------------------------------
# Ratio distribution
# ---------------------------------------------------------------------------

def distribute_ratios(
    total_ratios: List[int], n_lays: int, max_per_lay: int
) -> Optional[List[List[int]]]:
    """
    Distribute total ratio requirements across n_lays, each with sum ≤ max_per_lay.
    Returns list of ratio lists, or None if infeasible.
    """
    n = len(total_ratios)
    lays = [[0] * n for _ in range(n_lays)]

    for i, total in enumerate(total_ratios):
        base = total // n_lays
        extra = total % n_lays
        for j in range(n_lays):
            lays[j][i] = base + (1 if j < extra else 0)

    for _ in range(300):
        overloaded = [j for j in range(n_lays) if sum(lays[j]) > max_per_lay]
        if not overloaded:
            break
        underloaded = [j for j in range(n_lays) if sum(lays[j]) < max_per_lay]
        if not underloaded:
            return None
        src, dst = overloaded[0], underloaded[0]
        moved = False
        for i in sorted(range(n), key=lambda i: lays[src][i], reverse=True):
            if lays[src][i] > 0 and sum(lays[dst]) < max_per_lay:
                lays[src][i] -= 1
                lays[dst][i] += 1
                moved = True
        if not moved:
            return None

    for j in range(n_lays):
        if sum(lays[j]) > max_per_lay:
            return None
    for i in range(n):
        if sum(lays[j][i] for j in range(n_lays)) != total_ratios[i]:
            return None
    return lays


# ---------------------------------------------------------------------------
# Candidate ratio generation
# ---------------------------------------------------------------------------

def generate_candidate_ratios(
    order: Dict[str, int],
    sizes: List[str],
    max_pieces: int,
    plies: int,
    mode: str = "all",
) -> List[Dict[str, int]]:
    """
    Generate candidate marker ratios for a given ply count.
    
    mode: "floor" = floor(qty/plies), "ceil" = ceil(qty/plies),
          "all" = floor, ceil, greedy-bump, and zero-some-sizes variants.
    Returns list of ratio dicts.
    """
    if plies <= 0:
        return []

    n = len(sizes)
    results = []
    seen = set()

    def _add(ratio):
        key = tuple(ratio[s] for s in sizes)
        if key not in seen:
            total = sum(ratio.values())
            if 0 < total <= max_pieces:
                seen.add(key)
                results.append(dict(ratio))

    if mode == "floor":
        ratio = {s: order[s] // plies if order[s] > 0 else 0 for s in sizes}
        _add(ratio)
        return results

    if mode == "ceil":
        ratio = {s: math.ceil(order[s] / plies) if order[s] > 0 else 0 for s in sizes}
        _add(ratio)
        return results

    # "all" mode: generate multiple candidate ratios
    floor_r = {s: order[s] // plies if order[s] > 0 else 0 for s in sizes}
    ceil_r = {s: math.ceil(order[s] / plies) if order[s] > 0 else 0 for s in sizes}

    # 1. Pure floor and ceil
    _add(floor_r)
    _add(ceil_r)

    # 2. Floor + selectively bump sizes to ceil
    floor_total = sum(floor_r.values())
    budget = max_pieces - floor_total
    if budget > 0 and floor_total > 0:
        undershoot = []
        for s in sizes:
            deficit = order[s] - floor_r[s] * plies
            bump = ceil_r[s] - floor_r[s]
            if bump > 0 and deficit > 0:
                undershoot.append((deficit, bump, s))

        # Strategy A: bump biggest deficit first (greedy)
        undershoot_a = sorted(undershoot, reverse=True)
        combo_a = dict(floor_r)
        b = budget
        for deficit, bump, s in undershoot_a:
            if bump <= b:
                combo_a[s] = ceil_r[s]
                b -= bump
        _add(combo_a)

        # Strategy B: bump smallest deficit first (leaves more room for lay 2)
        undershoot_b = sorted(undershoot)
        combo_b = dict(floor_r)
        b = budget
        for deficit, bump, s in undershoot_b:
            if bump <= b:
                combo_b[s] = ceil_r[s]
                b -= bump
        _add(combo_b)

        # Strategy C: only bump sizes where floor leaves > tolerance gap
        combo_c = dict(floor_r)
        b = budget
        for deficit, bump, s in sorted(undershoot, reverse=True):
            pct_gap = deficit / order[s] if order[s] > 0 else 0
            if pct_gap > 0.03 and bump <= b:
                combo_c[s] = ceil_r[s]
                b -= bump
        _add(combo_c)

    # 3. Zero-out small sizes to make room for bigger ratios on large sizes
    active_sizes = [s for s in sizes if order[s] > 0]
    if len(active_sizes) > 1:
        sorted_by_qty = sorted(active_sizes, key=lambda s: order[s])
        for n_zero in range(1, min(len(active_sizes), n // 2 + 1)):
            zero_sizes = set(sorted_by_qty[:n_zero])
            ratio = {}
            for s in sizes:
                if s in zero_sizes or order[s] <= 0:
                    ratio[s] = 0
                else:
                    ratio[s] = math.ceil(order[s] / plies)
            _add(ratio)
            ratio_f = {}
            for s in sizes:
                if s in zero_sizes or order[s] <= 0:
                    ratio_f[s] = 0
                else:
                    ratio_f[s] = order[s] // plies
            _add(ratio_f)

    # 4. Round-to-nearest ratios
    ratio_round = {s: round(order[s] / plies) if order[s] > 0 else 0 for s in sizes}
    _add(ratio_round)

    return results


# ---------------------------------------------------------------------------
# Plan validation & scoring helpers
# ---------------------------------------------------------------------------

def check_tolerance(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
) -> bool:
    """Check if plan is within tolerance for every size."""
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


def total_deviation(
    plan: List[Tuple[Dict[str, int], int]],
    order: Dict[str, int],
    sizes: List[str],
) -> int:
    """Compute total absolute deviation from order."""
    totals = {s: 0 for s in sizes}
    for ratio, plies in plan:
        for s in sizes:
            totals[s] += ratio.get(s, 0) * plies
    return sum(abs(totals[s] - order[s]) for s in sizes)


def plan_cut_totals(
    plan: List[Tuple[Dict[str, int], int]],
    sizes: List[str],
) -> Dict[str, int]:
    """Compute total cut per size from a plan."""
    totals = {s: 0 for s in sizes}
    for ratio, plies in plan:
        for s in sizes:
            totals[s] += ratio.get(s, 0) * plies
    return totals


def within_tolerance_totals(
    totals: Dict[str, int],
    order: Dict[str, int],
    sizes: List[str],
    tol: float,
) -> bool:
    """Check per-size tolerance given pre-computed totals."""
    for s in sizes:
        if order[s] > 0 and abs(totals[s] - order[s]) / order[s] > tol:
            return False
    return True


def candidate_plies(
    remaining: Dict[str, int],
    sizes: List[str],
    max_plies: int,
    max_pieces: int,
    tubular: bool = False,
) -> List[int]:
    """Generate candidate ply counts from remaining quantities."""
    active = [s for s in sizes if remaining[s] > 0]
    if not active:
        return []

    cands = set()
    max_rem = max(remaining[s] for s in active)
    min_rem = min(remaining[s] for s in active)

    cands.add(min_rem)
    cands.add(max_rem)

    for s in active:
        r = remaining[s]
        cands.add(r)
        for d in range(1, min(int(math.sqrt(r)) + 1, max_plies + 1)):
            if r % d == 0:
                cands.add(d)
                cands.add(r // d)
        for ratio_val in range(1, min(max_pieces + 1, r + 1)):
            p = r // ratio_val
            if p > 0:
                cands.add(p)
            p2 = math.ceil(r / ratio_val) if ratio_val > 0 else 0
            if p2 > 0:
                cands.add(p2)

    for p in range(1, max_plies + 1):
        cands.add(p)

    valid = sorted(c for c in cands if 0 < c <= max_plies)
    if tubular:
        valid = [c for c in valid if c % 2 == 0]

    return valid
