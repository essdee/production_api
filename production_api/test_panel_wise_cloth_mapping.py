# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.panel_wise_cloth_mapping import (
	_merge_saved_matrix,
	expand_panel_wise_cloth_mapping_matrix,
)


def _context():
	return {
		"attributes": ["Panel", "Colour"],
		"panel_attribute": "Panel",
		"packing_attribute": "Colour",
		"other_attributes": [],
		"cloth_options": ["Main Fabric", "Rib"],
		"uses_panel": True,
		"uses_packing": True,
		"consumption": {
			"panel_values": ["Front", "Back"],
			"panel_packing_values": {
				"Front": ["Black"],
				"Back": ["Black"],
			},
			"source_packing_values": ["Black"],
		},
	}


def _matrix(cloth="Main Fabric"):
	return {
		"attributes": ["Panel", "Colour"],
		"panels": [
			{
				"group_id": "Front\x1fBack",
				"panel_value": "Front + Back",
				"panel_values": ["Front", "Back"],
				"packing_values": ["Black"],
				"rows": [
					{
						"attribute_values": {},
						"values": {"Black": {"cloth": cloth}},
					}
				],
			}
		],
	}


class TestPanelWiseClothMapping(FrappeTestCase):
	def test_group_cloth_is_expanded_to_each_panel(self):
		expanded = expand_panel_wise_cloth_mapping_matrix(_matrix(), _context())
		self.assertEqual(
			expanded["items"],
			[
				{"Panel": "Front", "Colour": "Black", "Cloth": "Main Fabric"},
				{"Panel": "Back", "Colour": "Black", "Cloth": "Main Fabric"},
			],
		)

	def test_blank_cloth_cell_is_allowed_in_draft(self):
		expanded = expand_panel_wise_cloth_mapping_matrix(_matrix(cloth=None), _context())
		self.assertEqual(expanded["items"], [])

	def test_invalid_cloth_label_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Invalid Cloth label"):
				expand_panel_wise_cloth_mapping_matrix(
				_matrix(cloth="Unknown Fabric"), _context()
			)

	def test_saved_single_panels_are_preserved_when_they_are_grouped(self):
		target = _matrix(cloth=None)
		saved = {
			"attributes": ["Panel", "Colour"],
			"panels": [
				{
					"panel_values": [panel],
					"rows": [{
						"attribute_values": {},
						"values": {"Black": {"cloth": "Main Fabric"}},
					}],
				}
				for panel in ("Front", "Back")
			],
		}

		_merge_saved_matrix(target, saved, _context())

		self.assertEqual(
			target["panels"][0]["rows"][0]["values"]["Black"]["cloth"],
			"Main Fabric",
		)
