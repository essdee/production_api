# Copyright (c) 2026, Essdee and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestStockUpdate(FrappeTestCase):
	def test_stock_update_ledger_qty_uses_stock_uom_qty_for_reduce(self):
		doc = frappe.new_doc("Stock Update")
		doc.update_type = "Reduce"
		doc.warehouse = "Test Warehouse"
		doc.posting_date = "2026-04-17"
		doc.posting_time = "19:34:17"
		doc.append(
			"stock_update_details",
			{
				"item_variant": "Test Item Variant",
				"lot": "Test Lot",
				"received_type": "Accepted",
				"uom": "Box",
				"stock_uom": "Pieces",
				"conversion_factor": 5,
				"update_diff_qty": 40,
				"stock_qty": 200,
				"rate": 500,
			},
		)

		sl_entries = doc.get_sl_entries()

		self.assertEqual(sl_entries[0].qty, -200)
		self.assertEqual(sl_entries[0].uom, "Pieces")

	def test_stock_update_ledger_qty_and_rate_use_stock_uom_for_add(self):
		doc = frappe.new_doc("Stock Update")
		doc.update_type = "Add"
		doc.warehouse = "Test Warehouse"
		doc.posting_date = "2026-04-17"
		doc.posting_time = "19:34:17"
		doc.append(
			"stock_update_details",
			{
				"item_variant": "Test Item Variant",
				"lot": "Test Lot",
				"received_type": "Accepted",
				"uom": "Box",
				"stock_uom": "Pieces",
				"conversion_factor": 5,
				"update_diff_qty": 40,
				"stock_qty": 200,
				"rate": 500,
			},
		)

		sl_entries = doc.get_sl_entries()

		self.assertEqual(sl_entries[0].qty, 200)
		self.assertEqual(sl_entries[0].uom, "Pieces")
		self.assertEqual(sl_entries[0].rate, 100)
