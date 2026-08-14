import json

import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from frappe.utils import cstr, flt, getdate, nowtime, today


def _parse_json(value):
    if isinstance(value, str):
        return json.loads(value or "{}")
    return {} if value is None else value


def _get_closed_sewing_work_order(work_order, supplier=None, for_update=False):
    work_order = cstr(work_order).strip()
    supplier = cstr(supplier).strip()
    if not work_order:
        frappe.throw(_("Work Order is required."))

    if for_update:
        doc = frappe.get_doc("Work Order", work_order, for_update=True)
    else:
        doc = frappe.get_doc("Work Order", work_order)
    doc.check_permission("read")

    if doc.docstatus != 1 or doc.open_status != "Close":
        frappe.throw(
            _("Work Order {0} is not a submitted, closed Work Order.").format(
                frappe.bold(work_order)
            )
        )
    if supplier and doc.supplier != supplier:
        frappe.throw(
            _("Work Order {0} does not belong to unit {1}.").format(
                frappe.bold(work_order), frappe.bold(supplier)
            )
        )
    if not frappe.db.exists("Sewing Plan", {"work_order": doc.name}):
        frappe.throw(
            _("Work Order {0} is not linked to Sewing Details.").format(
                frappe.bold(work_order)
            )
        )
    return doc


def _empty_item_selections(doc):
    return {
        row.name: {"types": {}, "secondary_qty_json": {}}
        for row in doc.receivables
    }


def _get_received_types(value, item_variant):
    value = _parse_json(value)
    if not isinstance(value, dict):
        frappe.throw(
            _("Invalid received-type quantities for item {0}.").format(
                frappe.bold(item_variant)
            )
        )

    received_types = {}
    for received_type, raw_quantity in value.items():
        received_type = cstr(received_type).strip()
        quantity = flt(raw_quantity)
        if quantity < 0:
            frappe.throw(_("Received Quantity cannot be negative."))
        if not quantity:
            continue
        if not received_type or not frappe.db.exists("GRN Item Type", received_type):
            frappe.throw(
                _("Select a valid Received Type for item {0}.").format(
                    frappe.bold(item_variant)
                )
            )
        received_types[received_type] = quantity
    return received_types


def _extract_item_selections(doc, item_details):
    item_details = _parse_json(item_details)
    if not isinstance(item_details, list):
        frappe.throw(_("Invalid GRN item details."))

    receivables = {row.name: row for row in doc.receivables}
    selections = _empty_item_selections(doc)
    seen_rows = set()

    for group in item_details:
        group = _parse_json(group)
        for item in group.get("items") or []:
            item = _parse_json(item)
            item_values = _parse_json(item.get("values"))
            if not isinstance(item_values, dict):
                frappe.throw(_("Invalid GRN item values."))

            for value in item_values.values():
                value = _parse_json(value)
                ref_docname = cstr(value.get("ref_docname")).strip()
                if not ref_docname:
                    continue
                if ref_docname in seen_rows:
                    frappe.throw(
                        _("Each Work Order receivable row can be entered only once.")
                    )
                seen_rows.add(ref_docname)

                receivable = receivables.get(ref_docname)
                if not receivable:
                    frappe.throw(
                        _("A selected item does not belong to this Work Order.")
                    )

                received_types = _get_received_types(
                    value.get("types"), receivable.item_variant
                )
                total_received = sum(received_types.values())
                entered_received = flt(value.get("received"))
                if entered_received < 0:
                    frappe.throw(_("Received Quantity cannot be negative."))
                if entered_received and abs(entered_received - total_received) > 0.001:
                    frappe.throw(
                        _("Received-type quantities do not match the total for item {0}.").format(
                            frappe.bold(receivable.item_variant)
                        )
                    )

                raw_secondary = _parse_json(value.get("secondary_qty_json"))
                if not isinstance(raw_secondary, dict):
                    frappe.throw(
                        _("Invalid secondary quantities for item {0}.").format(
                            frappe.bold(receivable.item_variant)
                        )
                    )
                secondary_quantities = {}
                for received_type, raw_quantity in raw_secondary.items():
                    received_type = cstr(received_type).strip()
                    quantity = flt(raw_quantity)
                    if quantity < 0:
                        frappe.throw(_("Secondary Quantity cannot be negative."))
                    if not quantity:
                        continue
                    if received_type not in received_types:
                        frappe.throw(
                            _("Secondary Quantity requires a matching Received Type for item {0}.").format(
                                frappe.bold(receivable.item_variant)
                            )
                        )
                    if not receivable.secondary_uom:
                        frappe.throw(
                            _("Item {0} does not have a Secondary UOM.").format(
                                frappe.bold(receivable.item_variant)
                            )
                        )
                    secondary_quantities[received_type] = quantity

                selections[ref_docname] = {
                    "types": received_types,
                    "secondary_qty_json": secondary_quantities,
                }

    return selections


