# Copyright (c) 2023, Essdee and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestStockEntry(FrappeTestCase):

	def _existing_submitted_stock_entry(self):
		name = frappe.db.get_value("Stock Entry", {"docstatus": 1}, "name")
		if not name:
			self.skipTest("No submitted Stock Entry available on site for test fixture.")
		return name

	def _existing_draft_stock_entry(self):
		name = frappe.db.get_value("Stock Entry", {"docstatus": 0}, "name")
		if not name:
			self.skipTest("No draft Stock Entry available on site for test fixture.")
		return name

	def test_search_submitted_stock_entries_returns_only_submitted(self):
		from production_api.api.stock import search_submitted_stock_entries

		submitted_name = self._existing_submitted_stock_entry()

		results = search_submitted_stock_entries(txt="", limit=20)
		self.assertIsInstance(results, list)
		names = [r["name"] for r in results]
		self.assertIn(submitted_name, names)

		for r in results:
			self.assertEqual(frappe.db.get_value("Stock Entry", r["name"], "docstatus"), 1)

	def test_get_stock_entry_for_fg_load_returns_mapped_items(self):
		from production_api.api.stock import get_stock_entry_for_fg_load

		submitted_name = self._existing_submitted_stock_entry()
		result = get_stock_entry_for_fg_load(submitted_name)

		self.assertEqual(result["stock_entry"], submitted_name)
		self.assertGreater(len(result["items"]), 0)
		first = result["items"][0]
		expected_keys = {"item_variant", "qty", "uom", "stock_qty", "stock_uom",
						 "conversion_factor", "rate", "received_type"}
		self.assertEqual(expected_keys, set(first.keys()))

	def test_get_stock_entry_for_fg_load_rejects_draft(self):
		from production_api.api.stock import get_stock_entry_for_fg_load

		draft_name = self._existing_draft_stock_entry()
		with self.assertRaises(frappe.ValidationError):
			get_stock_entry_for_fg_load(draft_name)
