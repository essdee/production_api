# Copyright (c) 2026, Essdee and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.doctype.stock_update.stock_update import StockUpdate


class TestStockUpdate(FrappeTestCase):
	def test_submit_updates_ledger_and_creates_repost_action(self):
		doc = frappe.new_doc("Stock Update")

		with (
			patch.object(StockUpdate, "update_stock_ledger") as update_stock_ledger,
			patch.object(StockUpdate, "make_repost_action") as make_repost_action,
		):
			doc.on_submit()

		update_stock_ledger.assert_called_once_with()
		make_repost_action.assert_called_once_with()

	def test_cancel_updates_ledger_and_creates_repost_action(self):
		doc = frappe.new_doc("Stock Update")

		with (
			patch.object(StockUpdate, "update_stock_ledger") as update_stock_ledger,
			patch.object(StockUpdate, "make_repost_action") as make_repost_action,
		):
			doc.on_cancel()

		update_stock_ledger.assert_called_once_with()
		make_repost_action.assert_called_once_with()
		self.assertEqual(
			doc.ignore_linked_doctypes,
			("Stock Ledger Entry", "Repost Item Valuation"),
		)

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
