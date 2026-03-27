#!/usr/bin/env python3
"""
Lay Planning Optimizer for Essdee MRP — v2.1
==============================================

Given an order (qty per size), max plies per lay, and max pieces per marker,
finds MULTIPLE lay plans ranked by different strategies.

Strategies:
  1. MIN LAYS       — Fewest lays possible (minimize spreading time)
  2. MIN OVERCUT    — Closest to order qty (minimize fabric waste)
  3. BALANCED       — Good trade-off between lays and accuracy
  4. MAX DENSITY    — Highest pieces/ply (better marker efficiency)
  5. SINGLE RATIO   — One marker ratio for all lays (simplest for CAD)

Each lay has:
  - A ratio (how many garments of each size per ply)
  - A ply count (number of fabric layers)
  - Cut qty per size = ratio × plies

Constraint: sum of ratios in any single lay ≤ max_pieces (marker capacity).
Goal: present multiple options so the planner picks the best trade-off.

Usage (CLI):
    python3 lay_optimizer.py \\
        --order "45:208,50:333,55:229,60:239,65:225,70:225,75:225" \\
        --max-plies 70 --max-pieces 21

    python3 lay_optimizer.py \\
        --order '{"45":208,"50":333,"55":229}' \\
        --max-plies 70 --max-pieces 21 --json

Usage (Python API):
    from lay_optimizer import optimize_lay_plan, optimize_all_strategies

    # Single best plan
    result = optimize_lay_plan(order, max_plies, max_pieces)

    # All strategies
    plans = optimize_all_strategies(order, max_plies, max_pieces)
    for plan in plans:
        print(plan['strategy'], plan['summary']['total_lays'])

Frappe Integration:
    Drop this file into your Frappe app's utils/ folder.
    Call optimize_all_strategies() from Cutting Plan doctype.

Author: VETRI (Essdee Production Intelligence)
Version: 2.1.0
Date: 2026-03-27
"""

import argparse
import json
import math
import sys
from itertools import product as cartesian_product
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Core solver
# ---------------------------------------------------------------------------

def _distribute_ratios(total_ratios: List[int], n_lays: int, max_per_lay: int) -> Optional[List[List[int]]]:
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
                break
        if not moved:
            return None

    for j in range(n_lays):
        if sum(lays[j]) > max_per_lay:
            return None
    for i in range(n):
        if sum(lays[j][i] for j in range(n_lays)) != total_ratios[i]:
            return None
    return lays


