import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime

from production_api.production_api.doctype.finishing_plan.finishing_plan import (
    get_finishing_packing_summary,
    get_finishing_plan_total_cutting,
    get_set_item_parts_count,
)


QUALIFYING_STATUSES = ("Dispatched", "Fully Dispatched")
OVERDUE_AFTER_DAYS = 7
ALLOWED_ROLES = {"Accounts User", "Accounts Manager", "System Manager"}


def _ensure_access():
    if not ALLOWED_ROLES.intersection(frappe.get_roles()):
        frappe.throw(
            _("You are not permitted to view the Audit Pending Finishing Plans dashboard."),
            frappe.PermissionError,
        )


def _version_changes(data):
    if not data:
        return []
    try:
        payload = json.loads(data) if isinstance(data, str) else data
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return payload.get("changed") or [] if isinstance(payload, dict) else []


def _find_status_since(plans, versions):
    """Find the latest Version transition into every plan's current status."""
    current_status = {plan.name: plan.fp_status for plan in plans}
    status_since = {}
    ordered_versions = sorted(
        versions,
        key=lambda row: get_datetime(row.creation),
        reverse=True,
    )
    for version in ordered_versions:
        if version.docname in status_since:
            continue
        wanted = current_status.get(version.docname)
        if not wanted:
            continue
        for change in _version_changes(version.data):
            if len(change) >= 3 and change[0] == "fp_status" and change[2] == wanted:
                status_since[version.docname] = get_datetime(version.creation)
                break
    return status_since


def _build_plan_metrics(
    finishing_plan,
    packing_summary,
    set_item_parts_count=1,
    total_cutting=None,
):
    total_cut = (
        flt(total_cutting)
        if total_cutting is not None
        else sum(flt(row.cutting_qty) for row in finishing_plan.finishing_plan_details)
    )
    sewing_received = sum(
        flt(row.delivered_quantity) for row in finishing_plan.finishing_plan_details
    )

    if packing_summary.dynamic_ratio_packing:
        packed = flt(packing_summary.total_packed)
        dispatched = flt(packing_summary.total_dispatched)
    else:
        multiplier = flt(finishing_plan.pieces_per_box) * max(
            flt(set_item_parts_count), 1
        )
        packed = sum(
            flt(row.quantity) for row in finishing_plan.finishing_plan_grn_details
        ) * multiplier
        dispatched = sum(
            flt(row.dispatched) for row in finishing_plan.finishing_plan_grn_details
        ) * multiplier

    return {
        "total_cut": total_cut,
        "sewing_received": sewing_received,
        "packed": packed,
        "dispatched": dispatched,
    }


def _history_document(log):
    if log.get("source_doctype") == "Finishing Plan Dispatch":
        return log.get("source_name") or log.get("stock_entry") or ""
    return log.get("stock_entry") or log.get("source_name") or ""


def _serialize_history(log, fallback_item=""):
    posting_date = log.get("posting_date")
    return {
        "document": _history_document(log),
        "source_doctype": log.get("source_doctype") or "",
        "source_name": log.get("source_name") or "",
        "stock_entry": log.get("stock_entry") or "",
        "posting_date": str(getdate(posting_date)) if posting_date else "",
        "posting_time": str(log.get("posting_time") or ""),
        "destination": log.get("destination") or "",
        "item_detail": log.get("item_detail") or fallback_item,
        "boxes": flt(log.get("dispatch_boxes")),
        "pieces": flt(log.get("dispatch_pieces")),
        "operator": log.get("operator") or "",
    }


def _build_overdue_rows(plans, status_since, metrics, histories, as_of):
    rows = []
    as_of = get_datetime(as_of)
    for plan in plans:
        since = status_since.get(plan.name)
        if not since:
            continue
        age_days = max((as_of - get_datetime(since)).days, 0)
        if age_days <= OVERDUE_AFTER_DAYS:
            continue

        valid_history = [
            log for log in histories.get(plan.name, []) if not int(log.get("cancelled") or 0)
        ]
        valid_history.sort(
            key=lambda log: (
                str(log.get("posting_date") or ""),
                str(log.get("posting_time") or ""),
                str(log.get("creation") or ""),
            ),
            reverse=True,
        )
        serialized_history = [
            _serialize_history(log, plan.item) for log in valid_history
        ]
        plan_metrics = metrics.get(plan.name) or {}
        rows.append(
            {
                "name": plan.name,
                "lot": plan.lot or "",
                "item": plan.item or "",
                "fp_status": plan.fp_status,
                "status_since": str(getdate(since)),
                "age_days": age_days,
                "total_cut": flt(plan_metrics.get("total_cut")),
                "sewing_received": flt(plan_metrics.get("sewing_received")),
                "packed": flt(plan_metrics.get("packed")),
                "dispatched": flt(plan_metrics.get("dispatched")),
                "latest_dispatch": serialized_history[0]
                if serialized_history
                else None,
                "dispatch_history": serialized_history,
            }
        )

    rows.sort(key=lambda row: (-row["age_days"], row["name"]))
    return rows


