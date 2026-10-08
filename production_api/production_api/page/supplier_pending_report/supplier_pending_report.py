"""Supplier Pending Report backend."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt

from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
	get_ipd_primary_values,
)
from production_api.utils import (
	get_variant_attr_details,
	max_date,
	min_date,
	update_if_string_instance,
)


@frappe.whitelist()
def get_supplier_pending_report(supplier, process):
	if not supplier:
		frappe.throw(_("Select a Supplier"))
	if not process:
		frappe.throw(_("Select a Process"))

	supplier_name = frappe.get_cached_value("Supplier", supplier, "supplier_name") or supplier
	process_names = _resolve_process_names(process)
	work_orders = _get_supplier_work_orders(supplier, process_names)
	response = {
		"supplier": supplier,
		"supplier_name": supplier_name,
		"process": process,
		"items": [],
	}
	if not work_orders:
		return response

	work_order_names = tuple(row["name"] for row in work_orders)
	calculated_items = frappe.get_all(
		"Work Order Calculated Item",
		filters={"parent": ["in", work_order_names]},
		fields=[
			"parent",
			"item_variant",
			"set_combination",
			"delivered_quantity",
			"received_qty",
		],
	)
	lot_names = tuple(sorted({row.get("lot") for row in work_orders if row.get("lot")}))
	variant_names = tuple(
		sorted({row.get("item_variant") for row in calculated_items if row.get("item_variant")})
	)
	lot_contexts = _load_lot_contexts(lot_names)
	variant_attributes = _load_variant_attributes(variant_names)
	response["items"] = _build_supplier_pending_items(
		work_orders,
		calculated_items,
		lot_contexts,
		variant_attributes,
	)
	return response


def _resolve_process_names(process):
	processes = frappe.db.sql(
		"""
			SELECT parent
			FROM `tabProcess Details`
			WHERE process_name = %(process)s OR parent = %(process)s
		""",
		{"process": process},
		as_dict=True,
	)
	return tuple(sorted({process, *(row["parent"] for row in processes)}))


def _get_supplier_work_orders(supplier, process_names):
	return frappe.get_all(
		"Work Order",
		filters={
			"supplier": supplier,
			"docstatus": 1,
			"is_rework": 0,
			"process_name": ["in", process_names],
		},
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"item",
			"lot",
			"process_name",
			"first_dc_date",
			"last_dc_date",
			"first_grn_date",
			"last_grn_date",
		],
	)


def _load_lot_contexts(lot_names):
	if not lot_names:
		return {}

	lots = frappe.get_all(
		"Lot",
		filters={"name": ["in", lot_names]},
		fields=["name", "production_detail"],
	)
	ipd_names = tuple(sorted({row.get("production_detail") for row in lots if row.get("production_detail")}))
	if not ipd_names:
		return {}
	ipd_rows = frappe.get_all(
		"Item Production Detail",
		filters={"name": ["in", ipd_names]},
		fields=[
			"name",
			"is_set_item",
			"packing_attribute",
			"primary_item_attribute",
			"set_item_attribute",
			"major_attribute_value",
		],
	)
	ipd_by_name = {row["name"]: row for row in ipd_rows}
	contexts = {}
	for lot in lots:
		ipd_name = lot.get("production_detail")
		ipd = ipd_by_name.get(ipd_name)
		if not ipd:
			continue
		contexts[lot["name"]] = {
			"is_set_item": ipd.get("is_set_item"),
			"packing_attribute": ipd.get("packing_attribute"),
			"primary_item_attribute": ipd.get("primary_item_attribute"),
			"set_item_attribute": ipd.get("set_item_attribute"),
			"major_attribute_value": ipd.get("major_attribute_value"),
			"primary_values": get_ipd_primary_values(ipd_name),
		}
	return contexts


def _load_variant_attributes(variant_names):
	return {variant: get_variant_attr_details(variant) for variant in variant_names}


def _row_is_pending(delivered, received):
	delivered = flt(delivered)
	return delivered > 0 and flt(received) <= delivered * 0.90


def _build_supplier_pending_items(
	work_orders,
	calculated_items,
	lot_contexts,
	variant_attributes,
):
	work_order_by_name = {row["name"]: row for row in work_orders}
	item_groups = {}

	for calculated_item in calculated_items:
		work_order = work_order_by_name.get(calculated_item.get("parent"))
		if not work_order:
			continue

		lot = work_order.get("lot")
		context = lot_contexts.get(lot)
		attributes = variant_attributes.get(calculated_item.get("item_variant"), {})
		if not context or not attributes:
			continue

		primary_attribute = context.get("primary_item_attribute")
		size = attributes.get(primary_attribute)
		if not size:
			continue

		set_combination = update_if_string_instance(calculated_item.get("set_combination")) or {}
		packing_attribute = context.get("packing_attribute")
		major_colour = set_combination.get("major_colour") or attributes.get(packing_attribute) or ""
		is_set_item = bool(context.get("is_set_item"))
		part = None
		colour = major_colour
		if is_set_item:
			variant_colour = attributes.get(packing_attribute) or major_colour
			part = attributes.get(context.get("set_item_attribute"))
			colour = variant_colour
			if part != context.get("major_attribute_value"):
				colour = f"{variant_colour}({major_colour})"

		item_name = work_order.get("item")
		item_group = item_groups.setdefault(item_name, {"item": item_name, "lots": {}})
		lot_group = item_group["lots"].setdefault(
			lot,
			{
				"lot": lot,
				"is_set_item": is_set_item,
				"set_attr": context.get("set_item_attribute"),
				"primary_values": list(context.get("primary_values") or []),
				"rows": {},
			},
		)
		if size not in lot_group["primary_values"]:
			configured_sizes = list(context.get("primary_values") or [])
			extra_sizes = sorted({*lot_group["primary_values"], size} - set(configured_sizes))
			lot_group["primary_values"] = configured_sizes + extra_sizes

		row_key = (colour, part or "")
		row = lot_group["rows"].setdefault(
			row_key,
			{
				"colour": colour,
				"part": part,
				"values": {},
				"dates": {
					"first_dc_date": None,
					"last_dc_date": None,
					"first_grn_date": None,
					"last_grn_date": None,
				},
			},
		)
		value = row["values"].setdefault(
			size,
			{"delivered": 0.0, "received": 0.0, "difference": 0.0},
		)
		delivered = flt(calculated_item.get("delivered_quantity"))
		received = flt(calculated_item.get("received_qty"))
		value["delivered"] += delivered
		value["received"] += received
		value["difference"] = value["received"] - value["delivered"]

		row["dates"]["first_dc_date"] = min_date(row["dates"]["first_dc_date"], work_order.get("first_dc_date"))
		row["dates"]["last_dc_date"] = max_date(row["dates"]["last_dc_date"], work_order.get("last_dc_date"))
		row["dates"]["first_grn_date"] = min_date(row["dates"]["first_grn_date"], work_order.get("first_grn_date"))
		row["dates"]["last_grn_date"] = max_date(row["dates"]["last_grn_date"], work_order.get("last_grn_date"))

	return _finalize_item_groups(item_groups)


def _finalize_item_groups(item_groups):
	items = []
	for item_name in sorted(item_groups, key=lambda value: value or ""):
		lots = []
		for lot_name in sorted(item_groups[item_name]["lots"], key=lambda value: value or ""):
			lot_group = item_groups[item_name]["lots"][lot_name]
			rows = []
			for row_key in sorted(lot_group["rows"], key=lambda value: (value[0] or "", value[1] or "")):
				row = lot_group["rows"][row_key]
				for size in lot_group["primary_values"]:
					row["values"].setdefault(
						size,
						{"delivered": 0.0, "received": 0.0, "difference": 0.0},
					)
				delivered = sum(value["delivered"] for value in row["values"].values())
				received = sum(value["received"] for value in row["values"].values())
				if not _row_is_pending(delivered, received):
					continue
				row["totals"] = {
					"delivered": delivered,
					"received": received,
					"difference": received - delivered,
				}
				last_dc_date = row["dates"]["last_dc_date"]
				last_grn_date = row["dates"]["last_grn_date"]
				row["dates"]["diff_days"] = (
					date_diff(last_grn_date, last_dc_date) if last_dc_date and last_grn_date else None
				)
				rows.append(row)

			if not rows:
				continue

			lot_group["rows"] = rows
			lot_group["totals"] = _build_lot_totals(lot_group)
			lots.append(lot_group)

		if lots:
			items.append({"item": item_name, "lots": lots})
	return items


def _build_lot_totals(lot_group):
	part_totals = {}
	for row in lot_group["rows"]:
		part = row["part"] if lot_group["is_set_item"] else None
		total = part_totals.setdefault(
			part,
			{
				"part": part,
				"values": {
					size: {"delivered": 0.0, "received": 0.0, "difference": 0.0}
					for size in lot_group["primary_values"]
				},
				"totals": {"delivered": 0.0, "received": 0.0, "difference": 0.0},
			},
		)
		for size in lot_group["primary_values"]:
			for quantity_type in ("delivered", "received", "difference"):
				total["values"][size][quantity_type] += row["values"][size][quantity_type]
		for quantity_type in ("delivered", "received", "difference"):
			total["totals"][quantity_type] += row["totals"][quantity_type]

	return [part_totals[key] for key in sorted(part_totals, key=lambda value: value or "")]