def _solve_two_tier(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    prefer: str = "min_lays",
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Two-tier solver: n_full lays at max_plies + n_sub lays at smaller ply count.
    prefer: "min_lays" | "min_deviation" | "max_density" | "balanced"
    tubular: if True, all ply counts must be even (tubular fabric = folded)
    """
    sizes = list(order.keys())
    n = len(sizes)
    tol = tolerance_pct / 100.0

    # Tubular: max_plies must be even
    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    # Collect ALL feasible plans, then pick best by preference
    all_plans = []

    # Candidate sub-ply counts
    sub_candidates = sorted(set(
        [d for d in range(1, max_plies + 1) if max_plies % d == 0]
        + list(range(max(1, max_plies // 4), max_plies))
        + list(range(6, max_plies, 6))
    ))
    # Tubular: only even ply counts
    if tubular:
        sub_candidates = [p for p in sub_candidates if p % 2 == 0]
        if not sub_candidates:
            sub_candidates = [2]

    for n_full in range(0, max_lays + 1):
        for n_sub in range(0, max_lays + 1):
            total_lays = n_full + n_sub
            if total_lays == 0 or total_lays > max_lays:
                continue

            sub_plies_list = sub_candidates if n_sub > 0 else [0]

            for sub_plies in sub_plies_list:
                if n_sub > 0 and (sub_plies == 0 or sub_plies >= max_plies):
                    continue

                options_per_size = []
                feasible = True
                for s in sizes:
                    target = order[s]
                    lo = math.ceil(target * (1 - tol))
                    hi = math.floor(target * (1 + tol))

                    valid = []
                    max_rf = (
                        min(n_full * max_pieces, hi // max_plies + 1) if n_full > 0 else 0
                    )

                    for rf in range(0, max_rf + 1):
                        cut_full = rf * max_plies

                        if n_sub > 0 and sub_plies > 0:
                            rs_lo = max(0, math.ceil((lo - cut_full) / sub_plies))
                            rs_hi = min(
                                max(0, math.floor((hi - cut_full) / sub_plies)),
                                n_sub * max_pieces,
                            )
                            for rs in range(rs_lo, rs_hi + 1):
                                total_cut = cut_full + rs * sub_plies
                                if lo <= total_cut <= hi:
                                    valid.append((rf, rs, abs(total_cut - target)))
                        else:
                            if lo <= cut_full <= hi:
                                valid.append((rf, 0, abs(cut_full - target)))

                    if not valid:
                        feasible = False
                        break
                    valid.sort(key=lambda x: x[2])
                    options_per_size.append(valid[:10])

                if not feasible:
                    continue

                search_limit = min(
                    80, math.prod(min(5, len(o)) for o in options_per_size)
                )
                for attempt in range(search_limit):
                    if attempt == 0:
                        selected = [o[0] for o in options_per_size]
                    else:
                        selected = []
                        tmp = attempt
                        for o in options_per_size:
                            k = min(5, len(o))
                            selected.append(o[tmp % k])
                            tmp //= k

                    rf_totals = [s[0] for s in selected]
                    rs_totals = [s[1] for s in selected]

                    if n_full > 0:
                        if sum(rf_totals) == 0:
                            continue
                        full_lays = _distribute_ratios(rf_totals, n_full, max_pieces)
                        if full_lays is None:
                            continue
                    else:
                        full_lays = []

                    if n_sub > 0:
                        if sum(rs_totals) == 0:
                            continue
                        sub_lays_dist = _distribute_ratios(rs_totals, n_sub, max_pieces)
                        if sub_lays_dist is None:
                            continue
                    else:
                        sub_lays_dist = []

                    plan = []
                    for lay in full_lays or []:
                        if sum(lay) > 0:
                            plan.append((dict(zip(sizes, lay)), max_plies))
                    for lay in sub_lays_dist or []:
                        if sum(lay) > 0:
                            plan.append((dict(zip(sizes, lay)), sub_plies))
                    if not plan:
                        continue

                    totals = {s: 0 for s in sizes}
                    for ratio, plies in plan:
                        for s in sizes:
                            totals[s] += ratio[s] * plies

                    ok = True
                    total_dev = 0
                    for s in sizes:
                        dev = abs(totals[s] - order[s])
                        pct = dev / order[s] * 100 if order[s] > 0 else 0
                        if pct > tolerance_pct:
                            ok = False
                            break
                        total_dev += dev

                    if ok:
                        total_density = sum(
                            sum(r.values()) for r, _ in plan
                        ) / len(plan) if plan else 0
                        all_plans.append((plan, len(plan), total_dev, total_density))

    if not all_plans:
        return None

    # Sort by preference
    if prefer == "min_lays":
        all_plans.sort(key=lambda x: (x[1], x[2]))
    elif prefer == "min_deviation":
        all_plans.sort(key=lambda x: (x[2], x[1]))
    elif prefer == "max_density":
        all_plans.sort(key=lambda x: (-x[3], x[1], x[2]))
    elif prefer == "balanced":
        # Score: weighted combination
        all_plans.sort(key=lambda x: (x[1] * 10 + x[2] * 0.5 - x[3] * 2))
    else:
        all_plans.sort(key=lambda x: (x[1], x[2]))

    return all_plans[0][0]


def _solve_single_ratio(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Optional[List[Tuple[Dict[str, int], int]]]:
    """
    Find a plan where ALL lays use the SAME marker ratio (different ply counts).
    Simplest for production: one marker to nest, use it for every lay.

    Strategy: For a fixed ratio R, total_cut[s] = R[s] x total_plies.
    We need R[s] x P ~ order[s] for all s, where P = sum of plies across lays.

    The ratio must be proportional to the order. If the order is very skewed
    (e.g., 144 vs 996), the smallest size constrains the ratio badly.
    tubular: if True, all ply counts must be even (tubular fabric = folded)
    """
    sizes = list(order.keys())
    n = len(sizes)
    total_order = sum(order.values())

    # Tubular: max_plies must be even
    if tubular and max_plies % 2 != 0:
        max_plies -= 1

    best_plan = None
    best_score = float("inf")

    def _evaluate_ratio(ratio, sizes, order, max_plies, max_lays, tolerance_pct, tubular=False):
        """Given a fixed ratio, find the best total_plies and lay distribution."""
        pcs_per_ply = sum(ratio.values())
        if pcs_per_ply == 0:
            return None, float("inf")

        # For each size with ratio > 0, ideal plies = order[s] / ratio[s]
        # We need one total_plies that satisfies all sizes within tolerance
        ideal_per_size = []
        for s in sizes:
            if ratio[s] > 0:
                ideal_per_size.append(order[s] / ratio[s])

        if not ideal_per_size:
            return None, float("inf")

        # Try a range around the median ideal plies
        median_p = sorted(ideal_per_size)[len(ideal_per_size) // 2]
        lo = max(1, int(median_p * 0.85))
        hi = min(max_plies * max_lays, int(median_p * 1.15) + 1)

        # Tubular: only try even total_plies
        step = 2 if tubular else 1
        if tubular and lo % 2 != 0:
            lo += 1

        best_local = None
        best_local_score = float("inf")

        for total_plies in range(lo, hi + 1, step):
            # Check tolerance
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

            # Distribute across lays — each lay must have even plies if tubular
            lays_plies = []
            remaining = total_plies
            for _ in range(max_lays):
                p = min(max_plies, remaining)
                if tubular and p % 2 != 0:
                    p -= 1  # round down to even
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

        plan, score = _evaluate_ratio(ratio, sizes, order, max_plies, max_lays, tolerance_pct, tubular)
        if plan and score < best_score:
            best_score = score
            best_plan = plan

    # Method 2: Try floor/ceil variations of the proportional ratio
    # This catches cases where rounding in one direction works better
    for total_ratio_target in range(max(n, max_pieces // 3), max_pieces + 1):
        base_ratios = {}
        for s in sizes:
            base_ratios[s] = order[s] / total_order * total_ratio_target

        # Try all floor/ceil combos for the first few sizes (limit to avoid explosion)
        # For each size, try floor and ceil of the ideal ratio
        from itertools import product as iter_product

        choices = []
        for s in sizes:
            f = max(0, math.floor(base_ratios[s]))
            c = math.ceil(base_ratios[s])
            choices.append([f, c] if f != c else [f])

        # Cap combinations to prevent explosion (2^8 = 256 max)
        if len(sizes) > 10:
            continue

        for combo in iter_product(*choices):
            ratio = {sizes[i]: combo[i] for i in range(len(sizes))}
            if sum(ratio.values()) == 0 or sum(ratio.values()) > max_pieces:
                continue

            plan, score = _evaluate_ratio(ratio, sizes, order, max_plies, max_lays, tolerance_pct, tubular)
            if plan and score < best_score:
                best_score = score
                best_plan = plan

    return best_plan


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(
    plan: Optional[List[Tuple[Dict[str, int], int]]],
    order: Dict[str, int],
    sizes: List[str],
    strategy: str,
    strategy_desc: str,
    params: dict,
) -> dict:
    """Build standardized result dict from a plan."""
    if plan is None:
        return {
            "success": False,
            "strategy": strategy,
            "strategy_description": strategy_desc,
            "error": f"No feasible plan found within \u00b1{params['tolerance_pct']}% tolerance",
            "lays": [],
            "summary": {},
            "per_size": {},
            "params": params,
        }

    lays_out = []
    totals = {s: 0 for s in sizes}

    for i, (ratio, plies) in enumerate(plan, 1):
        cut = {s: ratio.get(s, 0) * plies for s in sizes}
        for s in sizes:
            totals[s] += cut[s]
        pcs_per_ply = sum(ratio.get(s, 0) for s in sizes)
        lays_out.append({
            "lay_no": i,
            "plies": plies,
            "ratio": {s: ratio.get(s, 0) for s in sizes},
            "pieces_per_ply": pcs_per_ply,
            "total_pieces": sum(cut.values()),
            "cut_per_size": cut,
        })

    per_size = {}
    overcut = 0
    undercut = 0
    for s in sizes:
        diff = totals[s] - order[s]
        pct = abs(diff) / order[s] * 100 if order[s] > 0 else 0
        per_size[s] = {"order": order[s], "cut": totals[s], "diff": diff, "pct": round(pct, 1)}
        if diff > 0:
            overcut += diff
        else:
            undercut += abs(diff)

    total_order = sum(order.values())
    # Count unique ratios
    ratio_strs = set()
    for lay in lays_out:
        r_str = ":".join(str(lay["ratio"][s]) for s in sizes)
        ratio_strs.add(r_str)

    return {
        "success": True,
        "strategy": strategy,
        "strategy_description": strategy_desc,
        "lays": lays_out,
        "summary": {
            "total_lays": len(lays_out),
            "unique_markers": len(ratio_strs),
            "total_cut": sum(totals.values()),
            "total_order": total_order,
            "overcut": overcut,
            "undercut": undercut,
            "overcut_pct": round(overcut / total_order * 100, 1) if total_order > 0 else 0,
            "undercut_pct": round(undercut / total_order * 100, 1) if total_order > 0 else 0,
            "avg_pieces_per_ply": round(
                sum(l["pieces_per_ply"] for l in lays_out) / len(lays_out), 1
            ) if lays_out else 0,
        },
        "per_size": per_size,
        "params": params,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def optimize_lay_plan(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    strategy: str = "min_lays",
    tubular: bool = False,
) -> dict:
    """
    Optimize lay plan for a cutting order using a single strategy.

    Args:
        order:          Dict of {size: quantity}
        max_plies:      Maximum plies per lay (physical table limit)
        max_pieces:     Maximum garment pieces per marker (CAD constraint)
        tolerance_pct:  Allowed deviation per size (default +/-3%)
        max_lays:       Maximum lays to try (default 8)
        strategy:       "min_lays" | "min_overcut" | "balanced" | "max_density" | "single_ratio"
        tubular:        If True, all ply counts must be even (tubular fabric = folded)

    Returns: dict with 'lays', 'summary', 'per_size', 'strategy' keys
    """
    order = {str(k): int(v) for k, v in order.items()}
    sizes = list(order.keys())
    params = {
        "max_plies": max_plies,
        "max_pieces": max_pieces,
        "tolerance_pct": tolerance_pct,
        "tubular": tubular,
    }

    descs = {
        "min_lays": "Fewest lays \u2014 minimize spreading time and table usage",
        "min_overcut": "Closest to order \u2014 minimize fabric waste from overcut",
        "balanced": "Balanced \u2014 good trade-off between lays and accuracy",
        "max_density": "Max density \u2014 highest pieces per ply for better marker efficiency",
        "single_ratio": "Single marker \u2014 one ratio for all lays, simplest for CAD operator",
    }

    if strategy == "single_ratio":
        plan = _solve_single_ratio(order, max_plies, max_pieces, tolerance_pct, max_lays, tubular=tubular)
    else:
        prefer_map = {
            "min_lays": "min_lays",
            "min_overcut": "min_deviation",
            "balanced": "balanced",
            "max_density": "max_density",
        }
        plan = _solve_two_tier(
            order, max_plies, max_pieces, tolerance_pct, max_lays,
            prefer=prefer_map.get(strategy, "min_lays"),
            tubular=tubular,
        )

    return _build_result(plan, order, sizes, strategy, descs.get(strategy, ""), params)


def optimize_all_strategies(
    order: Dict[str, int],
    max_plies: int,
    max_pieces: int,
    tolerance_pct: float = 3.0,
    max_lays: int = 8,
    tubular: bool = False,
) -> Tuple[List[dict], List[dict]]:
    """
    Run ALL strategies and return a list of plans, each with a different approach.
    Planner can compare and choose.

    Returns: tuple of (results, failed) -- results are unique plans, failed are infeasible/deduped
    """
    strategies = ["min_lays", "min_overcut", "balanced", "max_density", "single_ratio"]
    results = []
    seen_plans = {}  # plan_key -> strategy name that produced it first
    failed = []

    for strategy in strategies:
        result = optimize_lay_plan(order, max_plies, max_pieces, tolerance_pct, max_lays, strategy, tubular=tubular)
        if result["success"]:
            # Deduplicate: check if this plan is identical to one already seen
            plan_key = tuple(
                (tuple(sorted(lay["ratio"].items())), lay["plies"])
                for lay in result["lays"]
            )
            if plan_key not in seen_plans:
                seen_plans[plan_key] = result["strategy"]
                results.append(result)
            else:
                # Mark as duplicate -- record which strategy it matches
                result["deduplicated"] = True
                result["same_as"] = seen_plans[plan_key]
                failed.append(result)
        else:
            failed.append(result)

    return results, failed


# ---------------------------------------------------------------------------
# CLI / Display
# ---------------------------------------------------------------------------

def print_plan(result: dict, compact: bool = False):
    """Pretty-print a single plan result."""
    if not result["success"]:
        print(f"  \u274c {result.get('error', 'No feasible plan')}")
        return

    sizes = list(result["per_size"].keys())
    order = {s: result["per_size"][s]["order"] for s in sizes}
    summary = result["summary"]
    strategy = result.get("strategy", "")
    desc = result.get("strategy_description", "")

    label = f"Strategy: {strategy.upper()}"
    if desc:
        label += f" \u2014 {desc}"

    line = "\u2500" * 90
    print(f"\n{line}")
    print(f"  {label}")
    print(f"{line}")

    if not compact:
        print(f"  Order: {', '.join(f'{s}:{order[s]}' for s in sizes)}")
    print(f"  Lays: {summary['total_lays']} | Markers: {summary['unique_markers']}"
          f" | Avg density: {summary['avg_pieces_per_ply']}/ply"
          f" | Overcut: {summary['overcut']} ({summary['overcut_pct']}%)"
          f" | Undercut: {summary['undercut']} ({summary['undercut_pct']}%)")

    sw = max(5, max(len(s) for s in sizes) + 1)
    hdr = " | ".join(f"{s:>{sw}}" for s in sizes)
    print(f"\n  {'Lay':>4} {'Plies':>6} {'Cut':>7} | {hdr} | Ratio")
    d = "\u2500"
    col_sep = d + "\u2524" + d
    sep = f"  {d*4} {d*6} {d*7}{d}\u2524{d}{col_sep.join(d*sw for _ in sizes)}{d}\u2524{d}{d*30}"
    print(sep)

    for lay in result["lays"]:
        cols = " | ".join(f"{lay['cut_per_size'][s]:>{sw}}" for s in sizes)
        r_str = ":".join(str(lay["ratio"][s]) for s in sizes)
        print(
            f"  {lay['lay_no']:>4} {lay['plies']:>6} {lay['total_pieces']:>7}"
            f" | {cols} | {r_str} ({lay['pieces_per_ply']}/ply)"
        )

    print(sep)
    cols = " | ".join(f"{result['per_size'][s]['cut']:>{sw}}" for s in sizes)
    print(f"  {'CUT':>4} {'':>6} {summary['total_cut']:>7} | {cols} |")
    cols = " | ".join(f"{order[s]:>{sw}}" for s in sizes)
    print(f"  {'ORD':>4} {'':>6} {summary['total_order']:>7} | {cols} |")
    cols = " | ".join(f"{result['per_size'][s]['diff']:>+{sw}}" for s in sizes)
    diff_total = summary["total_cut"] - summary["total_order"]
    print(f"  {'DIFF':>4} {'':>6} {diff_total:>+7} | {cols} |")

    # Flag violations
    for s in sizes:
        ps = result["per_size"][s]
        if ps["pct"] > 3:
            print(f"    \u26d4 {s}: {ps['diff']:+d} ({ps['pct']}%) EXCEEDS \u00b13%")


def print_comparison(results: List[dict], failed: List[dict] = None):
    """Print a comparison table across all strategies."""
    if not results:
        print("\u274c No feasible plans found.")
        if failed:
            for f in failed:
                reason = f.get("error", "Unknown")
                print(f"  \u274c {f['strategy'].upper()}: {reason}")
        return

    sizes = list(results[0]["per_size"].keys())
    order = {s: results[0]["per_size"][s]["order"] for s in sizes}

    total_shown = len(results) + (len(failed) if failed else 0)
    print(f"\n{'='*90}")
    print(f"  LAY PLAN OPTIMIZER \u2014 {total_shown} STRATEGIES")
    print(f"{'='*90}")
    print(f"  Order: {', '.join(f'{s}:{order[s]}' for s in sizes)}")
    print(f"  Total: {sum(order.values()):,} garments")
    tub_str = " | Fabric: TUBULAR (even plies only)" if results[0]['params'].get('tubular') else ""
    print(f"  Max plies: {results[0]['params']['max_plies']}"
          f" | Max pieces/marker: {results[0]['params']['max_pieces']}"
          f" | Tolerance: \u00b1{results[0]['params']['tolerance_pct']}%{tub_str}")

    # Summary comparison table
    print(f"\n  {'#':>2} {'Strategy':<18} {'Lays':>5} {'Markers':>8} {'Density':>8}"
          f" {'Overcut':>8} {'Undercut':>9} {'Total Dev':>10}")
    d = "\u2500"
    print(f"  {d*2} {d*18} {d*5} {d*8} {d*8} {d*8} {d*9} {d*10}")

    idx = 0
    for i, r in enumerate(results, 1):
        s = r["summary"]
        total_dev = s["overcut"] + s["undercut"]
        print(
            f"  {i:>2} {r['strategy']:<18} {s['total_lays']:>5}"
            f" {s['unique_markers']:>8} {s['avg_pieces_per_ply']:>7.1f}/ply"
            f" {s['overcut']:>7} ({s['overcut_pct']}%)"
            f" {s['undercut']:>7} ({s['undercut_pct']}%)"
            f" {total_dev:>10}"
        )
        idx = i

    # Show failed/deduped strategies
    if failed:
        for f in failed:
            idx += 1
            if f.get("deduplicated"):
                same_as = f.get("same_as", "?")
                print(f"  {idx:>2} {f['strategy']:<18}   = same plan as {same_as}")
            else:
                reason = f.get("error", "No feasible plan")
                print(f"  {idx:>2} {f['strategy']:<18}   \u274c {reason}")

    # Print each plan detail
    for r in results:
        print_plan(r, compact=True)

    print(f"\n{'='*90}")


def main():
    parser = argparse.ArgumentParser(
        description="Lay Planning Optimizer v2.1 \u2014 Essdee MRP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Strategies:
  min_lays      Fewest lays (minimize spreading time)
  min_overcut   Closest to order qty (minimize waste)
  balanced      Trade-off between lays and accuracy
  max_density   Highest pieces/ply (better marker efficiency)
  single_ratio  One marker ratio for all lays (simplest for CAD)
  all           Run all strategies and compare (default)

Examples:
  python3 lay_optimizer.py \\
      --order "45:208,50:333,55:229,60:239,65:225,70:225,75:225" \\
      --max-plies 70 --max-pieces 21

  python3 lay_optimizer.py \\
      --order '{"45":208,"50":333}' \\
      --max-plies 70 --max-pieces 21 --strategy min_overcut --json
        """,
    )
    parser.add_argument(
        "--order", required=True,
        help='Size:Qty \u2014 JSON dict or "S:Q,S:Q,..." string',
    )
    parser.add_argument("--max-plies", type=int, required=True, help="Max plies per lay")
    parser.add_argument("--max-pieces", type=int, required=True, help="Max garments per marker")
    parser.add_argument(
        "--tolerance", type=float, default=3.0, help="Allowed \u00b1%% per size (default: 3)"
    )
    parser.add_argument("--max-lays", type=int, default=8, help="Max lays to consider (default: 8)")
    parser.add_argument(
        "--strategy", default="all",
        choices=["min_lays", "min_overcut", "balanced", "max_density", "single_ratio", "all"],
        help="Strategy to use (default: all)",
    )
    parser.add_argument("--tubular", action="store_true",
                        help="Tubular fabric \u2014 force all ply counts to even numbers")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Parse order
    order_str = args.order.strip()
    if order_str.startswith("{"):
        order = json.loads(order_str)
        order = {str(k): int(v) for k, v in order.items()}
    else:
        order = {}
        for part in order_str.split(","):
            s, q = part.strip().split(":", 1)
            order[s.strip()] = int(q.strip())

    if args.strategy == "all":
        results, failed = optimize_all_strategies(
            order, args.max_plies, args.max_pieces, args.tolerance, args.max_lays,
            tubular=args.tubular,
        )
        if args.json:
            print(json.dumps({"plans": results, "failed": failed}, indent=2))
        else:
            print_comparison(results, failed)
    else:
        result = optimize_lay_plan(
            order, args.max_plies, args.max_pieces, args.tolerance, args.max_lays, args.strategy,
            tubular=args.tubular,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_plan(result)


if __name__ == "__main__":
    main()
