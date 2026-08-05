# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.essdee_production.doctype.ipd_compacting.ipd_compacting import (
	get_expected_compacting_details,
	merge_compacting_details,
	validate_submitted_details,
)
from production_api.essdee_production.doctype.lot import cloth_program


def _ipd():
	return frappe._dict(
		name="_Test Compacting IPD",
		enable_panel_wise_consumption_matrix=1,
		packing_attribute="Colour",
		cloth_attributes=[
			frappe._dict(attribute="Panel"),
			frappe._dict(attribute="Colour"),
		],
		cloth_detail=[
			frappe._dict(name1="Main", cloth="CLOTH-MAIN"),
			frappe._dict(name1="Rib", cloth="CLOTH-RIB"),
		],
		cutting_cloths_json={
			"items": [
				{"Panel": "Body", "Colour": "Black", "Cloth": "Main"},
				{"Panel": "Collar", "Colour": "Black", "Cloth": "Rib"},
			]
		},
		cutting_items_json={
			"items": [
				{
					"Size": "S", "Panel": "Body", "Colour": "Black",
					"Dia": "32", "Weight": 0.1,
				},
				{
					"Size": "M", "Panel": "Body", "Colour": "Black",
					"Dia": "32", "Weight": 0.11,
				},
				{
					"Size": "S", "Panel": "Collar", "Colour": "Black",
					"Dia": "32", "Weight": 0.02,
				},
			]
		},
	)


def _ipd_with_accessory():
	ipd = _ipd()
	ipd.cloth_detail.append(
		frappe._dict(name1="Folding Fabric", cloth="CLOTH-FOLDING")
	)
	ipd.cloth_accessory_json = {
		"items": [
			{"Size": "S", "Accessory": "Folding", "Dia": "20", "Weight": 0.01},
			{"Size": "M", "Accessory": "Folding", "Dia": "22", "Weight": 0.01},
		]
	}
	ipd.accessory_clothtype_json = {"Folding": "Folding Fabric"}
	ipd.stiching_accessory_json = {
		"items": [
			{
				"accessory": "Folding",
				"major_colour": "Black",
				"accessory_colour": "Black",
				"cloth_type": "Folding Fabric",
			},
			{
				"accessory": "Folding",
				"major_colour": "Navy",
				"accessory_colour": "Navy",
				"cloth_type": "Folding Fabric",
			},
		]
	}
	return ipd


class TestIPDCompacting(FrappeTestCase):
	def test_expected_details_use_cloth_mapping_and_collapse_exact_routes(self):
		self.assertEqual(
			get_expected_compacting_details(_ipd()),
			[
				{
					"cloth_item": "CLOTH-MAIN",
					"packing_attribute_value": "Black",
					"input_dia": "32",
				},
				{
					"cloth_item": "CLOTH-RIB",
					"packing_attribute_value": "Black",
					"input_dia": "32",
				},
			],
		)

	def test_expected_details_include_cloth_accessory_fabrics(self):
		details = get_expected_compacting_details(_ipd_with_accessory())
		accessory_details = [
			row for row in details if row["cloth_item"] == "CLOTH-FOLDING"
		]
		self.assertEqual(
			accessory_details,
			[
				{
					"cloth_item": "CLOTH-FOLDING",
					"packing_attribute_value": "Black",
					"input_dia": "20",
				},
				{
					"cloth_item": "CLOTH-FOLDING",
					"packing_attribute_value": "Black",
					"input_dia": "22",
				},
				{
					"cloth_item": "CLOTH-FOLDING",
					"packing_attribute_value": "Navy",
					"input_dia": "20",
				},
				{
					"cloth_item": "CLOTH-FOLDING",
					"packing_attribute_value": "Navy",
					"input_dia": "22",
				},
			],
		)

	def test_merge_preserves_values_only_for_the_same_three_part_key(self):
		expected = get_expected_compacting_details(_ipd())
		merged = merge_compacting_details(
			expected,
			[
				{
					"cloth_item": "CLOTH-MAIN",
					"packing_attribute_value": "Black",
					"input_dia": "32",
					"compacting_dia": "30",
				}
			],
		)
		self.assertEqual(merged[0]["compacting_dia"], "30")
		self.assertIsNone(merged[1]["compacting_dia"])

	def test_duplicate_submitted_key_is_rejected(self):
		expected = get_expected_compacting_details(_ipd())
		with self.assertRaisesRegex(frappe.ValidationError, "Duplicate"):
			validate_submitted_details(expected, [expected[0], expected[0]])

	@patch.object(cloth_program, "get_compacting_mapping")
	def test_cloth_program_resolves_compacting_by_cloth_colour_and_input_dia(self, mapping):
		mapping.return_value = {
			("CLOTH-MAIN", "Black", "32"): "30",
			("CLOTH-RIB", "Black", "32"): "31",
		}
		rows = [
			{"cloth_item": "CLOTH-MAIN", "colour": "Black", "dia": "32"},
			{"cloth_item": "CLOTH-RIB", "colour": "Black", "dia": "32"},
		]
		self.assertTrue(cloth_program._apply_compacting_details(_ipd(), rows))
		self.assertEqual(rows[0]["compacting_dia"], "30")
		self.assertEqual(rows[1]["compacting_dia"], "31")

	@patch.object(cloth_program, "get_compacting_mapping", return_value={})
	def test_cloth_program_rejects_missing_compacting_mapping(self, _mapping):
		with self.assertRaisesRegex(frappe.ValidationError, "CLOTH-MAIN / Black / 32"):
			cloth_program._apply_compacting_details(
				_ipd(),
				[{"cloth_item": "CLOTH-MAIN", "colour": "Black", "dia": "32"}],
			)

	def test_ipd_form_loads_the_compacting_editor(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"doctype",
				"item_production_detail",
				"item_production_detail.js",
			)
		).read_text()
		self.assertIn('frm.trigger("render_compacting_details")', source)
		self.assertIn("IPDCompactingDetails", source)

		component_source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"IPDCompactingDetails.vue",
			)
		).read_text()
		self.assertIn("fillDiaColumn", component_source)
		self.assertIn("copyColourToBlanks", component_source)
		self.assertIn("v-compacting-dia-link", component_source)
		self.assertIn('fieldtype: "Link"', component_source)
