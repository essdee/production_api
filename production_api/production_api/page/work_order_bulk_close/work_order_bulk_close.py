import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = [value]
    if not isinstance(value, (list, tuple, set)):
        value = [value]

    result = []
    for entry in value:
        entry = cstr(entry).strip()
        if entry and entry not in result:
            result.append(entry)
    return result


@frappe.whitelist()
def get_open_work_orders(
    supplier, lot=None, item=None, wo_from_date=None, wo_to_date=None
):
    supplier = (supplier or "").strip()
    if not supplier:
        frappe.throw(_("Supplier is required."))

    if not frappe.db.exists("Supplier", supplier):
        frappe.throw(_("Supplier {0} does not exist.").format(frappe.bold(supplier)))

    filters = {
        "supplier": supplier,
        "docstatus": 1,
        "open_status": "Open",
    }

    lots = _as_list(lot)
    items = _as_list(item)
    if lots:
        filters["lot"] = ["in", lots]
    if items:
        filters["item"] = ["in", items]

    from_date = getdate(wo_from_date) if wo_from_date else None
    to_date = getdate(wo_to_date) if wo_to_date else None
    if from_date and to_date and from_date > to_date:
        frappe.throw(_("WO From Date cannot be after WO To Date."))

    if from_date and to_date:
        filters["wo_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["wo_date"] = [">=", from_date]
    elif to_date:
        filters["wo_date"] = ["<=", to_date]

    work_orders = frappe.get_list(
        "Work Order",
        filters=filters,
        fields=[
            "name",
            "wo_date",
            "item",
            "lot",
            "process_name",
            "production_detail",
            "total_no_of_pieces_delivered as total_delivered",
            "total_no_of_pieces_received as total_received",
        ],
        order_by="modified desc, name desc",
        limit_page_length=0,
    )

    for work_order in work_orders:
        work_order.total_delivered = flt(work_order.total_delivered)
        work_order.total_received = flt(work_order.total_received)
        work_order.difference = flt(
            work_order.total_delivered - work_order.total_received
        )

    return work_orders


@frappe.whitelist()
def close_work_orders(
    work_orders, close_reason=None, close_other_reason=None, close_remarks=None
):
    from production_api.production_api.doctype.work_order.work_order import (
        update_stock,
    )

    work_order_names = _as_list(work_orders)
    if not work_order_names:
        frappe.throw(_("Select at least one Work Order to close."))

    # Validate and lock every target before updating the first one. The request
    # remains atomic, so a later close failure rolls back every earlier close.
    for work_order in work_order_names:
        doc = frappe.get_doc("Work Order", work_order, for_update=True)
        doc.check_permission("write")
        if doc.docstatus != 1 or doc.open_status != "Open":
            frappe.throw(
                _("Work Order {0} is no longer open.").format(
                    frappe.bold(work_order)
                )
            )

    results = []
    previous_alert_setting = frappe.flags.get("suppress_work_order_close_alert")
    frappe.flags.suppress_work_order_close_alert = True
    try:
        for work_order in work_order_names:
            result = update_stock(
                work_order,
                close_reason=close_reason,
                close_other_reason=close_other_reason,
                close_remarks=close_remarks,
            )
            results.append(
                {
                    "work_order": work_order,
                    "open_status": result.get("open_status"),
                }
            )
    finally:
        frappe.flags.suppress_work_order_close_alert = previous_alert_setting

    return {"results": results}


@frappe.whitelist()
def get_work_order_close_details(work_order):
    from production_api.production_api.doctype.work_order.work_order import (
        fetch_summary_details,
        get_wo_recut_details,
    )

    work_order_doc = frappe.get_doc("Work Order", work_order)
    work_order_doc.check_permission("read")

    if work_order_doc.docstatus != 1 or work_order_doc.open_status != "Open":
        frappe.throw(
            _("Work Order {0} is no longer open.").format(frappe.bold(work_order))
        )

    if work_order_doc.work_order_calculated_items:
        summary = fetch_summary_details(
            work_order_doc.name, work_order_doc.production_detail
        )
    else:
        summary = {
            "item_detail": [],
            "deliverables": [],
            "work_order_docstatus": work_order_doc.docstatus,
        }

    debits = []
    if frappe.has_permission("Essdee Debit", "read"):
        debits = frappe.get_list(
            "Essdee Debit",
            filters={
                "against": "Work Order",
                "against_id": work_order_doc.name,
                "docstatus": 1,
            },
            fields=[
                "name",
                "debit_type",
                "debit_no",
                "debit_value",
                "inspection",
                "status",
                "on_close",
            ],
            order_by="creation asc",
            limit_page_length=0,
        )

    return {
        "summary": summary,
        "recut_details": get_wo_recut_details(work_order_doc.name),
        "debits": debits,
    }
