from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate

from production_api.api.stock import get_stock
from production_api.production_api.doctype.item.item import get_attribute_details


@frappe.whitelist()
def get_ppo_production_snapshot(
	item,
	inward_start_date,
	inward_end_date,
	warehouses=None,
	ppo=None,
	lot=None,
	ppo_start_date=None,
	ppo_end_date=None,
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
		ppo=ppo,
		lot=lot,
	)
	warehouse_names = _normalise_warehouses(warehouses)

	ppo_rows = _fetch_ppo_rows(
		filters["item"],
		filters["ppo"],
	)
	ppo_names = list(dict.fromkeys(row.name for row in ppo_rows))

	if not ppo_names:
		return _empty_snapshot(filters, warehouse_names)

	seed_lots = _fetch_inward_lot_names(
		filters["item"],
		filters["inward_start_date"],
		filters["inward_end_date"],
	)
	if filters["lot"]:
		seed_lots = [name for name in seed_lots if name == filters["lot"]]
	lot_rows = _fetch_lot_rows(ppo_names, seed_lots)
	lot_names = list(
		dict.fromkeys(row.lot for row in lot_rows if row.get("lot"))
	)
	stage_rows = _fetch_lot_stage_rows(lot_names)
	transferred_source_lots = list(
		dict.fromkeys(
			row.lot
			for row in lot_rows
			if row.get("lot") and row.get("has_transferred")
		)
	)
	transferred_lot_rows = _fetch_transferred_lot_rows(
		transferred_source_lots
	)
	inward_rows = _fetch_inward_rows(lot_names)

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
		dict.fromkeys(
			[
				*ppo_item_variants,
				*item_variants,
				*[
					row.item_variant
					for row in transferred_lot_rows
					if row.get("item_variant")
				],
			]
		)
	)
	variant_attributes = _fetch_primary_attribute_values(all_item_variants)
	column_order = get_attribute_details(filters["item"]).get(
		"primary_attribute_values", []
	)
	stock = {}
	warnings = []
	if all_item_variants and warehouse_names:
		stock = get_stock(
			item=all_item_variants,
			warehouse=warehouse_names,
			remove_zero_balance_item=0,
		)
	elif all_item_variants:
		warnings.append(
			"No enabled Sales warehouses were supplied; current stock was not calculated."
		)

	return build_production_snapshot(
		filters=filters,
		ppo_rows=ppo_rows,
		lot_rows=lot_rows,
		stage_rows=stage_rows,
		transferred_lot_rows=transferred_lot_rows,
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
	stage_rows=None,
	transferred_lot_rows=None,
	variant_attributes=None,
	column_order=None,
	warnings=None,
):
	"""Build the size-wise PPO, Lot, transfer, inward, and WIP snapshot."""
	stage_rows = stage_rows or []
	stage_by_lot = {
		row.get("lot"): row for row in stage_rows if row.get("lot")
	}
	transferred_lot_rows = transferred_lot_rows or []
	variant_attributes = variant_attributes or {}
	column_order = list(column_order or [])
	report_warnings = list(warnings or [])

	ppo_map = {}
	variant_items = {}
	for row in ppo_rows:
		ppo = ppo_map.setdefault(
			row.name,
			{
				"name": row.name,
				"item": row.item,
				"delivery_date": _date_string(row.delivery_date),
				"details": [],
				"original_quantity": 0.0,
				"transferred_quantity": 0.0,
				"quantity": 0.0,
				"lot_count": 0,
			},
		)
		if row.get("item_variant"):
			variant_items[row.item_variant] = row.item
			quantity = flt(row.get("quantity"))
			ppo["details"].append(
				{
					"item_variant": row.item_variant,
					"primary_attribute_value": variant_attributes.get(
						row.item_variant
					),
					"original_quantity": quantity,
					"transferred_quantity": 0.0,
					"quantity": quantity,
				}
			)
			ppo["original_quantity"] += quantity
			ppo["quantity"] += quantity

	lot_map = {}
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
				"has_transferred": bool(row.get("has_transferred")),
				"is_transferred": bool(row.get("is_transferred")),
				"transferred_lot": row.get("transferred_lot"),
				"transferred_lots": [],
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
					"original_planned_quantity": 0.0,
					"transferred_quantity": 0.0,
					"planned_quantity": 0.0,
					"inward_quantity": 0.0,
					"wip_quantity": 0.0,
					"over_inward_quantity": 0.0,
					"inward_entries": [],
				},
			)
			planned_quantity = flt(row.get("planned_quantity"))
			item_row["original_planned_quantity"] += planned_quantity
			item_row["planned_quantity"] += planned_quantity

	transfer_deductions = defaultdict(lambda: defaultdict(float))
	transfer_lots = defaultdict(set)
	for row in transferred_lot_rows:
		source_lot = row.get("source_lot")
		item_variant = row.get("item_variant")
		if not source_lot or not item_variant:
			continue
		size = _size_key(item_variant, variant_attributes)
		transfer_deductions[source_lot][size] += flt(
			row.get("transferred_quantity")
		)
		if row.get("transferred_lot"):
			transfer_lots[source_lot].add(row.transferred_lot)

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
				"has_transferred": False,
				"is_transferred": False,
				"transferred_lot": None,
				"transferred_lots": [],
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
				"original_planned_quantity": 0.0,
				"transferred_quantity": 0.0,
				"planned_quantity": 0.0,
				"inward_quantity": 0.0,
				"wip_quantity": 0.0,
				"over_inward_quantity": 0.0,
				"inward_entries": [],
			},
		)
		quantity = flt(row.get("inward_quantity"))
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
	ppo_transfer_deductions = defaultdict(lambda: defaultdict(float))
	for lot in lot_map.values():
		items = list(lot["items"].values())
		applied_transfers = _apply_size_deductions(
			items,
			transfer_deductions.get(lot["name"], {}),
			quantity_field="planned_quantity",
			deducted_field="transferred_quantity",
			variant_attributes=variant_attributes,
			warnings=report_warnings,
			label=f"Lot {lot['name']}",
		)
		lot["transferred_lots"] = sorted(transfer_lots.get(lot["name"], set()))
		lot["transferred_quantity"] = sum(applied_transfers.values())
		for size, quantity in applied_transfers.items():
			if lot.get("production_order"):
				ppo_transfer_deductions[lot["production_order"]][size] += quantity

		size_map = {}
		for item_row in items:
			size = _size_key(item_row.get("item_variant"), variant_attributes)
			size_row = size_map.setdefault(
				size,
				{
					"primary_attribute_value": size,
					"original_planned_quantity": 0.0,
					"transferred_quantity": 0.0,
					"planned_quantity": 0.0,
					"inward_quantity": 0.0,
					"wip_quantity": 0.0,
					"over_inward_quantity": 0.0,
					"inward_entries": [],
				},
			)
			for fieldname in (
				"original_planned_quantity",
				"transferred_quantity",
				"planned_quantity",
				"inward_quantity",
			):
				size_row[fieldname] += flt(item_row.get(fieldname))
			size_row["inward_entries"].extend(
				item_row.get("inward_entries") or []
			)

		size_rows = []
		for size_row in size_map.values():
			difference = (
				size_row["planned_quantity"] - size_row["inward_quantity"]
			)
			size_row["wip_quantity"] = max(difference, 0.0)
			size_row["over_inward_quantity"] = max(-difference, 0.0)
			size_rows.append(size_row)

		for item_row in items:
			difference = (
				item_row["planned_quantity"] - item_row["inward_quantity"]
			)
			item_row["wip_quantity"] = max(difference, 0.0)
			item_row["over_inward_quantity"] = max(-difference, 0.0)
		lot["items"] = sorted(
			items,
			key=lambda row: (row.get("item") or "", row["item_variant"]),
		)
		lot["size_rows"] = sorted(
			size_rows,
			key=lambda row: _column_sort_key(
				row["primary_attribute_value"],
				column_order,
			),
		)
		lot["original_planned_quantity"] = sum(
			row["original_planned_quantity"] for row in lot["size_rows"]
		)
		lot["planned_quantity"] = sum(
			row["planned_quantity"] for row in lot["size_rows"]
		)
		lot["inward_quantity"] = sum(
			row["inward_quantity"] for row in lot["size_rows"]
		)
		stage = stage_by_lot.get(lot["name"], {})
		lot["production_stage"] = stage.get("production_stage") or "Cutting"
		lot["stage_details"] = {
			"cutting_work_orders": list(stage.get("cutting_work_orders") or []),
			"stitching_work_orders": list(stage.get("stitching_work_orders") or []),
			"stitching_has_delivery_challan": bool(
				stage.get("stitching_has_delivery_challan")
			),
			"stitching_has_goods_received_note": bool(
				stage.get("stitching_has_goods_received_note")
			),
		}
		lot["wip_quantity"] = sum(
			row["wip_quantity"] for row in lot["size_rows"]
		)
		lot["over_inward_quantity"] = sum(
			row["over_inward_quantity"] for row in lot["size_rows"]
		)
		lots.append(lot)

	lots.sort(key=lambda row: (row.get("production_order") or "", row["name"]))
	for ppo in ppo_map.values():
		applied_transfers = _apply_size_deductions(
			ppo["details"],
			ppo_transfer_deductions.get(ppo["name"], {}),
			quantity_field="quantity",
			deducted_field="transferred_quantity",
			variant_attributes=variant_attributes,
			warnings=report_warnings,
			label=f"PPO {ppo['name']}",
		)
		ppo["transferred_quantity"] = sum(applied_transfers.values())
		ppo["quantity"] = sum(
			flt(detail.get("quantity")) for detail in ppo["details"]
		)
		ppo["lot_count"] = sum(
			1 for lot in lots if lot.get("production_order") == ppo["name"]
		)

	ppo_inward_by_size = defaultdict(lambda: defaultdict(float))
	ppo_lot_planned_by_size = defaultdict(lambda: defaultdict(float))
	ppo_lot_wip_by_size = defaultdict(lambda: defaultdict(float))
	ppo_over_inward_by_size = defaultdict(lambda: defaultdict(float))
	for lot in lots:
		production_order = lot.get("production_order")
		if not production_order:
			continue
		for size_row in lot.get("size_rows") or []:
			size = size_row.get("primary_attribute_value") or "Unspecified"
			ppo_lot_planned_by_size[production_order][size] += flt(
				size_row.get("planned_quantity")
			)
			ppo_inward_by_size[production_order][size] += flt(
				size_row.get("inward_quantity")
			)
			ppo_lot_wip_by_size[production_order][size] += flt(
				size_row.get("wip_quantity")
			)
			ppo_over_inward_by_size[production_order][size] += flt(
				size_row.get("over_inward_quantity")
			)

	total_over_inward = 0.0
	for ppo in ppo_map.values():
		remaining_inward = dict(ppo_inward_by_size.get(ppo["name"], {}))
		remaining_lot_planned = dict(
			ppo_lot_planned_by_size.get(ppo["name"], {})
		)
		remaining_lot_wip = dict(ppo_lot_wip_by_size.get(ppo["name"], {}))
		remaining_over_inward = dict(
			ppo_over_inward_by_size.get(ppo["name"], {})
		)
		for detail in ppo["details"]:
			size = _size_key(detail.get("item_variant"), variant_attributes)
			detail["lot_planned_quantity"] = flt(
				remaining_lot_planned.pop(size, 0)
			)
			detail["inward_quantity"] = flt(remaining_inward.pop(size, 0))
			detail["wip_quantity"] = flt(remaining_lot_wip.pop(size, 0))
			detail["over_inward_quantity"] = flt(
				remaining_over_inward.pop(size, 0)
			)
		ppo["planned_quantity"] = sum(
			flt(detail.get("lot_planned_quantity")) for detail in ppo["details"]
		)
		ppo["inward_quantity"] = sum(
			flt(detail.get("inward_quantity")) for detail in ppo["details"]
		)
		ppo["wip_quantity"] = sum(
			flt(detail.get("wip_quantity")) for detail in ppo["details"]
		)
		ppo["over_inward_quantity"] = sum(
			flt(detail.get("over_inward_quantity")) for detail in ppo["details"]
		)
		ppo["production_stage"] = _aggregate_production_stage(
			lot.get("production_stage")
			for lot in lots
			if lot.get("production_order") == ppo["name"]
		)
		total_over_inward += ppo["over_inward_quantity"]

	stock_rows = {}
	for item_variant, row in (stock or {}).items():
		stock_rows[item_variant] = {
			"item": variant_items.get(item_variant),
			"item_variant": item_variant,
			"quantity": flt(row.get("bal_qty")),
			"uom": row.get("uom"),
		}

	summary = {
		"ppo_original_quantity": sum(
			ppo["original_quantity"] for ppo in ppo_map.values()
		),
		"transferred_quantity": sum(
			ppo["transferred_quantity"] for ppo in ppo_map.values()
		),
		"ppo_quantity": sum(ppo["quantity"] for ppo in ppo_map.values()),
		"lot_original_quantity": sum(
			lot["original_planned_quantity"] for lot in lots
		),
		"lot_quantity": sum(lot["planned_quantity"] for lot in lots),
		"inward_quantity": sum(lot["inward_quantity"] for lot in lots),
		"wip_quantity": sum(
			ppo["wip_quantity"] for ppo in ppo_map.values()
		),
		"over_inward_quantity": total_over_inward,
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


def _apply_size_deductions(
	rows,
	deductions,
	*,
	quantity_field,
	deducted_field,
	variant_attributes,
	warnings,
	label,
):
	"""Apply transferred quantities by size, deliberately ignoring Item names."""
	applied = defaultdict(float)
	for size, requested_quantity in (deductions or {}).items():
		remaining = flt(requested_quantity)
		for row in rows:
			if remaining <= 0:
				break
			if _size_key(row.get("item_variant"), variant_attributes) != size:
				continue
			available = max(flt(row.get(quantity_field)), 0.0)
			deducted = min(available, remaining)
			row[quantity_field] = available - deducted
			row[deducted_field] = flt(row.get(deducted_field)) + deducted
			applied[size] += deducted
			remaining -= deducted
		if remaining > 0:
			warnings.append(
				f"{label} transferred {requested_quantity} boxes for size "
				f"{size}, but only {applied[size]} boxes were available."
			)
	return dict(applied)


def _size_key(item_variant, variant_attributes):
	return str(
		variant_attributes.get(item_variant)
		or item_variant
		or "Unspecified"
	).strip()


def _column_sort_key(value, preferred):
	value = str(value or "").strip()
	try:
		return (0, preferred.index(value))
	except ValueError:
		return (1, value)


def _fetch_ppo_rows(item, ppo=None):
	production_order = frappe.qb.DocType("Production Order")
	detail = frappe.qb.DocType("Production Order Detail")

	query = (
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
		.where(production_order.status.isin(["Open", "Pending Request"]))
	)
	if ppo:
		query = query.where(production_order.name == ppo)
	return (
		query.orderby(production_order.delivery_date)
		.orderby(production_order.name)
		.orderby(detail.idx)
	).run(as_dict=True)


def _fetch_lot_rows(ppo_names, selected_lots):
	if not ppo_names or not selected_lots:
		return []

	lot = frappe.qb.DocType("Lot")
	lot_item = frappe.qb.DocType("Lot Order Item")
	item_variant = frappe.qb.DocType("Item Variant")

	query = (
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
			lot.has_transferred,
			lot.is_transferred,
			lot.transferred_lot,
			lot_item.item_variant,
			lot_item.qty.as_("planned_quantity"),
			lot_item.idx,
			item_variant.item,
		)
		.where(lot.production_order.isin(ppo_names))
		.where(lot.name.isin(selected_lots))
		.where(lot.is_transferred == 0)
		.orderby(lot.production_order)
		.orderby(lot.name)
		.orderby(lot_item.idx)
	)
	return query.run(as_dict=True)


