# Copyright (c) 2026, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.cutting_bulk_lay_sheets import (
	cutting_bulk_lay_sheets as bulk_laysheets,
)


class TestCuttingBulkLaySheets(FrappeTestCase):
	def test_create_bulk_lot_transfer_links_one_transfer_to_every_row(self):
		rows = [
			frappe._dict(
				name="CBLS-ROW-1", lot="LOT-SPLIT-1", cutting_laysheet="CLS-1",
				lot_transfer=None, delivery_challan=None,
			),
			frappe._dict(
				name="CBLS-ROW-2", lot="LOT-SPLIT-2", cutting_laysheet="CLS-2",
				lot_transfer=None, delivery_challan=None,
			),
		]
		bulk = frappe._dict(
			name="CBLS-TEST-1", main_lot="LOT-MAIN", from_location="LOCATION-1",
			posting_date="2026-08-21", lot_details=rows,
		)
		bulk._validate_lot_rows = MagicMock()
		laysheets = {
			"CLS-1": frappe._dict(cutting_laysheet_bundles=[1], status="Bundles Generated"),
			"CLS-2": frappe._dict(cutting_laysheet_bundles=[1], status="Bundles Generated"),
		}
		transfer = MagicMock()
		transfer.name = "LT-BULK-1"
		transfer.flags = frappe._dict()

		def build_items(laysheet, main_lot, target_lot, warehouse, received_type):
			return [{
				"item": f"FABRIC-{target_lot}", "qty": 5, "uom": "Kg",
				"from_lot": main_lot, "to_lot": target_lot,
				"warehouse": warehouse, "received_type": received_type,
			}]

		with (
			patch.object(bulk_laysheets, "get_bulk_doc", return_value=bulk),
			patch.object(bulk_laysheets, "get_shared_bulk_transfer_name", return_value=None),
			patch.object(bulk_laysheets.frappe.db, "get_single_value", return_value="Accepted"),
			patch.object(
				bulk_laysheets.frappe, "get_doc",
				side_effect=lambda doctype, name: laysheets[name],
			),
			patch.object(bulk_laysheets, "build_lot_transfer_items", side_effect=build_items),
			patch.object(bulk_laysheets, "nowtime", return_value="12:00:00"),
			patch.object(bulk_laysheets.frappe, "get_all", return_value=[]),
			patch.object(bulk_laysheets, "validate_source_stock") as validate_stock,
			patch.object(bulk_laysheets.frappe, "new_doc", return_value=transfer),
			patch.object(bulk_laysheets.frappe.db, "set_value") as set_value,
			patch.object(bulk_laysheets, "refresh_bulk_status") as refresh_status,
		):
			result = bulk_laysheets.create_bulk_lot_transfer(bulk.name)

		self.assertEqual(result, transfer.name)
		self.assertIsNone(transfer.cutting_bulk_lay_sheet_detail)
		self.assertEqual(transfer.set.call_args.args[0], "items")
		self.assertEqual(len(transfer.set.call_args.args[1]), 2)
		self.assertEqual(set_value.call_count, 2)
		validate_stock.assert_called_once()
		transfer.save.assert_called_once_with()
		refresh_status.assert_called_once_with(bulk.name)

	def test_submit_bulk_lot_transfer_uses_one_transfer_for_all_rows(self):
		bulk = frappe._dict(
			name="CBLS-TEST-1",
			lot_details=[
				frappe._dict(name="CBLS-ROW-1", lot_transfer="LT-BULK-1"),
				frappe._dict(name="CBLS-ROW-2", lot_transfer="LT-BULK-1"),
			],
		)
		transfer = MagicMock()
		transfer.name = "LT-BULK-1"
		transfer.docstatus = 0
		transfer.cutting_bulk_lay_sheet = bulk.name

		with (
			patch.object(bulk_laysheets, "get_bulk_doc", return_value=bulk),
			patch.object(bulk_laysheets, "get_docstatus", return_value=0),
			patch.object(bulk_laysheets.frappe, "get_doc", return_value=transfer),
			patch.object(bulk_laysheets, "refresh_bulk_status") as refresh_status,
		):
			result = bulk_laysheets.submit_bulk_lot_transfer(bulk.name)

		transfer.submit.assert_called_once_with()
		refresh_status.assert_called_once_with(bulk.name)
		self.assertEqual(result, transfer.name)

	def test_laysheet_editor_data_includes_generated_bundles(self):
		class ChildRow:
			def __init__(self, values):
				self.values = values

			def as_dict(self):
				return self.values

		entry = frappe._dict(lot_transfer=None)
		laysheet = frappe._dict(
			name="CLS-TEST-1",
			cutting_plan="CP-TEST-1",
			cutting_order=None,
			cutting_marker="CM-TEST-1",
			is_manual_entry=0,
			is_set_item=0,
			status="Bundles Generated",
			docstatus=0,
			cutting_laysheet_details=[],
			cutting_laysheet_accessory_details=[],
			cutting_laysheet_manual_items=[],
			cutting_laysheet_bundles=[
				ChildRow({"bundle_no": 1, "part": "Front", "quantity": 12})
			],
		)
		with (
			patch.object(bulk_laysheets, "get_entry_for_laysheet", return_value=entry),
			patch.object(bulk_laysheets.frappe, "get_doc", return_value=laysheet),
		):
			data = bulk_laysheets.get_laysheet_editor_data("CBLS-TEST-1", laysheet.name)

		self.assertEqual(
			data["bundles"],
			[{"bundle_no": 1, "part": "Front", "quantity": 12}],
		)

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

	def test_source_stock_check_combines_all_split_lot_quantities(self):
		items = [
			{
				"item": "FABRIC-BEIGE-72",
				"qty": 60,
				"uom": "Kg",
				"warehouse": "CUTTING-LOCATION",
				"received_type": "Accepted",
			},
			{
				"item": "FABRIC-BEIGE-72",
				"qty": 50,
				"uom": "Kg",
				"warehouse": "CUTTING-LOCATION",
				"received_type": "Accepted",
			},
		]
		with (
			patch(
				"production_api.mrp_stock.utils.get_stock_balance",
				return_value=100,
			),
			self.assertRaisesRegex(frappe.ValidationError, "required 110"),
		):
			bulk_laysheets.validate_source_stock(items, "LOT-MAIN")

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