def _summarize(rows):
    return {
        "overdue": len(rows),
        "dispatched": sum(row["fp_status"] == "Dispatched" for row in rows),
        "fully_dispatched": sum(
            row["fp_status"] == "Fully Dispatched" for row in rows
        ),
        "oldest_days": max((row["age_days"] for row in rows), default=0),
    }


def _get_plan_metrics(plan_name):
    finishing_plan = frappe.get_doc("Finishing Plan", plan_name)
    return _build_plan_metrics(
        finishing_plan,
        get_finishing_packing_summary(finishing_plan),
        set_item_parts_count=get_set_item_parts_count(finishing_plan),
        total_cutting=get_finishing_plan_total_cutting(finishing_plan),
    )


def _get_dispatch_histories(plan_names):
    histories = defaultdict(list)
    if not plan_names:
        return histories

    logs = frappe.get_all(
        "Finishing Plan Dispatch Log",
        filters={
            "parent": ["in", plan_names],
            "parenttype": "Finishing Plan",
            "parentfield": "finishing_plan_dispatch_logs",
            "cancelled": 0,
        },
        fields=[
            "parent",
            "source_doctype",
            "source_name",
            "stock_entry",
            "posting_date",
            "posting_time",
            "dispatch_boxes",
            "dispatch_pieces",
            "cancelled",
            "creation",
        ],
        order_by="posting_date desc, posting_time desc, creation desc",
        limit_page_length=0,
    )

    stock_entry_names = list({log.stock_entry for log in logs if log.stock_entry})
    stock_entries = {}
    if stock_entry_names:
        stock_entries = {
            row.name: row
            for row in frappe.get_all(
                "Stock Entry",
                filters={"name": ["in", stock_entry_names], "docstatus": 1},
                fields=["name", "transfer_supplier", "to_warehouse", "owner"],
                limit_page_length=0,
            )
        }

    owners = list({row.owner for row in stock_entries.values() if row.owner})
    owner_names = {}
    if owners:
        owner_names = {
            row.name: row.full_name or row.name
            for row in frappe.get_all(
                "User",
                filters={"name": ["in", owners]},
                fields=["name", "full_name"],
                limit_page_length=0,
            )
        }

    for log in logs:
        stock_entry = stock_entries.get(log.stock_entry)
        if stock_entry:
            log.destination = stock_entry.transfer_supplier or stock_entry.to_warehouse or ""
            log.operator = owner_names.get(stock_entry.owner, stock_entry.owner or "")
        histories[log.parent].append(log)
    return histories


@frappe.whitelist()
def get_dashboard_data():
    _ensure_access()
    as_of = now_datetime()
    plans = frappe.get_all(
        "Finishing Plan",
        filters={"fp_status": ["in", QUALIFYING_STATUSES]},
        fields=["name", "lot", "item", "fp_status"],
        limit_page_length=0,
    )
    if not plans:
        return {
            "as_of": str(getdate(as_of)),
            "threshold_days": OVERDUE_AFTER_DAYS,
            "summary": _summarize([]),
            "plans": [],
        }

    plan_names = [plan.name for plan in plans]
    versions = frappe.get_all(
        "Version",
        filters={
            "ref_doctype": "Finishing Plan",
            "docname": ["in", plan_names],
        },
        fields=["docname", "creation", "data"],
        order_by="creation desc",
        limit_page_length=0,
    )
    status_since = _find_status_since(plans, versions)
    overdue_names = [
        plan.name
        for plan in plans
        if plan.name in status_since
        and (as_of - status_since[plan.name]).days > OVERDUE_AFTER_DAYS
    ]
    metrics = {name: _get_plan_metrics(name) for name in overdue_names}
    histories = _get_dispatch_histories(overdue_names)
    rows = _build_overdue_rows(plans, status_since, metrics, histories, as_of)
    return {
        "as_of": str(getdate(as_of)),
        "threshold_days": OVERDUE_AFTER_DAYS,
        "summary": _summarize(rows),
        "plans": rows,
    }


def _as_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = frappe.parse_json(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _build_dynamic_dispatch_rows(batches, finishing_plan, include_unscoped=False):
    rows = []
    for batch in batches or []:
        batch_plan = batch.get("finishing_plan")
        if batch_plan != finishing_plan and not (include_unscoped and not batch_plan):
            continue
        detail = batch.get("colour") or "—"
        pieces_per_box = flt(batch.get("pieces_per_box"))
        boxes = flt(batch.get("box_quantity"))
        for size, pieces in (batch.get("size_pieces") or {}).items():
            rows.append(
                {
                    "size": size or "—",
                    "detail": detail,
                    "pieces_per_box": pieces_per_box,
                    "boxes": boxes,
                    "pieces": flt(pieces),
                }
            )
    return rows


def _get_variant_attributes(item_variants):
    attributes = defaultdict(dict)
    if not item_variants:
        return attributes
    for row in frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": ["in", list(set(item_variants))]},
        fields=["parent", "attribute", "attribute_value"],
        limit_page_length=0,
    ):
        attributes[row.parent][row.attribute] = row.attribute_value
    return attributes