def _make_grn_item_details(doc, selections=None):
    from production_api.production_api.doctype.goods_received_note.goods_received_note import (
        fetch_grn_item_details,
    )

    selections = selections or _empty_item_selections(doc)
    items = []
    for row in doc.receivables:
        selected = selections.get(row.name) or {}
        received_types = selected.get("types") or {}
        secondary_qty_json = selected.get("secondary_qty_json") or {}
        items.append(
            frappe.get_doc(
                {
                    "doctype": "Goods Received Note Item",
                    "item_variant": row.item_variant,
                    "lot": row.lot or doc.lot,
                    "quantity": sum(received_types.values()),
                    "secondary_qty": sum(secondary_qty_json.values()),
                    "uom": row.uom,
                    "secondary_uom": row.secondary_uom,
                    "rate": flt(row.cost),
                    "tax": None,
                    "table_index": row.table_index,
                    "row_index": row.row_index,
                    "comments": row.comments,
                    "ref_doctype": "Work Order Receivables",
                    "ref_docname": row.name,
                    "received_types": received_types,
                    "secondary_qty_json": secondary_qty_json,
                    "set_combination": row.set_combination or {},
                }
            )
        )

    if not items:
        return []
    return fetch_grn_item_details(
        items, doc.production_detail, doc.lot, docstatus=0
    )


def _make_grn_rows(doc, item_details):
    from production_api.production_api.doctype.goods_received_note.goods_received_note import (
        save_grn_item_details,
    )

    selections = _extract_item_selections(doc, item_details)
    trusted_item_details = _make_grn_item_details(doc, selections)
    calculated_rows, _total_rate, _total_qty = save_grn_item_details(
        trusted_item_details, doc.process_name
    )
    receivables = {row.name: row for row in doc.receivables}
    normalized_items = []

    for calculated in calculated_rows:
        quantity = flt(calculated.get("quantity"))
        if quantity <= 0:
            continue

        receivable = receivables.get(calculated.get("ref_docname"))
        if not receivable:
            frappe.throw(_("A selected item does not belong to this Work Order."))
        if flt(receivable.pending_quantity) <= 0:
            frappe.throw(
                _("There is no pending quantity for item {0}.").format(
                    frappe.bold(receivable.item_variant)
                )
            )

        selected = selections[receivable.name]
        received_types = selected["types"]
        if abs(sum(received_types.values()) - quantity) > 0.001:
            frappe.throw(
                _("Received-type quantities do not match item {0}.").format(
                    frappe.bold(receivable.item_variant)
                )
            )

        secondary_qty_json = selected["secondary_qty_json"]
        normalized_items.append(
            {
                "item_variant": receivable.item_variant,
                "lot": receivable.lot or doc.lot,
                "quantity": quantity,
                "secondary_qty": sum(secondary_qty_json.values()),
                "uom": receivable.uom,
                "secondary_uom": receivable.secondary_uom,
                "rate": flt(receivable.cost),
                "table_index": calculated.get("table_index"),
                "row_index": calculated.get("row_index"),
                "comments": receivable.comments,
                "ref_doctype": "Work Order Receivables",
                "ref_docname": receivable.name,
                "received_types": received_types,
                "secondary_qty_json": secondary_qty_json,
                "set_combination": receivable.set_combination or {},
            }
        )

    if not normalized_items:
        frappe.throw(_("Enter a received quantity for at least one item."))
    return normalized_items


def _set_combination_key(value):
    value = _parse_json(value)
    if not isinstance(value, dict):
        value = {}
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_closed_sewing_work_orders(
    doctype, txt, searchfield, start, page_len, filters
):
    filters = _parse_json(filters)
    supplier = cstr(filters.get("supplier")).strip()
    if not supplier:
        return []

    search_text = f"%{cstr(txt).strip()}%"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT
            `tabWork Order`.name,
            `tabWork Order`.lot,
            `tabWork Order`.item,
            `tabWork Order`.process_name
        FROM `tabWork Order`
        INNER JOIN `tabSewing Plan`
            ON `tabSewing Plan`.work_order = `tabWork Order`.name
        WHERE `tabWork Order`.docstatus = 1
          AND `tabWork Order`.open_status = 'Close'
          AND `tabWork Order`.supplier = %(supplier)s
          AND (
              `tabWork Order`.name LIKE %(txt)s
              OR `tabWork Order`.lot LIKE %(txt)s
              OR `tabWork Order`.item LIKE %(txt)s
              OR `tabWork Order`.process_name LIKE %(txt)s
          )
          {get_match_cond("Work Order")}
        ORDER BY `tabWork Order`.modified DESC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "supplier": supplier,
            "txt": search_text,
            "start": int(start or 0),
            "page_len": int(page_len or 20),
        },
        as_list=True,
    )


@frappe.whitelist()
def get_closed_work_order_grn_details(work_order, supplier):
    doc = _get_closed_sewing_work_order(work_order, supplier)

    return {
        "work_order": doc.name,
        "item": doc.item,
        "lot": doc.lot,
        "process": doc.process_name,
        "supplier": doc.supplier,
        "supplier_address": doc.supplier_address,
        "delivery_location": doc.delivery_location,
        "delivery_address": doc.delivery_address,
        "has_pending_items": any(
            flt(row.pending_quantity) > 0 for row in doc.receivables
        ),
        "item_details": _make_grn_item_details(doc),
    }


