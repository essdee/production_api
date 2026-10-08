# Copyright (c) 2023, Essdee and Contributors
# See license.txt

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.doctype.stock_entry import stock_entry


class TestDynamicFinishingDispatch(FrappeTestCase):
	def test_ratio_dispatch_print_renders_only_colour_box_totals(self):
		print_format_path = (
			Path(__file__).parents[2]
			/ "print_format"
			/ "ratio_dispatch_colour_slip"
			/ "ratio_dispatch_colour_slip.json"
		)
		self.assertTrue(
			print_format_path.exists(),
			"Ratio Dispatch Colour Slip print format is missing",
		)
		print_format = json.loads(print_format_path.read_text())
		doc = SimpleNamespace(
			name="STE-PRINT",
			docstatus=1,
			posting_date="2026-10-08",
			from_warehouse=None,
			to_warehouse=None,
			transfer_supplier=None,
			vehicle_no=None,
			terms_and_condition=None,
			comments=None,
			get_formatted=lambda fieldname: "08-10-2026"
			if fieldname == "posting_date"
			else "",
		)
		html = frappe.render_template(print_format["html"], {
			"doc": doc,
			"letter_head": None,
			"no_letterhead": True,
			"footer": None,
			"get_supplier_address_display": lambda _supplier: "",
			"get_ratio_dispatch_print_data": lambda _name: [{
				"finishing_plan": "FP-1",
				"lot": "LOT-1",
				"item": "ITEM-1",
				"colours": [
					{"colour": "Navy", "boxes": 5},
					{"colour": "White", "boxes": 1},
				],
				"total_boxes": 6,
			}],
		})

		self.assertIn("Colour", html)
		self.assertIn("Boxes", html)
		self.assertIn("Navy", html)
		self.assertIn("White", html)
		self.assertIn("LOT-1", html)
		self.assertIn("ITEM-1", html)
		self.assertNotIn("Size", html)
		self.assertNotIn("Pieces", html)

	def get_ratio_print_data(self, stock_entry_name):
		self.assertTrue(
			hasattr(stock_entry, "get_ratio_dispatch_print_data"),
			"Ratio dispatch print-data helper is missing",
		)
		return stock_entry.get_ratio_dispatch_print_data(stock_entry_name)

	def test_ratio_print_groups_direct_finishing_plan_batches_by_colour(self):
		dispatch = SimpleNamespace(
			name="STE-DIRECT",
			against="Finishing Plan",
			against_id="FP-1",
			packing_batch_dispatch_json=frappe.as_json([
				{"colour": "Navy", "box_quantity": 2},
				{"colour": "White", "box_quantity": 1},
				{"colour": "Navy", "box_quantity": 3},
			]),
		)

		with (
			patch.object(stock_entry.frappe, "get_doc", return_value=dispatch),
			patch.object(
				stock_entry.frappe,
				"get_cached_value",
				side_effect=self.ratio_print_cached_value,
			),
		):
			result = self.get_ratio_print_data(dispatch.name)

		self.assertEqual(result, [{
			"finishing_plan": "FP-1",
			"lot": "LOT-1",
			"item": "ITEM-1",
			"colours": [
				{"colour": "Navy", "boxes": 5},
				{"colour": "White", "boxes": 1},
			],
			"total_boxes": 6,
		}])

	def test_ratio_print_keeps_finishing_plan_dispatch_items_separate(self):
		dispatch = SimpleNamespace(
			name="STE-FPD",
			against="Finishing Plan Dispatch",
			against_id="FPD-1",
			packing_batch_dispatch_json=frappe.as_json([
				{"finishing_plan": "FP-1", "colour": "Navy", "box_quantity": 4},
				{"finishing_plan": "FP-2", "colour": "Black", "box_quantity": 2},
				{"finishing_plan": "FP-2", "colour": "Black", "box_quantity": 3},
			]),
		)

		with (
			patch.object(stock_entry.frappe, "get_doc", return_value=dispatch),
			patch.object(
				stock_entry.frappe,
				"get_cached_value",
				side_effect=self.ratio_print_cached_value,
			),
		):
			result = self.get_ratio_print_data(dispatch.name)

		self.assertEqual(result, [
			{
				"finishing_plan": "FP-1",
				"lot": "LOT-1",
				"item": "ITEM-1",
				"colours": [{"colour": "Navy", "boxes": 4}],
				"total_boxes": 4,
			},
			{
				"finishing_plan": "FP-2",
				"lot": "LOT-2",
				"item": "ITEM-2",
				"colours": [{"colour": "Black", "boxes": 5}],
				"total_boxes": 5,
			},
		])

	def test_ratio_print_excludes_non_attribute_mapped_ipd(self):
		dispatch = SimpleNamespace(
			name="STE-NON-RATIO",
			against="Finishing Plan",
			against_id="FP-1",
			packing_batch_dispatch_json=frappe.as_json([
				{"colour": "Navy", "box_quantity": 4},
			]),
		)

		def cached_value(doctype, name, _fields, as_dict=False):
			if doctype == "Finishing Plan":
				return frappe._dict(
					lot="LOT-1", item="ITEM-1", production_detail="IPD-1"
				)
			if doctype == "Item Production Detail":
				return frappe._dict(
					packing_mode="Size Ratio Packing",
					based_on_other_attribute_mapping=0,
				)
			raise AssertionError((doctype, name, as_dict))

		with (
			patch.object(stock_entry.frappe, "get_doc", return_value=dispatch),
			patch.object(
				stock_entry.frappe,
				"get_cached_value",
				side_effect=cached_value,
			),
		):
			result = self.get_ratio_print_data(dispatch.name)

		self.assertEqual(result, [])

	@staticmethod
	def ratio_print_cached_value(doctype, name, _fields, as_dict=False):
		if doctype == "Finishing Plan":
			index = name.removeprefix("FP-")
			return frappe._dict(
				lot=f"LOT-{index}",
				item=f"ITEM-{index}",
				production_detail=f"IPD-{index}",
			)
		if doctype == "Item Production Detail":
			return frappe._dict(
				packing_mode="Size Ratio Packing",
				based_on_other_attribute_mapping=1,
			)
		raise AssertionError((doctype, name, as_dict))

	def test_dynamic_finishing_dispatch_accumulates_pieces_from_every_batch(self):
		fp_dispatch = SimpleNamespace(
			name="FPD-TEST",
			finishing_plan_dispatch_items=[
				SimpleNamespace(
					against_id="FP-SELECTED",
					against_id_detail="FP-GRN-ROW-1",
					item_variant="VARIANT-S",
					quantity=25,
					packing_source="batch",
				),
			],
			stock_entry=None,
			save=MagicMock(),
		)
		fp_plan = SimpleNamespace(name="FP-SELECTED", save=MagicMock())
		dispatch = SimpleNamespace(
			purpose="Material Issue",
			against="Finishing Plan Dispatch",
			against_id=fp_dispatch.name,
			name="STE-TEST",
			docstatus=1,
			packing_batch_dispatch_json=frappe.as_json([
				{
					"finishing_plan": fp_plan.name,
					"batch_row": "BATCH-ROW-1",
					"box_quantity": 2,
					"size_pieces": {"S": 10},
				},
				{
					"finishing_plan": fp_plan.name,
					"batch_row": "BATCH-ROW-2",
					"box_quantity": 3,
					"size_pieces": {"S": 15},
				},
			]),
		)

		def get_doc(doctype, _name):
			if doctype == "Finishing Plan Dispatch":
				return fp_dispatch
			if doctype == "Finishing Plan":
				return fp_plan
			raise AssertionError(doctype)

		def get_value(doctype, _filters, _fieldname, **_kwargs):
			if doctype == "GRN Packing Batch":
				return 0
			if doctype == "Finishing Plan GRN Detail":
				return frappe._dict(
					name="FP-GRN-ROW-1",
					parent=fp_plan.name,
					dispatched=0,
				)
			raise AssertionError(doctype)

		with (
			patch.object(stock_entry.frappe, "get_doc", side_effect=get_doc),
			patch.object(stock_entry.frappe.db, "get_value", side_effect=get_value),
			patch.object(stock_entry.frappe.db, "set_value"),
			patch.object(stock_entry, "record_finishing_dispatch_log") as record_log,
			patch.object(stock_entry, "apply_auto_fp_status"),
			patch.object(stock_entry, "rebuild_finishing_packing_quantities"),
		):
			stock_entry.StockEntry.update_finishing_plan(dispatch)

		record_log.assert_called_once_with(
			fp_plan,
			dispatch,
			5,
			source_doctype="Finishing Plan Dispatch",
			source_name=fp_dispatch.name,
			dispatch_pieces=25,
		)


