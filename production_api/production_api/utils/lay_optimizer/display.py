"""
Display / pretty-print functions for lay optimizer results.
"""

from typing import Dict, List


def print_plan(result: dict, compact: bool = False):
    """Pretty-print a single plan result."""
    if not result["success"]:
        print(f"  ❌ {result.get('error', 'No feasible plan')}")
        return

    sizes = list(result["per_size"].keys())
    order = {s: result["per_size"][s]["order"] for s in sizes}
    summary = result["summary"]
    strategy = result.get("strategy", "")
    desc = result.get("strategy_description", "")

    label = f"Strategy: {strategy.upper()}"
    if desc:
        label += f" — {desc}"

    print(f"\n{'─' * 90}")
    print(f"  {label}")
    print(f"{'─' * 90}")

    if not compact:
        print(f"  Order: {', '.join(f'{s}:{order[s]}' for s in sizes)}")
    print(
        f"  Lays: {summary['total_lays']} | Markers: {summary['unique_markers']}"
        f" | Avg density: {summary['avg_pieces_per_ply']}/ply"
        f" | Overcut: {summary['overcut']} ({summary['overcut_pct']}%)"
        f" | Undercut: {summary['undercut']} ({summary['undercut_pct']}%)"
    )

    sw = max(5, max(len(s) for s in sizes) + 1)
    hdr = " | ".join(f"{s:>{sw}}" for s in sizes)
    print(f"\n  {'Lay':>4} {'Plies':>6} {'Cut':>7} | {hdr} | Ratio")
    sep = f"  {'─' * 4} {'─' * 6} {'─' * 7}─┼─{'─┼─'.join('─' * sw for _ in sizes)}─┼─{'─' * 30}"
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

    for s in sizes:
        ps = result["per_size"][s]
        if ps["pct"] > 3:
            print(f"    ⛔ {s}: {ps['diff']:+d} ({ps['pct']}%) EXCEEDS ±3%")


def print_comparison(results: List[dict], failed: List[dict] = None):
    """Print a comparison table across all strategies."""
    if not results:
        print("❌ No feasible plans found.")
        if failed:
            for f in failed:
                reason = f.get("error", "Unknown")
                print(f"  ❌ {f['strategy'].upper()}: {reason}")
        return

    sizes = list(results[0]["per_size"].keys())
    order = {s: results[0]["per_size"][s]["order"] for s in sizes}

    total_shown = len(results) + (len(failed) if failed else 0)
    print(f"\n{'=' * 90}")
    print(f"  LAY PLAN OPTIMIZER — {total_shown} STRATEGIES")
    print(f"{'=' * 90}")
    print(f"  Order: {', '.join(f'{s}:{order[s]}' for s in sizes)}")
    print(f"  Total: {sum(order.values()):,} garments")
    tub_str = " | Fabric: TUBULAR (even plies only)" if results[0]["params"].get("tubular") else ""
    print(
        f"  Max plies: {results[0]['params']['max_plies']}"
        f" | Max pieces/marker: {results[0]['params']['max_pieces']}"
        f" | Tolerance: ±{results[0]['params']['tolerance_pct']}%{tub_str}"
    )

    print(
        f"\n  {'#':>2} {'Strategy':<18} {'Lays':>5} {'Markers':>8} {'Density':>8}"
        f" {'Overcut':>8} {'Undercut':>9} {'Total Dev':>10}"
    )
    print(f"  {'─' * 2} {'─' * 18} {'─' * 5} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 9} {'─' * 10}")

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

    if failed:
        for f in failed:
            idx += 1
            if f.get("deduplicated"):
                same_as = f.get("same_as", "?")
                print(f"  {idx:>2} {f['strategy']:<18}   = same plan as {same_as}")
            else:
                reason = f.get("error", "No feasible plan")
                print(f"  {idx:>2} {f['strategy']:<18}   ❌ {reason}")

    for r in results:
        print_plan(r, compact=True)

    print(f"\n{'=' * 90}")