def _fetch_lot_stage_rows(lot_names):
	"""Resolve each lot's stage from submitted Work Order movements.

	The Work Order's Item Production Detail identifies which configured process
	is Cutting or Stitching. A submitted Stitching DC moves the lot into
	Stitching; a submitted non-return Stitching GRN moves it into Packing.
	"""
	if not lot_names:
		return []

	work_order = frappe.qb.DocType("Work Order")
	production_detail = frappe.qb.DocType("Item Production Detail")
	work_orders = (
		frappe.qb.from_(work_order)
		.left_join(production_detail)
		.on(production_detail.name == work_order.production_detail)
		.select(
			work_order.name,
			work_order.lot,
			work_order.process_name,
			production_detail.cutting_process,
			production_detail.stiching_process,
		)
		.where(work_order.docstatus == 1)
		.where(work_order.lot.isin(lot_names))
		.orderby(work_order.lot)
		.orderby(work_order.name)
	).run(as_dict=True)

	process_names = list(
		dict.fromkeys(
			row.process_name for row in work_orders if row.get("process_name")
		)
	)
	grouped_processes = defaultdict(set)
	if process_names:
		process_detail = frappe.qb.DocType("Process Details")
		for row in (
			frappe.qb.from_(process_detail)
			.select(process_detail.parent, process_detail.process_name)
			.where(process_detail.parent.isin(process_names))
		).run(as_dict=True):
			if row.get("process_name"):
				grouped_processes[row.parent].add(row.process_name)

	lot_states = {
		lot_name: {
			"lot": lot_name,
			"cutting_work_orders": [],
			"stitching_work_orders": [],
			"stitching_has_delivery_challan": False,
			"stitching_has_goods_received_note": False,
		}
		for lot_name in lot_names
	}
	stitching_work_order_lots = {}
	for row in work_orders:
		state = lot_states.setdefault(
			row.lot,
			{
				"lot": row.lot,
				"cutting_work_orders": [],
				"stitching_work_orders": [],
				"stitching_has_delivery_challan": False,
				"stitching_has_goods_received_note": False,
			},
		)
		processes = {
			row.get("process_name"),
			*grouped_processes.get(row.get("process_name"), set()),
		}
		if row.get("cutting_process") in processes:
			state["cutting_work_orders"].append(row.name)
		if row.get("stiching_process") in processes:
			state["stitching_work_orders"].append(row.name)
			stitching_work_order_lots[row.name] = row.lot

	stitching_work_orders = list(stitching_work_order_lots)
	if stitching_work_orders:
		delivery_challan = frappe.qb.DocType("Delivery Challan")
		for row in (
			frappe.qb.from_(delivery_challan)
			.select(delivery_challan.work_order)
			.where(delivery_challan.docstatus == 1)
			.where(delivery_challan.work_order.isin(stitching_work_orders))
			.distinct()
		).run(as_dict=True):
			lot_states[stitching_work_order_lots[row.work_order]][
				"stitching_has_delivery_challan"
			] = True

		goods_received_note = frappe.qb.DocType("Goods Received Note")
		for row in (
			frappe.qb.from_(goods_received_note)
			.select(goods_received_note.against_id.as_("work_order"))
			.where(goods_received_note.docstatus == 1)
			.where(goods_received_note.against == "Work Order")
			.where(goods_received_note.is_return == 0)
			.where(goods_received_note.against_id.isin(stitching_work_orders))
			.distinct()
		).run(as_dict=True):
			lot_states[stitching_work_order_lots[row.work_order]][
				"stitching_has_goods_received_note"
			] = True

	for state in lot_states.values():
		state["production_stage"] = _production_stage_from_work_orders(
			state["stitching_has_delivery_challan"],
			state["stitching_has_goods_received_note"],
		)
	return [lot_states[lot_name] for lot_name in lot_names]


