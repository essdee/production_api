from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate

from production_api.api.stock import get_stock
from production_api.production_api.doctype.item.item import get_attribute_details


@frappe.whitelist()
def get_ppo_production_snapshot(
	item,
	ppo_start_date,
	ppo_end_date,
	inward_start_date,
	inward_end_date,
	warehouses=None,
):
	"""Return the MRP-side PPO, lot, inward, WIP, and stock snapshot.

	Authorization for the business report is enforced on the calling Sales site.
	This endpoint still requires an authenticated MRP user and is intended to be
	called with the configured Master Site credentials.
	"""
	if frappe.session.user == "Guest":
		frappe.throw("Authentication is required", frappe.PermissionError)

	filters = _validate_filters(
		item=item,
		ppo_start_date=ppo_start_date,
		ppo_end_date=ppo_end_date,
		inward_start_date=inward_start_date,
		inward_end_date=inward_end_date,
	)
	warehouse_names = _normalise_warehouses(warehouses)

	ppo_rows = _fetch_ppo_rows(
		filters["item"],
		filters["ppo_start_date"],
		filters["ppo_end_date"],
	)
	ppo_names = list(dict.fromkeys(row.name for row in ppo_rows))

	if not ppo_names:
		return _empty_snapshot(filters, warehouse_names)

	lot_rows = _fetch_lot_rows(ppo_names)
	lot_names = list(
		dict.fromkeys(row.lot for row in lot_rows if row.get("lot"))
	)
	inward_rows = _fetch_inward_rows(
		lot_names,
		filters["inward_start_date"],
		filters["inward_end_date"],
	)

	item_variants = list(
		dict.fromkeys(
			row.item_variant
			for row in [*lot_rows, *inward_rows]
			if row.get("item_variant")
		)
	)
	ppo_item_variants = [
		row.item_variant for row in ppo_rows if row.get("item_variant")
	]
	all_item_variants = list(
		dict.fromkeys([*ppo_item_variants, *item_variants])
	)
	variant_attributes = _fetch_primary_attribute_values(all_item_variants)
	column_order = get_attribute_details(filters["item"]).get(
		"primary_attribute_values", []
	)
	stock = {}
	warnings = []
	if item_variants and warehouse_names:
		stock = get_stock(
			item=item_variants,
			warehouse=warehouse_names,
			remove_zero_balance_item=0,
		)
	elif item_variants:
		warnings.append(
			"No enabled Sales warehouses were supplied; current stock was not calculated."
		)

	return build_production_snapshot(
		filters=filters,
		ppo_rows=ppo_rows,
		lot_rows=lot_rows,
		inward_rows=inward_rows,
		stock=stock,
		warehouses=warehouse_names,
		variant_attributes=variant_attributes,
		column_order=column_order,
		warnings=warnings,
	)


