"""
Backfill valuation for Work Order GRN receipts (scope: Work Order against GRN ONLY).

WHY
---
Before the fix in `goods_received_note.py`, a Work Order GRN valued its received
items at `deliverables_avg (=0, stale)`, so every received panel landed in the Stock
Ledger at valuation_rate = 0. The correct value (matching the fixed
`update_wo_stock_ledger` / `get_sl_entries`) is:

        rate = deliverable_average + receivable_cost (GRN line rate)

This one-off backfill recomputes exactly that for the WO-GRN *receipt* SLEs and
reposts each GRN so FIFO recomputes valuation_rate / stock_value and carries the
correction forward to same-key downstream entries.

SCOPE (explicit user decision)
------------------------------
- ONLY `against = "Work Order"`, non-return, submitted GRNs.
- We DO NOT touch Stock Entry / Delivery Challan transfer SLEs. Those snapshot their
  source valuation at submit time, so a transferred-then-consumed panel may still be
  read at its (uncorrected) transfer valuation by a downstream process's average.
  That is an accepted limitation of the "Work Order GRN only" scope.

DESIGN
------
- GRNs are processed in posting order (cut -> fuse -> stitch -> ... -> pack) so that
  when a downstream process computes its deliverable average, the upstream receipts it
  consumes have already been corrected and reposted.
- `avg` is taken from the live helper `GoodsReceivedNote.get_wo_deliverable_avg_rate`
  (single source of truth with the runtime code).
- `receivable_cost` is the GRN line rate (the WO Receivable's process cost).
- No last-SLE term: each receipt is valued purely at deliverable_average + process cost.
- After updating a GRN's receipt rates we repost each affected
  (item, warehouse, lot, received_type) key synchronously via `update_entries_after`.

SAFETY
------
- `dry_run=True` by default: computes and reports, writes NOTHING and reposts NOTHING.
- Take a fresh DB backup and run in a maintenance window before `dry_run=False`.
- Idempotent: re-running recomputes from the (now correct) ledger; deltas converge to 0.

HOW TO RUN (after review + backup)
----------------------------------
Dry run (report only):
    bench --site <site> execute \
        production_api.patches.v1_0.backfill_wo_grn_valuation.run \
        --kwargs "{'from_date': '2026-03-04', 'dry_run': True}"

Single lot first (recommended verification):
    ... --kwargs "{'lot': 'JB2627-001', 'dry_run': True}"

Real run:
    ... --kwargs "{'from_date': '2026-01-01', 'dry_run': False}"
"""

import frappe
from frappe.utils import flt

from production_api.production_api.doctype.delivery_challan.delivery_challan import (
    get_variant_stock_details,
)
from production_api.mrp_stock.stock_ledger import update_entries_after

# Default window = "past 3 months" anchor agreed with the user.
DEFAULT_FROM_DATE = "2026-01-01"
RATE_TOLERANCE = 1e-6  # ignore rounding-noise differences


def execute():
    """Patch entry point — runs the real backfill on `bench migrate`.

    Recomputes Work Order GRN receipt valuations from DEFAULT_FROM_DATE (past 3 months)
    and reposts the affected stock-ledger keys, chronologically. Expect a long migrate
    while reposting runs. Runs once per Patch Log entry — bump the patches.txt suffix
    (#1, #2, ...) to force a re-run.

    Manual dry-run anytime (writes nothing):
        bench --site <site> execute
            production_api.patches.v1_0.backfill_wo_grn_valuation.run
            --kwargs "{'from_date': '%s', 'dry_run': True}"
    """ % DEFAULT_FROM_DATE
    run(from_date=DEFAULT_FROM_DATE, dry_run=False)