def _fetch_inward_lot_names(item, start_date, end_date):
	"""Seed lots from submitted FG entries for the selected item/date range."""
	stock_entry = frappe.qb.DocType("FG Stock Entry")
	detail = frappe.qb.DocType("FG Stock Entry Detail")
	item_variant = frappe.qb.DocType("Item Variant")

	rows = (
		frappe.qb.from_(detail)
		.join(stock_entry)
		.on(stock_entry.name == detail.parent)
		.join(item_variant)
		.on(item_variant.name == detail.item_variant)
		.select(detail.lot)
		.where(stock_entry.docstatus == 1)
		.where(stock_entry.posting_date.between(start_date, end_date))
		.where(item_variant.item == item)
		.where(detail.lot.isnotnull())
		.distinct()
	).run(as_dict=True)
	return list(dict.fromkeys(row.lot for row in rows if row.get("lot")))


def _fetch_transferred_lot_rows(source_lot_names):
	if not source_lot_names:
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
			lot.transferred_lot.as_("source_lot"),
			lot.name.as_("transferred_lot"),
			lot.item.as_("transferred_item"),
			lot_item.item_variant,
			lot_item.qty.as_("transferred_quantity"),
			lot_item.idx,
			item_variant.item,
		)
		.where(lot.is_transferred == 1)
		.where(lot.transferred_lot.isin(source_lot_names))
		.orderby(lot.transferred_lot)
		.orderby(lot.name)
		.orderby(lot_item.idx)
	).run(as_dict=True)