def _build_legacy_dispatch_rows(
    items,
    attributes,
    primary_attribute,
    dependent_attribute,
    pieces_per_box,
    set_item_parts_count=1,
):
    grouped = {}
    for item in items:
        variant = item.get("item_variant") or item.get("item")
        variant_attributes = attributes.get(variant) or {}
        size = variant_attributes.get(primary_attribute) or "—"
        detail = variant_attributes.get(dependent_attribute) or "—"
        boxes = flt(item.get("quantity"))
        pieces = flt(item.get("packing_piece_quantity")) or (
            boxes * flt(pieces_per_box) * max(flt(set_item_parts_count), 1)
        )
        key = (size, detail, flt(pieces_per_box))
        row = grouped.setdefault(
            key,
            {
                "size": size,
                "detail": detail,
                "pieces_per_box": flt(pieces_per_box),
                "boxes": 0.0,
                "pieces": 0.0,
            },
        )
        row["boxes"] += boxes
        row["pieces"] += pieces
    return list(grouped.values())


def _get_stock_entry_meta(stock_entry):
    if not stock_entry:
        return frappe._dict()
    return frappe.db.get_value(
        "Stock Entry",
        {"name": stock_entry, "docstatus": 1},
        [
            "name",
            "posting_date",
            "posting_time",
            "transfer_supplier",
            "to_warehouse",
            "owner",
            "packing_batch_dispatch_json",
        ],
        as_dict=True,
    ) or frappe._dict()


@frappe.whitelist()
def get_dispatch_detail(finishing_plan, source_doctype, source_name, stock_entry):
    _ensure_access()
    log_filters = {
        "parent": finishing_plan,
        "parenttype": "Finishing Plan",
        "parentfield": "finishing_plan_dispatch_logs",
        "source_doctype": source_doctype,
        "source_name": source_name,
        "stock_entry": stock_entry,
        "cancelled": 0,
    }
    if not frappe.db.exists("Finishing Plan Dispatch Log", log_filters):
        frappe.throw(
            _("This dispatch does not belong to the selected Finishing Plan."),
            frappe.PermissionError,
        )

    log = frappe.db.get_value(
        "Finishing Plan Dispatch Log",
        log_filters,
        [
            "posting_date",
            "posting_time",
            "dispatch_boxes",
            "dispatch_pieces",
        ],
        as_dict=True,
    )
    finishing_doc = frappe.get_doc("Finishing Plan", finishing_plan)
    stock_meta = _get_stock_entry_meta(stock_entry)
    batches = _as_json_list(stock_meta.get("packing_batch_dispatch_json"))
    if not batches and source_doctype == "Finishing Plan Dispatch":
        batches = _as_json_list(
            frappe.db.get_value(
                "Finishing Plan Dispatch", source_name, "packing_batch_dispatch_json"
            )
        )
    rows = _build_dynamic_dispatch_rows(
        batches,
        finishing_plan,
        include_unscoped=source_doctype == "Finishing Plan",
    )

    if not rows:
        if source_doctype == "Finishing Plan Dispatch":
            items = frappe.get_all(
                "Finishing Plan Dispatch Item",
                filters={"parent": source_name, "against_id": finishing_plan},
                fields=[
                    "item_variant",
                    "quantity",
                    "packing_piece_quantity",
                ],
                limit_page_length=0,
            )
        else:
            items = [
                frappe._dict(
                    item_variant=row.item,
                    quantity=row.qty,
                    packing_piece_quantity=0,
                )
                for row in frappe.get_all(
                    "Stock Entry Detail",
                    filters={"parent": stock_entry},
                    fields=["item", "qty"],
                    limit_page_length=0,
                )
            ]

        ipd = finishing_doc.production_detail or frappe.db.get_value(
            "Lot", finishing_doc.lot, "production_detail"
        )
        ipd_attributes = frappe.db.get_value(
            "Item Production Detail",
            ipd,
            ["primary_item_attribute", "dependent_attribute"],
            as_dict=True,
        ) or frappe._dict()
        variants = [row.get("item_variant") for row in items if row.get("item_variant")]
        rows = _build_legacy_dispatch_rows(
            items,
            _get_variant_attributes(variants),
            ipd_attributes.get("primary_item_attribute"),
            ipd_attributes.get("dependent_attribute"),
            finishing_doc.pieces_per_box,
            get_set_item_parts_count(finishing_doc),
        )

    owner = stock_meta.get("owner") or ""
    operator = frappe.db.get_value("User", owner, "full_name") if owner else ""
    return {
        "document": source_name
        if source_doctype == "Finishing Plan Dispatch"
        else stock_entry,
        "finishing_plan": finishing_plan,
        "posting_date": str(getdate(log.posting_date)) if log.posting_date else "",
        "destination": stock_meta.get("transfer_supplier")
        or stock_meta.get("to_warehouse")
        or "",
        "item_detail": finishing_doc.item or "",
        "operator": operator or owner,
        "total_dispatched": flt(log.dispatch_pieces),
        "rows": rows,
        "totals": {
            "boxes": flt(log.dispatch_boxes),
            "pieces": flt(log.dispatch_pieces),
        },
    }
