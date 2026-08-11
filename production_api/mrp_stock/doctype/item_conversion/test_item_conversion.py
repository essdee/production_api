# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.mrp_stock.doctype.item_conversion.item_conversion import (
	ItemConversion,
	get_item_conversion_valuation_rate,
)


class TestItemConversion(FrappeTestCase):
	def test_large_target_quantity_retains_precise_rate_and_matching_value(self):
		doc = frappe.new_doc("Item Conversion")
		doc.from_item = "FROM ITEM"
		doc.to_item = "TO ITEM"
		doc.warehouse = "Test Warehouse"
		doc.append(
			"from_items",
			{
				"item": "FROM VARIANT",
				"lot": "Test Lot",
				"qty": 300,
				"rate": 34,
				"uom": "Nos",
			},
		)
		doc.append(
			"to_items",
			{
				"item": "TO VARIANT",
				"lot": "Test Lot",
				"qty": 76500,
				"rate": 0,
				"uom": "Nos",
			},
		)

		module = "production_api.mrp_stock.doctype.item_conversion.item_conversion"
		with patch.object(
			ItemConversion,
			"validate_item",
			side_effect=["FROM ITEM", "TO ITEM"],
		), patch.object(
			ItemConversion,
			"get_existing_valuation_rate",
			return_value=34,
		), patch(
			f"{module}.get_uom_details",
			return_value={"stock_uom": "Nos", "conversion_factor": 1},
		):
			doc.validate()

		doc.validate_valuation_match()

		self.assertEqual(doc.to_items[0].rate, 0.133333333)
		self.assertEqual(doc.to_items[0].stock_uom_rate, 0.133333333)
		self.assertEqual(doc.from_total_amount, 10200)
		self.assertEqual(doc.to_total_amount, 10200)
		self.assertEqual(doc.difference_amount, 0)

	def test_valuation_rate_api_does_not_round_to_paise(self):
		with patch(
			"production_api.mrp_stock.doctype.item_conversion.item_conversion.get_variant",
			return_value="FROM VARIANT",
		), patch(
			"production_api.mrp_stock.doctype.item_conversion.item_conversion.get_stock_balance",
			return_value=(100, 0.123456789),
		):
			result = get_item_conversion_valuation_rate(
				item="FROM ITEM",
				warehouse="Test Warehouse",
			)

		self.assertEqual(result["rate"], 0.123456789)

	def test_conversion_requires_exactly_one_from_and_to_row(self):
		doc = frappe.new_doc("Item Conversion")
		doc.append("from_items", {"item": "FROM-1"})
		doc.append("from_items", {"item": "FROM-2"})
		doc.append("to_items", {"item": "TO-1"})

		with self.assertRaisesRegex(
			frappe.ValidationError,
			"exactly one From Item row",
		):
			doc.validate_single_item_rows()

		doc.set("from_items", [])
		doc.append("from_items", {"item": "FROM-1"})
		doc.append("to_items", {"item": "TO-2"})

		with self.assertRaisesRegex(
			frappe.ValidationError,
			"exactly one To Item row",
		):
			doc.validate_single_item_rows()

	def test_item_conversion_ui_uses_precise_rates(self):
		component = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Stock",
				"ItemConversion",
				"ItemConversion.vue",
			)
		).read_text()

		self.assertNotIn("round_paise", component)
		self.assertIn(
			"to_number(value.qty) * to_number(value.rate)",
			component,
		)
		self.assertIn("function auto_balance_single_to_rate()", component)
		self.assertIn(
			"from_total.value / to_number(target_values[0].qty)",
			component,
		)
		self.assertIn(
			"Rate is calculated automatically when there is one target row.",
			component,
		)
		self.assertIn(':validate="validate_single_selection"', component)
		self.assertIn("function validate_single_selection(item)", component)
		self.assertIn(
			"get_quantity_values(from_items.value).length < 1",
			component,
		)
		self.assertIn(
			"get_quantity_values(to_items.value).length < 1",
			component,
		)
