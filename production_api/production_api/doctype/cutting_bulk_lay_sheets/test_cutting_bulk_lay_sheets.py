# Copyright (c) 2026, Essdee and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.cutting_bulk_lay_sheets import (
	cutting_bulk_lay_sheets as bulk_laysheets,
)


class TestCuttingBulkLaySheets(FrappeTestCase):
	def test_transfer_items_consolidate_cloth_and_accessory_by_variant(self):
		laysheet = frappe._dict(
			cutting_laysheet_details=[
				frappe._dict(cloth_item_variant="FABRIC-BEIGE-72", weight=40.125),
				frappe._dict(cloth_item_variant="FABRIC-BEIGE-72", weight=10.125),
			],
			cutting_laysheet_accessory_details=[
				frappe._dict(cloth_item_variant="RIB-BEIGE-33", weight=4.5),
			],
		)

		def get_cached_value(doctype, name, fieldname):
			if doctype == "Item Variant":
				return {
					"FABRIC-BEIGE-72": "FABRIC",
					"RIB-BEIGE-33": "RIB",
				}[name]
			if doctype == "Item":
				return "Kg"
			raise AssertionError((doctype, name, fieldname))

		with patch.object(
			bulk_laysheets.frappe,
			"get_cached_value",
			side_effect=get_cached_value,
		):
			items = bulk_laysheets.build_lot_transfer_items(
				laysheet,
				"LOT-MAIN",
				"LOT-SPLIT-1",
				"CUTTING-LOCATION",
				"Accepted",
			)

		self.assertEqual(len(items), 2)
		self.assertEqual(
			{row["item"]: row["qty"] for row in items},
			{"FABRIC-BEIGE-72": 50.25, "RIB-BEIGE-33": 4.5},
		)
		self.assertTrue(all(row["from_lot"] == "LOT-MAIN" for row in items))
		self.assertTrue(all(row["to_lot"] == "LOT-SPLIT-1" for row in items))
		self.assertTrue(all(row["warehouse"] == "CUTTING-LOCATION" for row in items))

	def test_source_stock_check_includes_other_draft_transfers(self):
		items = [
			{
				"item": "FABRIC-BEIGE-72",
				"qty": 45,
				"uom": "Kg",
				"warehouse": "CUTTING-LOCATION",
				"received_type": "Accepted",
			}
		]
		with (
			patch(
				"production_api.mrp_stock.utils.get_stock_balance",
				return_value=100,
			),
			self.assertRaisesRegex(frappe.ValidationError, "required 105"),
		):
			bulk_laysheets.validate_source_stock(
				items,
				"LOT-MAIN",
				reserved={"FABRIC-BEIGE-72": 60},
			)

	def test_cutting_plan_stock_is_checked_after_dc(self):
		laysheet = frappe._dict(
			cutting_plan="CP-SPLIT-1",
			cutting_laysheet_details=[
				frappe._dict(
					colour="Beige",
					cloth_type="Terry",
					actual_dia="72 Dia",
					weight=30,
					balance_weight=2,
				)
			],
			cutting_laysheet_accessory_details=[],
		)
		plan = frappe._dict(
			cutting_plan_cloth_details=[
				frappe._dict(
					colour="Beige",
					cloth_type="Terry",
					dia="72 Dia",
					weight=25,
					used_weight=0,
				)
			]
		)
		with (
			patch.object(bulk_laysheets.frappe, "get_doc", return_value=plan),
			self.assertRaisesRegex(frappe.ValidationError, "required 28.0 Kg, available 25.0 Kg"),
		):
			bulk_laysheets.validate_cutting_plan_stock(laysheet)
