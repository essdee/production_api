import frappe
from frappe.utils import flt, now_datetime

from production_api.utils import get_variant_attr_details


def get_production_order_price_map(production_order):
	"""Return the PPO default MRP keyed by its primary attribute value."""
	doc = (
		production_order
		if getattr(production_order, "doctype", None) == "Production Order"
		else frappe.get_doc("Production Order", production_order)
	)
	primary = frappe.get_value("Item", doc.item, "primary_attribute")
	price_map = {}
	if not primary:
		return price_map

	for row in doc.production_order_details:
		size = get_variant_attr_details(row.item_variant).get(primary)
		if size:
			price_map[size] = flt(row.mrp)
	return price_map


def get_lot_override_map(production_order):
	doc = (
		production_order
		if getattr(production_order, "doctype", None) == "Production Order"
		else frappe.get_doc("Production Order", production_order)
	)
	overrides = {}
	for row in doc.get("lot_price_overrides") or []:
		overrides.setdefault(row.lot, {})[row.size] = flt(row.mrp)
	return overrides


def get_lot_print_state(lot, for_update=False):
	lock_clause = " FOR UPDATE" if for_update else ""
	rows = frappe.db.sql(
		"""
		SELECT bsp.name AS box_sticker_print, bsp.modified, detail.name AS detail_name,
			detail.size, detail.mrp, detail.printed_quantity
		FROM `tabBox Sticker Print` bsp
		INNER JOIN `tabBox Sticker Print Detail` detail ON detail.parent = bsp.name
		WHERE bsp.lot = %s AND bsp.docstatus = 1
			AND bsp.against = 'Work Order' AND COALESCE(bsp.against_id, '') != ''
		ORDER BY bsp.modified DESC, bsp.creation DESC, detail.idx ASC
		""" + lock_clause,
		(lot,),
		as_dict=True,
	)

	documents = []
	prices = {}
	locked = False
	for row in rows:
		if row.box_sticker_print not in documents:
			documents.append(row.box_sticker_print)
		printed_quantity = flt(row.printed_quantity)
		locked = locked or printed_quantity > 0
		entry = prices.setdefault(
			row.size,
			{
				"snapshot_mrp": flt(row.mrp),
				"printed_quantity": 0,
				"printed_mrps": [],
			},
		)
		entry["printed_quantity"] += printed_quantity
		if printed_quantity > 0 and flt(row.mrp) not in entry["printed_mrps"]:
			entry["printed_mrps"].append(flt(row.mrp))

	return {"locked": locked, "documents": documents, "prices": prices}


def get_lot_pricing(lot, production_order=None, for_update=False):
	linked_production_order = frappe.db.get_value("Lot", lot, "production_order")
	if not linked_production_order:
		return None
	if production_order and linked_production_order != production_order:
		frappe.throw(f"Lot {lot} is not linked to Production Order {production_order}")

	production_order = linked_production_order
	ppo_doc = frappe.get_doc("Production Order", production_order)
	defaults = get_production_order_price_map(ppo_doc)
	overrides = get_lot_override_map(ppo_doc).get(lot, {})
	print_state = get_lot_print_state(lot, for_update=for_update)
	all_sizes = list(defaults)
	for size in overrides:
		if size not in all_sizes:
			all_sizes.append(size)
	for size in print_state["prices"]:
		if size not in all_sizes:
			all_sizes.append(size)

	prices = {}
	for size in all_sizes:
		has_override = size in overrides
		assigned_mrp = overrides.get(size) if has_override else defaults.get(size)
		print_price = print_state["prices"].get(size, {})
		# Once any label is printed for the Lot, its submitted BSP is the immutable
		# source for every subsequent print from that Lot.
		effective_mrp = (
			print_price.get("snapshot_mrp", assigned_mrp)
			if print_state["locked"]
			else assigned_mrp
		)
		prices[size] = {
			"ppo_mrp": defaults.get(size),
			"override_mrp": overrides.get(size) if has_override else None,
			"has_override": has_override,
			"effective_mrp": effective_mrp,
			"snapshot_mrp": print_price.get("snapshot_mrp"),
			"printed_quantity": flt(print_price.get("printed_quantity")),
			"printed_mrps": print_price.get("printed_mrps", []),
		}

	return {
		"lot": lot,
		"production_order": production_order,
		"locked": print_state["locked"],
		"box_sticker_prints": print_state["documents"],
		"prices": prices,
	}


def get_effective_lot_price_map(lot, production_order=None, for_update=False):
	pricing = get_lot_pricing(lot, production_order, for_update=for_update)
	if not pricing:
		return {}
	return {size: row.get("effective_mrp") for size, row in pricing["prices"].items()}


def validate_lot_price_overrides(doc):
	if doc.doctype != "Production Order":
		return

	valid_sizes = set(get_production_order_price_map(doc))
	seen = set()
	previous = doc.get_doc_before_save()
	previous_overrides = get_lot_override_map(previous) if previous else {}
	current_overrides = {}

	for row in doc.get("lot_price_overrides") or []:
		key = (row.lot, row.size)
		if key in seen:
			frappe.throw(f"Duplicate Lot price override for {row.lot}, size {row.size}")
		seen.add(key)
		if frappe.db.get_value("Lot", row.lot, "production_order") != doc.name:
			frappe.throw(f"Lot {row.lot} is not linked to Production Order {doc.name}")
		if row.size not in valid_sizes:
			frappe.throw(f"Size {row.size} is not present in Production Order {doc.name}")
		if flt(row.mrp) <= 0:
			frappe.throw(f"MRP must be greater than zero for Lot {row.lot}, size {row.size}")
		row.changed_by = row.changed_by or frappe.session.user
		row.changed_on = row.changed_on or now_datetime()
		current_overrides.setdefault(row.lot, {})[row.size] = flt(row.mrp)

	for lot in set(previous_overrides) | set(current_overrides):
		if previous_overrides.get(lot, {}) == current_overrides.get(lot, {}):
			continue
		if get_lot_print_state(lot)["locked"]:
			frappe.throw(f"Lot {lot} price is locked because Box Stickers have already been printed")


def sync_unprinted_box_sticker_prices(lot, production_order=None):
	pricing = get_lot_pricing(lot, production_order, for_update=True)
	if not pricing or pricing["locked"]:
		return 0

	updated = 0
	for box_sticker_print in pricing["box_sticker_prints"]:
		rows = frappe.get_all(
			"Box Sticker Print Detail",
			filters={"parent": box_sticker_print},
			fields=["name", "size", "mrp"],
		)
		for row in rows:
			mrp = pricing["prices"].get(row.size, {}).get("effective_mrp")
			if mrp is None or flt(mrp) <= 0:
				frappe.throw(f"MRP is missing for Lot {lot}, size {row.size}")
			if flt(row.mrp) != flt(mrp):
				frappe.db.set_value(
					"Box Sticker Print Detail", row.name, "mrp", flt(mrp), update_modified=False
				)
				updated += 1
	return updated