def build_production_snapshot(
	*,
	filters,
	ppo_rows,
	lot_rows,
	inward_rows,
	stock,
	warehouses,
	variant_attributes=None,
	column_order=None,
	warnings=None,
):
	"""Build a deterministic report payload from query rows.

	Kept independent from database access so the multi-lot and mismatched-inward
	edge cases can be regression-tested without a running site.
	"""
	variant_attributes = variant_attributes or {}
	column_order = list(column_order or [])
	ppo_map = {}
	for row in ppo_rows:
		ppo = ppo_map.setdefault(
			row.name,
			{
				"name": row.name,
				"item": row.item,
				"delivery_date": _date_string(row.delivery_date),
				"details": [],
				"quantity": 0.0,
				"lot_count": 0,
			},
		)
		if row.get("item_variant"):
			quantity = flt(row.get("quantity"))
			ppo["details"].append(
				{
					"item_variant": row.item_variant,
					"primary_attribute_value": variant_attributes.get(
						row.item_variant
					),
					"quantity": quantity,
				}
			)
			ppo["quantity"] += quantity

	lot_map = {}
	variant_items = {}
	report_warnings = list(warnings or [])
	for row in lot_rows:
		if not row.get("lot"):
			continue
		lot = lot_map.setdefault(
			row.lot,
			{
				"name": row.lot,
				"production_order": row.production_order,
				"header_item": row.get("lot_item"),
				"status": row.get("status"),
				"is_transferred": bool(row.get("is_transferred")),
				"transferred_lot": row.get("transferred_lot"),
				"items": {},
			},
		)
		if row.get("item_variant"):
			key = row.item_variant
			item_name = row.get("item") or row.get("lot_item")
			variant_items[key] = item_name
			item_row = lot["items"].setdefault(
				key,
				{
					"item": item_name,
					"item_variant": key,
					"primary_attribute_value": variant_attributes.get(key),
					"planned_quantity": 0.0,
					"inward_quantity": 0.0,
					"wip_quantity": 0.0,
					"over_inward_quantity": 0.0,
					"inward_entries": [],
				},
			)
			item_row["planned_quantity"] += flt(row.get("planned_quantity"))

	for row in inward_rows:
		if not row.get("lot") or not row.get("item_variant"):
			continue
		lot = lot_map.setdefault(
			row.lot,
			{
				"name": row.lot,
				"production_order": None,
				"header_item": None,
				"status": None,
				"is_transferred": False,
				"transferred_lot": None,
				"items": {},
			},
		)
		item_name = row.get("item")
		variant_items[row.item_variant] = item_name
		item_row = lot["items"].setdefault(
			row.item_variant,
			{
				"item": item_name,
				"item_variant": row.item_variant,
				"primary_attribute_value": variant_attributes.get(
					row.item_variant
				),
				"planned_quantity": 0.0,
				"inward_quantity": 0.0,
				"wip_quantity": 0.0,
				"over_inward_quantity": 0.0,
				"inward_entries": [],
			},
		)
		quantity, conversion_warning = _inward_quantity_in_boxes(row)
		if conversion_warning and conversion_warning not in report_warnings:
			report_warnings.append(conversion_warning)
		if quantity is None:
			continue
		item_row["inward_quantity"] += quantity
		item_row["inward_entries"].append(
			{
				"stock_entry": row.get("stock_entry"),
				"posting_date": _date_string(row.get("posting_date")),
				"warehouse": row.get("warehouse"),
				"quantity": quantity,
				"uom": row.get("uom"),
				"reported_uom": "Box",
			}
		)

	lots = []
	for lot in lot_map.values():
		items = []
		for item_row in lot["items"].values():
			difference = (
				item_row["planned_quantity"] - item_row["inward_quantity"]
			)
			item_row["wip_quantity"] = max(difference, 0.0)
			item_row["over_inward_quantity"] = max(-difference, 0.0)
			items.append(item_row)
		lot["items"] = sorted(
			items,
			key=lambda row: (row.get("item") or "", row["item_variant"]),
		)
		lot["planned_quantity"] = sum(
			row["planned_quantity"] for row in lot["items"]
		)
		lot["inward_quantity"] = sum(
			row["inward_quantity"] for row in lot["items"]
		)
		lot["wip_quantity"] = sum(
			row["wip_quantity"] for row in lot["items"]
		)
		lot["over_inward_quantity"] = sum(
			row["over_inward_quantity"] for row in lot["items"]
		)
		lots.append(lot)

	lots.sort(key=lambda row: (row.get("production_order") or "", row["name"]))
	for ppo in ppo_map.values():
		ppo["lot_count"] = sum(
			1 for lot in lots if lot.get("production_order") == ppo["name"]
		)

	stock_rows = {}
	for item_variant, row in (stock or {}).items():
		stock_rows[item_variant] = {
			"item": variant_items.get(item_variant),
			"item_variant": item_variant,
			"quantity": flt(row.get("bal_qty")),
			"uom": row.get("uom"),
		}

	summary = {
		"ppo_quantity": sum(ppo["quantity"] for ppo in ppo_map.values()),
		"lot_quantity": sum(lot["planned_quantity"] for lot in lots),
		"inward_quantity": sum(lot["inward_quantity"] for lot in lots),
		"wip_quantity": sum(lot["wip_quantity"] for lot in lots),
		"over_inward_quantity": sum(
			lot["over_inward_quantity"] for lot in lots
		),
	}

	return {
		"filters": {
			key: _date_string(value) if key.endswith("_date") else value
			for key, value in filters.items()
		},
		"warehouses": warehouses,
		"summary": summary,
		"ppos": list(ppo_map.values()),
		"lots": lots,
		"variants": [
			{
				"item_variant": variant,
				"item": item,
				"primary_attribute_value": variant_attributes.get(variant),
			}
			for variant, item in sorted(
				variant_items.items(), key=lambda value: (value[1] or "", value[0])
			)
		],
		"column_order": _merge_column_order(
			column_order,
			variant_attributes.values(),
		),
		"stock": stock_rows,
		"warnings": report_warnings,
	}