def _fetch_inward_rows(lot_names):
	"""Fetch every submitted inward row for the lots seeded by the date filter."""
	if not lot_names:
		return []

	stock_entry = frappe.qb.DocType("FG Stock Entry")
	detail = frappe.qb.DocType("FG Stock Entry Detail")
	item_variant = frappe.qb.DocType("Item Variant")
	return (
		frappe.qb.from_(detail)
		.join(stock_entry)
		.on(stock_entry.name == detail.parent)
		.left_join(item_variant)
		.on(item_variant.name == detail.item_variant)
		.select(
			detail.lot,
			detail.item_variant,
			detail.qty.as_("inward_quantity"),
			detail.uom,
			stock_entry.name.as_("stock_entry"),
			stock_entry.posting_date,
			stock_entry.warehouse,
			item_variant.item,
		)
		.where(stock_entry.docstatus == 1)
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


def _production_stage_from_work_orders(stitching_dcs, stitching_grns):
	if stitching_grns:
		return "Packing"
	if stitching_dcs:
		return "Stitching"
	return "Cutting"


def _aggregate_production_stage(stages):
	stage_rank = {"Cutting": 0, "Stitching": 1, "Packing": 2}
	stages = [stage for stage in stages if stage in stage_rank]
	if not stages:
		return None
	return min(stages, key=stage_rank.get)


def _validate_filters(
	*,
	item,
	inward_start_date,
	inward_end_date,
	ppo=None,
	lot=None,
	ppo_start_date=None,
	ppo_end_date=None,
):
	required = {
		"item": item,
		"inward_start_date": inward_start_date,
		"inward_end_date": inward_end_date,
	}
	missing = [key for key, value in required.items() if not value]
	if missing:
		frappe.throw(
			f"Missing required filters: {', '.join(missing)}",
			frappe.ValidationError,
		)

	result = {
		"item": str(item).strip(),
		"ppo": str(ppo or "").strip() or None,
		"lot": str(lot or "").strip() or None,
		"inward_start_date": getdate(inward_start_date),
		"inward_end_date": getdate(inward_end_date),
	}
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
	item = filters.get("item")
	ppo = filters.get("ppo")
	lot = filters.get("lot")
	if lot:
		message = (
			f"Lot {lot} was not found among the selected submitted PPOs "
			f"for {item}."
		)
		code = "lot_not_found"
	elif ppo:
		message = f"No submitted PPO {ppo} was found for {item}."
		code = "ppo_not_found"
	else:
		message = (
			f"No open or pending submitted PPO was found for {item}."
		)
		code = "no_open_ppo"
	return {
		"filters": {
			key: _date_string(value) if key.endswith("_date") else value
			for key, value in filters.items()
		},
		"warehouses": warehouses,
		"summary": {
			"ppo_quantity": 0.0,
			"ppo_original_quantity": 0.0,
			"transferred_quantity": 0.0,
			"lot_quantity": 0.0,
			"lot_original_quantity": 0.0,
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
		"empty_state": {
			"code": code,
			"message": message,
		},
	}


def _date_string(value):
	return value.isoformat() if hasattr(value, "isoformat") else value
