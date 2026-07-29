# Copyright (c) 2026, Essdee and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.essdee_production.doctype.lot import cloth_program


class TestClothProgramPreview(FrappeTestCase):
	def setUp(self):
		self.lot = frappe._dict(
			name="_Test Cloth Program Lot",
			lot_order_details=[
				frappe._dict(item_variant="RED-S", quantity=10),
				frappe._dict(item_variant="RED-M", quantity=5),
			],
		)
		self.ipd = frappe._dict(
			name="_Test Garment IPD",
			dependent_attribute=None,
			cloth_detail=[
				frappe._dict(name1="Main Fabric", cloth="CLOTH-1"),
			],
		)

	def _calculated_cloth(self, ipd, attributes, quantity, cloth_combination, stitching_combination):
		return [
			{
				"cloth_type": "Main Fabric",
				"colour": attributes["Colour"],
				"dia": "20 Dia",
				"quantity": quantity * 0.2,
			}
		]

	@patch.object(cloth_program, "get_cloth_combination", return_value={})
	@patch.object(cloth_program, "get_stitching_combination", return_value={})
	@patch.object(cloth_program, "calculate_cloth")
	@patch.object(cloth_program, "_variant_attributes")
	def test_aggregates_routes_and_applies_extra_percentage(
		self,
		variant_attributes,
		calculate,
		_get_stitching,
		_get_cloth,
	):
		variant_attributes.return_value = {"Colour": "Red"}
		calculate.side_effect = self._calculated_cloth

		result = cloth_program._calculate_cloth_program(
			self.lot, self.ipd, extra_percentage=5
		)

		self.assertEqual(result["cloth_per_kg_yarn"], 1.0)
		self.assertEqual(result["extra_percentage"], 5.0)
		self.assertEqual(
			result["rows"],
			[
				{
					"cloth_item": "CLOTH-1",
					"colour": "Red",
					"dia": "20 Dia",
					"required_weight": 3.0,
					"extra_weight": 0.15,
					"program_weight": 3.15,
				}
			],
		)
		self.assertEqual(result["totals"]["program_weight"], 3.15)

	def test_negative_extra_percentage_is_rejected(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "cannot be negative"
		):
			cloth_program._calculate_cloth_program(
				self.lot, self.ipd, extra_percentage=-1
			)

	@patch.object(cloth_program, "get_cloth_combination", return_value={})
	@patch.object(cloth_program, "get_stitching_combination", return_value={})
	@patch.object(cloth_program, "calculate_cloth")
	@patch.object(cloth_program, "_variant_attributes")
	def test_unmapped_cloth_label_is_rejected(
		self,
		variant_attributes,
		calculate,
		_get_stitching,
		_get_cloth,
	):
		variant_attributes.return_value = {"Colour": "Red"}
		calculate.return_value = [
			{
				"cloth_type": "Missing Fabric",
				"colour": "Red",
				"dia": "20 Dia",
				"quantity": 1,
			}
		]

		with self.assertRaisesRegex(
			frappe.ValidationError, "Missing Fabric"
		):
			cloth_program._calculate_cloth_program(
				self.lot, self.ipd, extra_percentage=0
			)