def run(from_date=None, to_date=None, lot=None, dry_run=True, limit=None, commit_every=25, verbose=True):
    """Recompute and (optionally) repost Work Order GRN receipt valuations.

    Args:
        from_date / to_date: posting_date window (inclusive). Defaults from_date = 2026-03-04.
        lot: restrict to a single Lot (use this to verify on one production chain first).
        dry_run: when True (default) nothing is written or reposted.
        limit: cap number of GRNs (for a quick sample run).
        commit_every: commit + progress print cadence (real run only).
    """
    from_date = from_date or DEFAULT_FROM_DATE
    grn_names = _get_target_grns(from_date, to_date, lot, limit)
    res = get_variant_stock_details()  # {variant: is_stock_item}

    stats = frappe._dict(
        grns=len(grn_names), grns_changed=0, sles_changed=0,
        keys_reposted=0, value_delta=0.0, failed=0,
    )
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"[{mode}] WO-GRN valuation backfill: {stats.grns} GRNs from {from_date} to {to_date or 'now'}"
          + (f" (lot={lot})" if lot else ""))

    for index, grn_name in enumerate(grn_names, start=1):
        try:
            changed_sles, delta, repost_keys = _process_grn(grn_name, res, dry_run, verbose)
        except Exception as exc:  # one bad GRN must not abort the whole backfill
            stats.failed += 1
            if not dry_run:
                frappe.db.rollback()
            print(f"[{index}/{stats.grns}] FAILED {grn_name}: {exc}")
            continue

        if changed_sles:
            stats.grns_changed += 1
            stats.sles_changed += changed_sles
            stats.value_delta += delta

        if not dry_run and repost_keys:
            for key in repost_keys:
                _repost_key(key)
            stats.keys_reposted += len(repost_keys)

        if not dry_run and index % commit_every == 0:
            frappe.db.commit()
            print(f"  committed {index}/{stats.grns} GRNs")

    if not dry_run:
        frappe.db.commit()

    print(
        f"[{mode}] done: grns_changed={stats.grns_changed}, sles_changed={stats.sles_changed}, "
        f"keys_reposted={stats.keys_reposted}, value_delta={round(stats.value_delta, 2)}, failed={stats.failed}"
    )

    # Silent-success guard: a real (migrate) run that failed on EVERY GRN is a systemic
    # error (e.g. a bad formula), not tolerable bad-data rows. Raise so `bench migrate`
    # aborts and the Patch Log does NOT record this patch as applied — otherwise it would
    # be marked done having changed nothing, and a patches.txt suffix bump would be needed
    # to retry. Individual GRN failures are still tolerated (see _process_grn loop).
    if not dry_run and stats.grns and stats.failed == stats.grns:
        frappe.throw(
            f"WO-GRN valuation backfill aborted: all {stats.grns} GRNs failed "
            f"(systemic error, not bad data). Patch NOT marked applied — fix and re-run."
        )

    return stats


def _get_target_grns(from_date, to_date, lot, limit):
    """Submitted, non-return Work Order GRNs in posting order (chronological replay)."""
    filters = {
        "against": "Work Order",
        "is_return": 0,
        "docstatus": 1,
        "posting_date": [">=", from_date],
    }
    if to_date:
        filters["posting_date"] = ["between", [from_date, to_date]]
    if lot:
        filters["lot"] = lot
    return frappe.get_all(
        "Goods Received Note",
        filters=filters,
        order_by="posting_date asc, posting_time asc, creation asc",
        pluck="name",
        limit=limit,
    )


def _process_grn(grn_name, res, dry_run, verbose):
    """Recompute receipt SLE rates for one GRN. Returns (changed_count, value_delta, repost_keys)."""
    doc = frappe.get_doc("Goods Received Note", grn_name)

    # avg = deliverable (consumed material) value per received unit — live helper, single source of truth.
    avg = flt(doc.get_wo_deliverable_avg_rate(res))
    line_by_name = {line.name: line for line in doc.items}  # GRN Item row -> receivable cost

    receipt_sles = frappe.get_all(
        "Stock Ledger Entry",
        filters={"voucher_type": "Goods Received Note", "voucher_no": grn_name, "is_cancelled": 0},
        fields=["name", "item", "warehouse", "lot", "received_type", "uom", "qty",
                "rate", "valuation_rate", "voucher_detail_no"],
    )

    changed = 0
    value_delta = 0.0
    repost_keys = {}  # dedupe (item, warehouse, lot, received_type)
    samples = []
    for sle in receipt_sles:
        if flt(sle.qty) <= 0:           # only incoming receipts
            continue
        if not res.get(sle.item):       # non-stock item -> no valuation
            continue

        line = line_by_name.get(sle.voucher_detail_no)
        receivable_cost = flt(line.rate) if line else 0.0
        # Mirror the live runtime formula in update_wo_stock_ledger:
        #   valuation_rate = deliverable_average + receivable/process cost. No last-SLE term.
        new_rate = avg + receivable_cost

        if abs(new_rate - flt(sle.rate)) <= RATE_TOLERANCE:
            continue

        changed += 1
        value_delta += (new_rate - flt(sle.rate)) * flt(sle.qty)
        repost_keys[(sle.item, sle.warehouse, sle.lot, sle.received_type)] = True
        if len(samples) < 3:
            samples.append(f"{sle.item[:34]} {flt(sle.rate)}->{round(new_rate, 4)}")

        if not dry_run:
            frappe.db.set_value("Stock Ledger Entry", sle.name, "rate", new_rate, update_modified=False)

    if changed and verbose:
        print(f"  {grn_name} [{doc.process_name}] avg={round(avg, 4)} "
              f"changed={changed} | " + "; ".join(samples))

    # repost from the earliest receipt point of each affected key
    keys = [
        frappe._dict(item=k[0], warehouse=k[1], lot=k[2], received_type=k[3],
                     posting_date=doc.posting_date, posting_time=doc.posting_time)
        for k in repost_keys
    ]
    return changed, value_delta, keys


def _repost_key(key):
    """Synchronously rebuild one (item, warehouse, lot, received_type) timeline forward
    from the GRN posting point, so FIFO recomputes valuation_rate / stock_value and the
    correction carries to same-key downstream entries."""
    update_entries_after({
        "item": key.item,
        "warehouse": key.warehouse,
        "lot": key.lot,
        "received_type": key.received_type,
        "posting_date": key.posting_date,
        "posting_time": key.posting_time,
    })