def _fetch_ppo_rows(item, start_date, end_date):
	production_order = frappe.qb.DocType("Production Order")
	detail = frappe.qb.DocType("Production Order Detail")

	return (
		frappe.qb.from_(production_order)
		.left_join(detail)
		.on(detail.parent == production_order.name)
		.select(
			production_order.name,
			production_order.item,
			production_order.delivery_date,
			detail.item_variant,
			detail.quantity,
			detail.idx,
		)
		.where(production_order.docstatus == 1)
		.where(production_order.item == item)
		.where(production_order.delivery_date.between(start_date, end_date))
		.orderby(production_order.delivery_date)
		.orderby(production_order.name)
		.orderby(detail.idx)
	).run(as_dict=True)


def _fetch_lot_rows(ppo_names):
	if not ppo_names:
		return []

	lot = frappe.qb.DocType("Lot")
	lot_item = frappe.qb.DocType("Lot Order Item")
	item_variant = frappe.qb.DocType("Item Variant")

	return (
		frappe.qb.from_(lot)
		.left_join(lot_item)
		.on(lot_item.parent == lot.name)
		.left_join(item_variant)
		.on(item_variant.name == lot_item.item_variant)
		.select(
			lot.name.as_("lot"),
			lot.production_order,
			lot.item.as_("lot_item"),
			lot.status,
			lot.is_transferred,
			lot.transferred_lot,
			lot_item.item_variant,
			lot_item.qty.as_("planned_quantity"),
			lot_item.idx,
			item_variant.item,
		)
		.where(lot.production_order.isin(ppo_names))
		.orderby(lot.production_order)
		.orderby(lot.name)
		.orderby(lot_item.idx)
	).run(as_dict=True)


def _fetch_inward_rows(lot_names, start_date, end_date):
	if not lot_names:
		return []

	stock_entry = frappe.qb.DocType("FG Stock Entry")
	detail = frappe.qb.DocType("FG Stock Entry Detail")
	item_variant = frappe.qb.DocType("Item Variant")
	box_uom = frappe.qb.DocType("UOM Conversion Detail").as_("box_uom")

	return (
		frappe.qb.from_(detail)
		.join(stock_entry)
		.on(stock_entry.name == detail.parent)
		.left_join(item_variant)
		.on(item_variant.name == detail.item_variant)
		.left_join(box_uom)
		.on(
			(box_uom.parent == item_variant.item)
			& (box_uom.uom == "Box")
		)
		.select(
			detail.lot,
			detail.item_variant,
			detail.qty.as_("inward_quantity"),
			detail.uom,
			detail.stock_qty,
			detail.stock_uom,
			detail.conversion_factor,
			box_uom.conversion_factor.as_("box_conversion_factor"),
			stock_entry.name.as_("stock_entry"),
			stock_entry.posting_date,
			stock_entry.warehouse,
			item_variant.item,
		)
		.where(stock_entry.docstatus == 1)
		.where(stock_entry.consumed == 0)
		.where(stock_entry.posting_date.between(start_date, end_date))
		.where(detail.lot.isin(lot_names))
		.orderby(stock_entry.posting_date)
		.orderby(stock_entry.name)
		.orderby(detail.idx)
	).run(as_dict=True)