class TestStockEntry(FrappeTestCase):
	def test_material_receipt_rate_is_scoped_to_destination_and_lot(self):
		class Row(SimpleNamespace):
			def set(self, fieldname, value):
				setattr(self, fieldname, value)

		row = Row(
			item="VARIANT-1",
			qty=2,
			rate=0,
			received_type="Accepted",
			lot="LOT-1",
			uom="Nos",
			table_index=0,
			row_index=0,
		)
		doc = SimpleNamespace(
			purpose="Material Receipt",
			to_warehouse="S-0171",
			posting_date="2026-08-13",
			posting_time="10:00:00",
			items=[row],
			validate_item=MagicMock(),
			precision=lambda _field, _row: 9,
		)

		with (
			patch.object(stock_entry, "get_stock_balance", return_value=(10, 55.25)) as get_balance,
			patch.object(
				stock_entry,
				"get_uom_details",
				return_value={"stock_uom": "Nos", "conversion_factor": 1},
			),
			patch.object(stock_entry, "get_item_variant_price", return_value=None),
		):
			stock_entry.StockEntry.validate_data(doc)

		get_balance.assert_called_once_with(
			"VARIANT-1",
			"S-0171",
			"Accepted",
			"2026-08-13",
			"10:00:00",
			with_valuation_rate=True,
			lot="LOT-1",
			uom="Nos",
		)
		self.assertEqual(row.rate, 55.25)

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
		expected_keys = {
			"item_variant", "qty", "uom", "stock_qty", "stock_uom",
			"conversion_factor", "rate", "received_type", "lot",
			"row_index", "table_index",
		}
		self.assertEqual(expected_keys, set(first.keys()))

	def test_get_stock_entry_for_fg_load_rejects_draft(self):
		from production_api.api.stock import get_stock_entry_for_fg_load

		draft_name = self._existing_draft_stock_entry()
		with self.assertRaises(frappe.ValidationError):
			get_stock_entry_for_fg_load(draft_name)
