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

	def test_source_lot_is_not_partially_changed_when_any_cell_is_insufficient(self):
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
			with self.assertRaisesRegex(
				frappe.ValidationError,
				"only 10 available",
			):
				finishing_plan._reduce_source_lot_quantity(
					"LOT-SOURCE",
					[
						{"colour": "Red", "size": "S", "qty": 1},
						{"colour": "Navy", "size": "S", "qty": 11},
					],
				)

		self.assertEqual(
			[row.quantity for row in lot.lot_order_details],
			[10, 5, 20],
		)
		lot.save.assert_not_called()