def _fetch_primary_attribute_values(item_variants):
	if not item_variants:
		return {}

	item_variant = frappe.qb.DocType("Item Variant")
	item = frappe.qb.DocType("Item")
	attribute = frappe.qb.DocType("Item Variant Attribute")

	rows = (
		frappe.qb.from_(item_variant)
		.join(item)
		.on(item.name == item_variant.item)
		.left_join(attribute)
		.on(
			(attribute.parent == item_variant.name)
			& (attribute.attribute == item.primary_attribute)
		)
		.select(
			item_variant.name.as_("item_variant"),
			attribute.attribute_value.as_("primary_attribute_value"),
		)
		.where(item_variant.name.isin(item_variants))
	).run(as_dict=True)

	return {
		row.item_variant: row.primary_attribute_value
		for row in rows
		if row.get("primary_attribute_value")
	}


def _merge_column_order(preferred, observed):
	columns = []
	for value in [*(preferred or []), *(observed or [])]:
		value = str(value or "").strip()
		if value and value not in columns:
			columns.append(value)
	return columns


def _inward_quantity_in_boxes(row):
	"""Return an FG inward row in boxes, or a warning when it cannot be converted."""
	source_uom = str(row.get("uom") or "").strip()
	if source_uom.lower() in {"box", "boxes"}:
		return flt(row.get("inward_quantity")), None

	stock_uom = str(row.get("stock_uom") or "").strip()
	stock_quantity = row.get("stock_qty")
	if stock_quantity is None:
		stock_quantity = (
			flt(row.get("inward_quantity"))
			* flt(row.get("conversion_factor") or 1)
		)
	stock_quantity = flt(stock_quantity)

	if stock_uom.lower() in {"box", "boxes"}:
		return stock_quantity, None

	box_factor = flt(row.get("box_conversion_factor"))
	if box_factor:
		return stock_quantity / box_factor, None

	item_variant_name = row.get("item_variant") or "Unknown item variant"
	return None, (
		f"FG inward UOM conversion is missing for {item_variant_name}: "
		f"{source_uom or stock_uom or 'Unknown UOM'} to Box. "
		"The affected inward row was excluded."
	)


def _validate_filters(
	*,
	item,
	ppo_start_date,
	ppo_end_date,
	inward_start_date,
	inward_end_date,
):
	required = {
		"item": item,
		"ppo_start_date": ppo_start_date,
		"ppo_end_date": ppo_end_date,
		"inward_start_date": inward_start_date,
		"inward_end_date": inward_end_date,
	}
	missing = [key for key, value in required.items() if not value]
	if missing:
		frappe.throw(
			f"Missing required filters: {', '.join(missing)}",
			frappe.ValidationError,
		)

	result = {"item": str(item).strip()}
	for fieldname in (
		"ppo_start_date",
		"ppo_end_date",
		"inward_start_date",
		"inward_end_date",
	):
		result[fieldname] = getdate(required[fieldname])

	_validate_date_range(
		result["ppo_start_date"],
		result["ppo_end_date"],
		"PPO delivery",
	)
	_validate_date_range(
		result["inward_start_date"],
		result["inward_end_date"],
		"Inward",
	)
	return result


def _validate_date_range(start_date, end_date, label):
	if start_date > end_date:
		frappe.throw(
			f"{label} start date cannot be after its end date",
			frappe.ValidationError,
		)


def _normalise_warehouses(warehouses):
	if isinstance(warehouses, str):
		warehouses = frappe.parse_json(warehouses)
	if not warehouses:
		return []
	if not isinstance(warehouses, (list, tuple)):
		frappe.throw("warehouses must be a list", frappe.ValidationError)
	return list(
		dict.fromkeys(
			str(warehouse).strip()
			for warehouse in warehouses
			if str(warehouse).strip()
		)
	)


def _empty_snapshot(filters, warehouses):
	return {
		"filters": {
			key: _date_string(value) if key.endswith("_date") else value
			for key, value in filters.items()
		},
		"warehouses": warehouses,
		"summary": {
			"ppo_quantity": 0.0,
			"lot_quantity": 0.0,
			"inward_quantity": 0.0,
			"wip_quantity": 0.0,
			"over_inward_quantity": 0.0,
		},
		"ppos": [],
		"lots": [],
		"variants": [],
		"column_order": [],
		"stock": {},
		"warnings": [],
	}


def _date_string(value):
	return value.isoformat() if hasattr(value, "isoformat") else value
