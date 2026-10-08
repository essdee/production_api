"""Supplier Pending Report backend."""

from frappe.utils import date_diff, flt

from production_api.utils import max_date, min_date, update_if_string_instance


def _row_is_pending(delivered, received):
	delivered = flt(delivered)
	return delivered > 0 and flt(received) <= delivered * 0.90


def _build_supplier_pending_items(
	work_orders,
	calculated_items,
	lot_contexts,
	variant_attributes,
	quality_statuses,
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
			lot_group["primary_values"].append(size)

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
			{"delivered": 0.0, "received": 0.0, "difference": 0.0, "quality": None},
		)
		delivered = flt(calculated_item.get("delivered_quantity"))
		received = flt(calculated_item.get("received_qty"))
		value["delivered"] += delivered
		value["received"] += received
		value["difference"] = value["received"] - value["delivered"]

		quality = (
			quality_statuses.get(work_order.get("supplier_name"), {})
			.get(colour, {})
			.get(size)
		)
		if quality is not None:
			value["quality"] = quality

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
						{"delivered": 0.0, "received": 0.0, "difference": 0.0, "quality": None},
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
