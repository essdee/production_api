"""Enable stock for yarn Items on sites that already ran the colour migration."""

import frappe

from production_api.patches.v1_0.consolidate_yarn_items_by_colour import (
	ATTRIBUTE_ONLY_ITEMS,
	TARGET_SITE,
	YARN_ITEM_GROUPS,
)


def execute():
	if frappe.local.site != TARGET_SITE:
		return

	item_names = list(YARN_ITEM_GROUPS) + list(ATTRIBUTE_ONLY_ITEMS)
	for item in frappe.get_all(
		"Item",
		filters={"name": ["in", item_names]},
		fields=["name", "is_stock_item"],
	):
		if not item.is_stock_item:
			frappe.db.set_value("Item", item.name, "is_stock_item", 1)
			frappe.clear_document_cache("Item", item.name)
