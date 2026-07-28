import frappe


def execute():
	"""Add the focused indexes used by the cross-site PPO report."""
	frappe.db.add_index(
		"Production Order",
		["item", "delivery_date", "docstatus"],
		"ppo_report_item_delivery_docstatus",
	)
	frappe.db.add_index(
		"Lot",
		["production_order"],
		"ppo_report_production_order",
	)
	frappe.db.add_index(
		"Lot Order Item",
		["parent", "item_variant"],
		"ppo_report_lot_item",
	)
	frappe.db.add_index(
		"FG Stock Entry Detail",
		["lot", "parent", "item_variant"],
		"ppo_report_lot_stock_entry_item",
	)
	frappe.db.add_index(
		"FG Stock Entry",
		["posting_date", "consumed", "docstatus"],
		"ppo_report_inward_date_status",
	)