@frappe.whitelist()
def get_closed_work_order_calculation_items(work_order, supplier):
    from production_api.production_api.doctype.delivery_challan.delivery_challan import (
        get_calculated_items,
    )

    doc = _get_closed_sewing_work_order(work_order, supplier)
    return get_calculated_items("Sewing Details", doc.name)


@frappe.whitelist()
def calculate_closed_work_order_receivables(
    work_order, supplier, calculation_items, item_details, received_type
):
    from production_api.production_api.doctype.work_order.work_order import (
        get_deliverable_receivable,
    )

    doc = _get_closed_sewing_work_order(work_order, supplier)
    received_type = cstr(received_type).strip()
    if not received_type or not frappe.db.exists("GRN Item Type", received_type):
        frappe.throw(_("Select a valid Received Type."))

    calculation_items = _parse_json(calculation_items)
    if not isinstance(calculation_items, list):
        frappe.throw(_("Invalid Work Order calculation items."))

    selections = _extract_item_selections(doc, item_details)
    calculated_receivables = get_deliverable_receivable(
        calculation_items, doc.name, receivable=True
    )
    default_received_type = frappe.db.get_single_value(
        "Stock Settings", "default_received_type"
    )
    if not default_received_type:
        frappe.throw(_("Set Default Received Type in Stock Settings."))

    receivable_map = {}
    for row in doc.receivables:
        key = (row.item_variant, _set_combination_key(row.set_combination))
        receivable_map.setdefault(key, row)

    for calculated in calculated_receivables:
        key = (
            calculated.get("item_variant"),
            _set_combination_key(calculated.get("set_combination")),
        )
        receivable = receivable_map.get(key)
        if not receivable:
            continue

        quantity = flt(calculated.get("qty"))
        if quantity < 0:
            frappe.throw(_("Calculated Received Quantity cannot be negative."))

        if calculated.get("is_accessory"):
            selected_type = default_received_type
            if quantity:
                current_quantity = flt(
                    selections[receivable.name]["types"].get(selected_type)
                )
                selections[receivable.name]["types"][selected_type] = (
                    current_quantity + quantity
                )
                selections[receivable.name]["secondary_qty_json"].setdefault(
                    selected_type, 0
                )
        else:
            selected_type = received_type
            if quantity:
                selections[receivable.name]["types"][selected_type] = quantity
                selections[receivable.name]["secondary_qty_json"].setdefault(
                    selected_type, 0
                )
            else:
                selections[receivable.name]["types"].pop(selected_type, None)
                selections[receivable.name]["secondary_qty_json"].pop(
                    selected_type, None
                )

    return _make_grn_item_details(doc, selections)


@frappe.whitelist()
def create_closed_work_order_grn(work_order, supplier, values, item_details):
    if not frappe.has_permission("Goods Received Note", ptype="create"):
        frappe.throw(_("You do not have permission to create a Goods Received Note."))
    if not frappe.has_permission("Goods Received Note", ptype="submit"):
        frappe.throw(_("You do not have permission to submit a Goods Received Note."))

    # Lock the Work Order until this request commits so two simultaneous page
    # submissions cannot both consume the same pending receivable quantity.
    doc = _get_closed_sewing_work_order(work_order, supplier, for_update=True)
    values = _parse_json(values)
    normalized_items = _make_grn_rows(doc, item_details)

    posting_date = getdate(values.get("posting_date") or today())
    delivery_date = getdate(values.get("delivery_date") or posting_date)
    if delivery_date > posting_date:
        frappe.throw(_("Delivery Date cannot be after Posting Date."))

    supplier_document_no = cstr(values.get("supplier_document_no")).strip()
    vehicle_no = cstr(values.get("vehicle_no")).strip()
    if not supplier_document_no:
        frappe.throw(_("Supplier Document Number is required."))
    if not vehicle_no:
        frappe.throw(_("Vehicle Number is required."))

    grn = frappe.new_doc("Goods Received Note")
    grn.update(
        {
            "naming_series": "GRN-",
            "against": "Work Order",
            "against_id": doc.name,
            "supplier": doc.supplier,
            "supplier_address": doc.supplier_address,
            "delivery_location": doc.delivery_location,
            "delivery_address": doc.delivery_address,
            "delivery_date": delivery_date,
            "posting_date": posting_date,
            "posting_time": values.get("posting_time") or nowtime(),
            "supplier_document_no": supplier_document_no,
            "supplier_document_date": values.get("supplier_document_date") or delivery_date,
            "vehicle_no": vehicle_no,
            "dc_no": cstr(values.get("dc_no")).strip(),
            "comments": cstr(values.get("comments")).strip(),
            "lot": doc.lot,
            "process_name": doc.process_name,
            "is_internal_unit": doc.is_internal_unit,
            "is_rework": doc.is_rework,
            "includes_packing": doc.includes_packing,
            "from_closed_wo_sewing_details": 1,
            "items": normalized_items,
            "grn_deliverables": [],
        }
    )
    grn.flags.allow_closed_wo_sewing_details_grn = True
    grn.insert()
    grn.submit()

    return {"name": grn.name, "docstatus": grn.docstatus}
