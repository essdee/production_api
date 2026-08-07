# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.finishing_plan import finishing_plan


class TestFinishingPlan(FrappeTestCase):
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
