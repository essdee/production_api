# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.finishing_plan import finishing_plan
from production_api import utils as production_utils


class TestFinishingPlan(FrappeTestCase):
	def test_packing_dpr_multiplies_set_quantities_but_not_pieces_per_box(self):
		ipd_doc = frappe._dict(
			name="IPD-SET",
			is_set_item=1,
			set_item_combination_details=[
				frappe._dict(set_item_attribute_value="Top"),
				frappe._dict(set_item_attribute_value="Bottom"),
				frappe._dict(set_item_attribute_value="Top"),
			],
		)
		packing = frappe._dict(
			sizes=["S"],
			size_pieces={"S": 100},
			pieces_per_box=5,
			dynamic_ratio_packing=False,
			total_boxes=20,
			total_pieces=100,
		)

		with (
			patch.object(
				finishing_plan.frappe,
				"get_all",
				return_value=[frappe._dict(name="GRN-SET", lot="LOT-SET")],
			),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				side_effect=["SET-ITEM", "IPD-SET"],
			),
			patch.object(
				finishing_plan.frappe,
				"get_cached_doc",
				return_value=ipd_doc,
			),
			patch.object(
				finishing_plan,
				"_get_packing_grn_report_values",
				return_value=packing,
			),
		):
			result = finishing_plan.get_finishing_packed_details("2026-08-10")

		row = result["data"][0]
		self.assertEqual(row["size_qty"], {"S": 200})
		self.assertEqual(row["total_pieces"], 200)
		self.assertEqual(row["pieces_per_box"], 5)
		self.assertEqual(row["total_boxes"], 40)

	def test_ironing_dpr_keeps_set_parts_with_same_colour_separate(self):
		dc_docs = {}
		for name, part in (("DC-TOP", "Top"), ("DC-BOTTOM", "Bottom")):
			doc = MagicMock()
			doc.name = name
			doc.lot = "LOT-SET"
			doc.item = "SET-ITEM"
			doc.production_detail = "IPD-SET"
			doc.items = part
			doc.get.side_effect = lambda fieldname, current_doc=doc: getattr(
				current_doc, fieldname
			)
			dc_docs[name] = doc

		def get_doc(doctype, name):
			if doctype == "Delivery Challan":
				return dc_docs[name]
			if doctype == "Lot":
				return SimpleNamespace(production_detail="IPD-SET")
			raise AssertionError((doctype, name))

		def fetch_item_details(items, _ipd, _lot):
			qty = 10 if items == "Top" else 8
			return [{
				"primary_attribute_values": ["S"],
				"items": [{
					"attributes": {"Colour": "Navy", "Part": items},
					"values": {"S": {"delivered_quantity": qty}},
				}],
			}]

		with (
			patch.object(
				production_utils.frappe.db,
				"get_single_value",
				return_value="Ironing",
			),
			patch.object(
				production_utils.frappe.db,
				"sql",
				side_effect=[
					[],
					[frappe._dict(name="DC-TOP"), frappe._dict(name="DC-BOTTOM")],
				],
			),
			patch.object(
				production_utils.frappe,
				"get_single",
				return_value=frappe._dict(
					default_packing_attribute="Colour",
					default_set_item_attribute="Wrong Global Part Attribute",
				),
			),
			patch.object(production_utils.frappe, "get_doc", side_effect=get_doc),
			patch.object(
				production_utils.frappe,
				"get_value",
				return_value=frappe._dict(
					is_set_item=1,
					set_item_attribute="Part",
				),
			),
			patch(
				"production_api.production_api.doctype.delivery_challan.delivery_challan.fetch_item_details",
				side_effect=fetch_item_details,
			),
		):
			result = production_utils.dc_dpr_report(date="2026-08-10")

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["attributes"], ["Colour", "Part"])
		rows_by_part = {row["part"]: row for row in result[0]["rows"]}
		self.assertEqual(set(rows_by_part), {"Top", "Bottom"})
		self.assertEqual(rows_by_part["Top"]["S"], 10)
		self.assertEqual(rows_by_part["Top"]["total_qty"], 10)
		self.assertEqual(rows_by_part["Bottom"]["S"], 8)
		self.assertEqual(rows_by_part["Bottom"]["total_qty"], 8)

	def _get_ocr_test_doc(self):
		return frappe._dict(
			lot="LOT-TEST",
			pieces_per_box=5,
			finishing_plan_details=[
				frappe._dict(
					item_variant="VARIANT-S",
					set_combination={"major_colour": "Blue"},
					cutting_qty=10,
					dc_qty=10,
					transferred_qty=0,
					ironing_excess=0,
					lot_transferred=0,
					delivered_quantity=10,
					return_qty=0,
					pack_return_qty=0,
					rejected_qty=0,
				),
			],
			finishing_plan_grn_details=[
				frappe._dict(item_variant="VARIANT-S", quantity=2, dispatched=1),
			],
			finishing_plan_reworked_details=[],
			finishing_old_lot_given_items=[],
			finishing_old_lot_received_items=[],
		)

	def _get_ocr_value(self, doctype, name, fields):
		if doctype == "Lot":
			return "IPD-TEST"
		if doctype == "Item Production Detail":
			return (0, "Colour", "Size", None)
		raise AssertionError((doctype, name, fields))

	def test_legacy_ocr_totals_include_packed_and_dispatched_boxes(self):
		doc = self._get_ocr_test_doc()
		packing_summary = frappe._dict(dynamic_ratio_packing=False, sizes={})
		with (
			patch.object(finishing_plan.frappe, "get_value", side_effect=self._get_ocr_value),
			patch.object(
				finishing_plan, "get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(
				finishing_plan, "get_finishing_packing_summary",
				return_value=packing_summary,
			),
			patch.object(
				finishing_plan.frappe, "get_cached_doc",
				return_value=frappe._dict(lot_order_details=[]),
			),
		):
			ocr = finishing_plan.get_ocr_details(doc)["Item"]

		packed_by_size = sum(row["packed_box"] for row in ocr["total"].values())
		dispatched_by_size = sum(
			row["dispatched_box"] for row in ocr["total"].values()
		)
		self.assertEqual(packed_by_size, 2)
		self.assertEqual(dispatched_by_size, 1)
		self.assertEqual(ocr["packed_box"], packed_by_size)
		self.assertEqual(ocr["dispatched_box"], dispatched_by_size)

	def test_dynamic_ocr_totals_use_physical_batch_box_totals(self):
		doc = self._get_ocr_test_doc()
		packing_summary = frappe._dict(
			dynamic_ratio_packing=True,
			total_packed_boxes=3,
			total_dispatched_boxes=2,
			sizes={"S": {"packed": 10, "dispatched": 5, "packed_boxes": 5, "dispatched_boxes": 4}},
		)
		with (
			patch.object(finishing_plan.frappe, "get_value", side_effect=self._get_ocr_value),
			patch.object(
				finishing_plan, "get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(
				finishing_plan, "get_finishing_packing_summary",
				return_value=packing_summary,
			),
			patch.object(
				finishing_plan.frappe, "get_cached_doc",
				return_value=frappe._dict(lot_order_details=[]),
			),
		):
			ocr = finishing_plan.get_ocr_details(doc)["Item"]

		self.assertEqual(ocr["packed_box"], packing_summary.total_packed_boxes)
		self.assertEqual(
			ocr["dispatched_box"], packing_summary.total_dispatched_boxes
		)

	def test_packing_quantities_are_rebuilt_after_fractional_grn_cancellation(self):
		doc = frappe.get_doc({
			"doctype": "Finishing Plan",
			"work_order": "WO-TEST",
			"lot": "LOT-TEST",
			"production_detail": "IPD-TEST",
			"finishing_plan_grn_details": [
				{"item_variant": "VARIANT-2T", "quantity": -0.333333333, "dispatched": 0},
				{"item_variant": "VARIANT-3T", "quantity": -0.333333333, "dispatched": 0},
			],
		})

		with patch.object(finishing_plan.frappe, "get_all", return_value=[]):
			finishing_plan.rebuild_finishing_packing_quantities(doc)

		self.assertEqual(
			[row.quantity for row in doc.finishing_plan_grn_details],
			[0, 0],
		)

	def test_migrated_legacy_boxes_and_dynamic_grn_rebuild_as_pieces(self):
		doc = frappe.get_doc({
			"doctype": "Finishing Plan",
			"work_order": "WO-TEST",
			"lot": "LOT-TEST",
			"production_detail": "IPD-TEST",
			"finishing_plan_grn_details": [
				{"item_variant": "VARIANT-S", "quantity": 15, "dispatched": 0},
			],
		})
		grns = [
			frappe._dict(
				name="GRN-LEGACY",
				packing_calculation_version=1,
				total_packing_boxes=60,
				total_packing_pieces=720,
			),
			frappe._dict(
				name="GRN-DYNAMIC",
				packing_calculation_version=2,
				total_packing_boxes=2,
				total_packing_pieces=10,
			),
		]
		items = {
			"GRN-LEGACY": [frappe._dict(item_variant="VARIANT-S", quantity=15)],
			"GRN-DYNAMIC": [frappe._dict(item_variant="VARIANT-S", quantity=10)],
		}

		def get_all(doctype, filters=None, **_kwargs):
			if doctype == "Goods Received Note":
				return grns
			if doctype == "Goods Received Note Item":
				return items[filters["parent"]]
			if doctype == "GRN Packing Batch":
				return []
			raise AssertionError(doctype)

		with (
			patch.object(finishing_plan.frappe, "get_all", side_effect=get_all),
			patch.object(finishing_plan.frappe, "get_cached_value", return_value="Size"),
			patch.object(finishing_plan, "get_variant_attr_details", return_value={"Size": "S"}),
		):
			finishing_plan.rebuild_finishing_packing_quantities(doc)

		self.assertEqual(doc.finishing_plan_grn_details[0].quantity, 190)

	def _source_lot(self):
		lot = SimpleNamespace(
			name="LOT-SOURCE",
			production_detail="IPD-SOURCE",
			item="SOURCE-ITEM",
			lot_order_details=[
				frappe._dict(
					item_variant="NAVY-S", quantity=10, cut_qty=12,
					set_combination={"major_colour": "Navy"},
				),
				frappe._dict(
					item_variant="RED-S", quantity=5, cut_qty=5,
					set_combination={"major_colour": "Red"},
				),
				frappe._dict(
					item_variant="NAVY-M", quantity=20, cut_qty=20,
					set_combination={"major_colour": "Navy"},
				),
			],
			items=[
				frappe._dict(item_variant="SIZE-S", qty=3),
				frappe._dict(item_variant="SIZE-M", qty=4),
			],
		)
		lot.save = MagicMock()
		return lot

	def _variant_attributes(self, variant):
		return {
			"NAVY-S": {"Colour": "Navy", "Size": "S"},
			"RED-S": {"Colour": "Red", "Size": "S"},
			"NAVY-M": {"Colour": "Navy", "Size": "M"},
			"SIZE-S": {"Size": "S"},
			"SIZE-M": {"Size": "M"},
		}[variant]

	def test_alternative_conversion_reduces_source_lot_and_rebuilds_totals(self):
		lot = self._source_lot()
		with (
			patch.object(finishing_plan.frappe.db, "sql"),
			patch.object(finishing_plan.frappe, "get_doc", return_value=lot),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				return_value=(5, "Size", "Colour"),
			),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				side_effect=self._variant_attributes,
			),
		):
			finishing_plan._reduce_source_lot_quantity(
				"LOT-SOURCE",
				[
					{"colour": "Navy", "size": "S", "qty": 3},
					{"colour": "Navy", "size": "M", "qty": 5},
				],
			)

		self.assertEqual(
			[row.quantity for row in lot.lot_order_details],
			[7, 5, 15],
		)
		self.assertEqual(
			[row.cut_qty for row in lot.lot_order_details],
			[12, 5, 20],
		)
		self.assertEqual([row.qty for row in lot.items], [2.4, 3])
		self.assertEqual(lot.total_order_quantity, 27)
		self.assertEqual(lot.total_quantity, 5.4)
		lot.save.assert_called_once_with(ignore_permissions=True)

	def test_source_lot_planned_quantity_clamps_at_zero_for_excess_cutting(self):
		lot = self._source_lot()
		with (
			patch.object(finishing_plan.frappe.db, "sql"),
			patch.object(finishing_plan.frappe, "get_doc", return_value=lot),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				return_value=(5, "Size", "Colour"),
			),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				side_effect=self._variant_attributes,
			),
		):
			finishing_plan._reduce_source_lot_quantity(
				"LOT-SOURCE",
				[{"colour": "Navy", "size": "S", "qty": 12}],
			)

		self.assertEqual(
			[row.quantity for row in lot.lot_order_details],
			[0, 5, 20],
		)
		self.assertEqual(
			[row.cut_qty for row in lot.lot_order_details],
			[12, 5, 20],
		)
		self.assertEqual([row.qty for row in lot.items], [1, 4])
		self.assertEqual(lot.total_order_quantity, 25)
		self.assertEqual(lot.total_quantity, 5)
		lot.save.assert_called_once_with(ignore_permissions=True)

	def test_excess_transfer_uses_full_quantity_and_stops_when_stock_issue_fails(self):
		source_fp = frappe._dict(
			item="SOURCE-ITEM",
			lot="LOT-SOURCE",
			finishing_plan_details=[],
		)
		source_fp.set = MagicMock()
		source_fp.save = MagicMock()
		wo_doc = frappe._dict(
			item="TARGET-ITEM",
			lot="LOT-TARGET",
			supplier="SUPPLIER-1",
		)
		fp_key = (
			"SOURCE-VARIANT-S",
			(("major_colour", "Navy"),),
		)
		fp_dict = {fp_key: {"transferred_qty": 0}}

		def get_value(doctype, name, fieldname):
			if doctype == "Item":
				return "Pieces"
			if doctype == "Item Variant":
				return "TARGET-ITEM"
			raise AssertionError((doctype, name, fieldname))

		stock_error = frappe.ValidationError("Insufficient source stock")
		with (
			patch.object(
				finishing_plan.frappe.db,
				"get_single_value",
				return_value="Accepted",
			),
			patch.object(finishing_plan.frappe, "get_value", side_effect=get_value),
			patch.object(finishing_plan, "get_finishing_plan_dict", return_value=fp_dict),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				return_value={"Colour": "Navy", "Size": "S"},
			),
			patch.object(
				finishing_plan,
				"get_or_create_variant",
				return_value="SOURCE-VARIANT-S",
			),
			patch(
				"production_api.mrp_stock.doctype.stock_summary.stock_summary.create_bulk_stock_entry",
				side_effect=stock_error,
			) as create_stock,
		):
			with self.assertRaisesRegex(
				frappe.ValidationError,
				"Insufficient source stock",
			):
				finishing_plan._apply_transfer_delta(
					source_fp,
					wo_doc,
					[{
						"item_variant": "TARGET-VARIANT-S",
						"set_combination": {"major_colour": "Navy"},
						"qty": 120,
					}],
				)

		issue_items = create_stock.call_args.args[1]
		self.assertEqual(issue_items[0]["bal_qty"], 120)
		self.assertEqual(create_stock.call_args.args[2], "Material Issue")
		self.assertEqual(fp_dict[fp_key]["transferred_qty"], 120)
		source_fp.set.assert_not_called()
		source_fp.save.assert_not_called()
