# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from production_api.utils import get_variant_attr_details


class PPOPriceRequest(Document):
	pass


@frappe.whitelist()
def approve_ppo_price_request(name):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can approve price changes")

	doc = frappe.get_doc("PPO Price Request", name)
	if doc.status != "Pending":
		frappe.throw(f"Cannot approve a request with status '{doc.status}'")

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	apply_price_to_production_order(doc)
	apply_price_to_box_sticker_prints(doc)

	frappe.db.set_value("Production Order", doc.production_order,
		"price_approval_status", "", update_modified=False)

	return {"status": "success"}


@frappe.whitelist()
def reject_ppo_price_request(name):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can reject price changes")

	doc = frappe.get_doc("PPO Price Request", name)
	if doc.status != "Pending":
		frappe.throw(f"Cannot reject a request with status '{doc.status}'")

	doc.status = "Rejected"
	doc.approved_by = frappe.session.user
	doc.approved_at = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	frappe.db.set_value("Production Order", doc.production_order,
		"price_approval_status", "", update_modified=False)

	return {"status": "success"}


def apply_price_to_production_order(price_request):
	po_doc = frappe.get_doc("Production Order", price_request.production_order)
	primary = frappe.get_value("Item", po_doc.item, "primary_attribute")

	for detail in price_request.price_details:
		for row in po_doc.production_order_details:
			attrs = get_variant_attr_details(row.item_variant)
			if attrs[primary] == detail.size:
				if row.get("production_order_mrp") in (None, ""):
					row.production_order_mrp = row.mrp
				row.mrp = detail.new_mrp
				row.wholesale_price = detail.new_wholesale_price
				row.retail_price = detail.new_retail_price
				break

	po_doc.save(ignore_permissions=True)


def apply_price_to_box_sticker_prints(price_request):
	lots = frappe.get_all(
		"Lot",
		filters={"production_order": price_request.production_order},
		pluck="name"
	)
	if not lots:
		return

	bsp_list = frappe.get_all(
		"Box Sticker Print",
		filters={"lot": ["in", lots], "docstatus": 1},
		pluck="name"
	)
	if not bsp_list:
		return

	price_map = {}
	for detail in price_request.price_details:
		price_map[detail.size] = detail.new_mrp

	for bsp_name in bsp_list:
		bsp_doc = frappe.get_doc("Box Sticker Print", bsp_name)
		changed = False
		for row in bsp_doc.box_sticker_print_details:
			if row.printed_quantity == 0 and row.size in price_map:
				row.mrp = price_map[row.size]
				changed = True
		if changed:
			bsp_doc.save(ignore_permissions=True)
