# Copyright (c) 2024, Essdee and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFGStockEntry(FrappeTestCase):

	def _sample_master_data(self):
		"""Pick existing master records on the site for a minimal FG Stock Entry."""
		item_variant = frappe.db.get_value("Item Variant", {}, "name")
		uom = frappe.db.get_value("UOM", {"name": "Pieces"}, "name") or frappe.db.get_value("UOM", {}, "name")
		lot = frappe.db.get_value("Lot", {}, "name")
		warehouse = frappe.db.get_value("Supplier", {}, "name")
		supplier = warehouse
		if not all([item_variant, uom, lot, warehouse]):
			self.skipTest("Required master data (Item Variant / UOM / Lot / Supplier) missing on site.")
		return item_variant, uom, lot, warehouse, supplier

	def test_create_fg_ste_persists_source_stock_entry_and_quantity(self):
		"""create_FG_ste must persist parent stock_entry and per-row stock_entry_quantity."""
		from production_api.mrp_stock.doctype.fg_stock_entry.fg_stock_entry import create_FG_ste

		item_variant, uom, lot, warehouse, supplier = self._sample_master_data()

		items_list = [
			{"item_variant": item_variant, "qty": 7, "uom": uom, "row": 0, "col": 0,
			 "stock_entry_quantity": 10},
		]

		fg_ste_name = create_FG_ste(
			lot=lot,
			received_by="Tester",
			dc_number="DC-TEST-001",
			warehouse=warehouse,
			posting_date="2026-05-05",
			posting_time="10:00:00",
			items_list=items_list,
			comments="",
			created_user="Administrator",
			consumed=False,
			supplier=supplier,
			stock_entry=None,
		)

		doc = frappe.get_doc("FG Stock Entry", fg_ste_name)
		self.assertIsNone(doc.stock_entry)
		self.assertEqual(len(doc.items), 1)
		self.assertEqual(doc.items[0].qty, 7)
		self.assertEqual(doc.items[0].stock_entry_quantity, 10)
