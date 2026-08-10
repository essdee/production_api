# Copyright (c) 2026, Essdee and contributors
# See license.txt

from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.essdee_production.doctype.lot import cloth_program


class TestClothProgramPreview(FrappeTestCase):
	def test_lot_has_cloth_excess_percentage_field(self):
		meta = frappe.get_file_json(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"doctype",
				"lot",
				"lot.json",
			)
		)
		field = next(
			row
			for row in meta["fields"]
			if row.get("fieldname") == "cloth_excess_percentage"
		)
		self.assertEqual(field["label"], "Cloth Excess Percentage")
		self.assertEqual(field["fieldtype"], "Percent")
		self.assertEqual(field["default"], "0")

		cloth_program_tab = next(
			row
			for row in meta["fields"]
			if row.get("fieldname") == "cloth_program_tab"
		)
		cloth_program_html = next(
			row
			for row in meta["fields"]
			if row.get("fieldname") == "cloth_program_html"
		)
		self.assertEqual(cloth_program_tab["label"], "Cloth Program")
		self.assertEqual(cloth_program_tab["fieldtype"], "Tab Break")
		self.assertEqual(cloth_program_html["fieldtype"], "HTML")

	def test_accessories_share_cloth_item_table_with_fabric_type_column(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"doctype",
				"lot",
				"lot.js",
			)
		).read_text()

		self.assertIn("accessory_block_label", source)
		self.assertIn("`${label} Fabric`", source)
		self.assertIn("const table_key = cloth_item;", source)
		self.assertIn(
			'const route_key = [requirement_type, accessory_name, dia].join("\\u0000");',
			source,
		)
		self.assertIn('<th>${__("Fabric Type")}</th>', source)
		self.assertIn("<td>${escape(route.fabric_type)}</td>", source)
		self.assertNotIn(
			'const table_key = [cloth_item, requirement_type, accessory_name]',
			source,
		)
		self.assertIn("const round_weight = (value) =>", source)
		self.assertIn("number - floor > 0.5 ? Math.ceil(number) : floor", source)
		self.assertNotIn("Math.ceil(Number(value || 0))", source)
		self.assertIn("result.program_weight += program", source)
		self.assertNotIn("minimumFractionDigits: 3", source)
		self.assertIn("const fabric_groups = [];", source)
		self.assertIn('__("Total {0}", [fabric_group.fabric_type])', source)
		self.assertIn('secondary_action_label: __("Print")', source)
		self.assertIn('encodeURIComponent("Lot Cloth Program")', source)
		self.assertIn("load_saved_cloth_program(frm);", source)
		self.assertIn("extra_percentage <= 0", source)
		self.assertIn("render_saved_cloth_program(frm, r.message || {});", source)
		self.assertIn(
			"production_api.essdee_production.doctype.lot.cloth_program.get_cloth_program_preview",
			source,
		)

	def test_print_format_is_named_lot_cloth_program(self):
		print_format = frappe.get_file_json(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"print_format",
				"lot_cloth_program",
				"lot_cloth_program.json",
			)
		)
		self.assertEqual(print_format["name"], "Lot Cloth Program")
		self.assertEqual(print_format["doc_type"], "Lot")
		self.assertEqual(print_format["standard"], "Yes")
		self.assertIn("orientation: Landscape", print_format["css"])
		self.assertIn(
			"get_cloth_program_print_data(doc.name)", print_format["html"]
		)
		self.assertIn("Fabric Type", print_format["html"])
		self.assertIn('class="program-identifiers"', print_format["html"])
		self.assertIn("Lot : {{ doc.name }}", print_format["html"])
		self.assertIn("cloth.fabric_groups", print_format["html"])
		self.assertIn("Total {{ fabric.fabric_type }}", print_format["html"])
		self.assertIn('class="subtotal-label" colspan="2"', print_format["html"])
		self.assertIn("Total Knitting Program Kg", print_format["html"])

	def test_display_data_matches_preview_matrix_and_rounding(self):
		result = cloth_program.build_cloth_program_display_data(
			{
				"uses_compacting_details": False,
				"rows": [
					{
						"cloth_item": "CLOTH-1",
						"requirement_type": "cloth",
						"colour": "Red",
						"dia": "20 Dia",
						"required_weight": 10.0,
						"program_weight": 10.5,
					},
					{
						"cloth_item": "CLOTH-1",
						"requirement_type": "cloth",
						"colour": "Blue",
						"dia": "20 Dia",
						"required_weight": 4.1,
						"program_weight": 4.51,
					},
					{
						"cloth_item": "CLOTH-1",
						"requirement_type": "accessory",
						"accessory_name": "binding",
						"colour": "Blue",
						"dia": "20 Dia",
						"required_weight": 3.0,
						"program_weight": 3.6,
					},
					{
						"cloth_item": "CLOTH-1",
						"requirement_type": "accessory",
						"accessory_name": "folding",
						"colour": "Red",
						"dia": "20 Dia",
						"required_weight": 2.0,
						"program_weight": 2.5,
					},
				],
			}
		)

		self.assertEqual(len(result["tables"]), 1)
		table = result["tables"][0]
		self.assertEqual(table["colours"], ["Blue", "Red"])
		self.assertEqual(
			[route["fabric_type"] for route in table["routes"]],
			["Main Fabric", "Binding Fabric", "Folding Fabric"],
		)
		self.assertEqual(table["routes"][0]["weights"], {"Blue": 5, "Red": 10})
		self.assertEqual(table["routes"][1]["weights"], {"Blue": 4, "Red": 0})
		self.assertEqual(table["routes"][2]["weights"], {"Blue": 0, "Red": 2})
		self.assertEqual(
			[group["fabric_type"] for group in table["fabric_groups"]],
			["Main Fabric", "Binding Fabric", "Folding Fabric"],
		)
		self.assertEqual(
			table["fabric_groups"][0]["colour_totals"],
			{"Blue": 5, "Red": 10},
		)
		self.assertEqual(table["fabric_groups"][0]["total"], 15)
		self.assertEqual(table["fabric_groups"][1]["total"], 4)
		self.assertEqual(table["fabric_groups"][2]["total"], 2)
		self.assertEqual(table["colour_totals"], {"Blue": 9, "Red": 12})
		self.assertEqual(table["total"], 21)
		self.assertEqual(
			result["display_totals"],
			{"required_weight": 19, "extra_weight": 2, "program_weight": 21},
		)

	@patch.object(cloth_program, "build_cloth_program_display_data")
	@patch.object(cloth_program, "_calculate_cloth_program")
	@patch.object(cloth_program.frappe, "get_cached_doc")
	@patch.object(cloth_program.frappe, "get_doc")
	def test_print_data_uses_saved_lot_percentage(
		self,
		get_doc,
		get_cached_doc,
		calculate,
		build_display,
	):
		lot_doc = MagicMock()
		lot_doc.production_detail = "GARMENT-IPD-1"
		lot_doc.get.side_effect = lambda fieldname: {
			"production_detail": "GARMENT-IPD-1",
			"cloth_excess_percentage": 7,
			"item": "GARMENT-1",
		}.get(fieldname)
		get_doc.return_value = lot_doc
		ipd_doc = MagicMock()
		get_cached_doc.return_value = ipd_doc
		preview = {"lot": "LOT-1", "rows": []}
		calculate.return_value = preview
		build_display.return_value = {"tables": [], "display_totals": {}}

		result = cloth_program.get_cloth_program_print_data("LOT-1")

		lot_doc.check_permission.assert_called_once_with("read")
		calculate.assert_called_once_with(lot_doc, ipd_doc, 7)
		build_display.assert_called_once_with(preview)
		self.assertEqual(result["item"], "GARMENT-1")
		self.assertEqual(result["production_detail"], "GARMENT-IPD-1")

	@patch.object(cloth_program, "_calculate_cloth_program")
	@patch.object(cloth_program.frappe, "get_cached_doc")
	@patch.object(cloth_program.frappe, "get_doc")
	def test_preview_saves_selected_percentage_on_lot(
		self,
		get_doc,
		get_cached_doc,
		calculate,
	):
		lot_doc = MagicMock()
		lot_doc.production_detail = "GARMENT-IPD-1"
		lot_doc.get.side_effect = lambda fieldname: {
			"production_detail": "GARMENT-IPD-1",
			"cloth_excess_percentage": 2,
		}.get(fieldname)
		lot_doc.modified = "2026-08-10 12:00:00.000000"
		get_doc.return_value = lot_doc
		ipd_doc = MagicMock()
		get_cached_doc.return_value = ipd_doc
		calculate.return_value = {"extra_percentage": 5.0, "rows": []}

		result = cloth_program.get_cloth_program_preview("LOT-1", 5)

		self.assertEqual(result["extra_percentage"], 5.0)
		self.assertEqual(result["lot_modified"], lot_doc.modified)
		lot_doc.check_permission.assert_called_once_with("write")
		calculate.assert_called_once_with(lot_doc, ipd_doc, 5)
		lot_doc.db_set.assert_called_once_with("cloth_excess_percentage", 5.0)

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
					"requirement_type": "cloth",
					"accessory_name": None,
					"colour": "Red",
					"dia": "20 Dia",
					"required_weight": 3.0,
					"extra_weight": 0.15,
					"program_weight": 3.15,
				}
			],
		)
		self.assertEqual(result["totals"]["program_weight"], 3.15)

	@patch.object(cloth_program, "get_cloth_combination", return_value={})
	@patch.object(cloth_program, "get_stitching_combination", return_value={})
	@patch.object(cloth_program, "calculate_cloth")
	@patch.object(cloth_program, "_variant_attributes")
	def test_main_fabric_and_accessory_stay_separate_for_the_same_route(
		self,
		variant_attributes,
		calculate,
		_get_stitching,
		_get_cloth,
	):
		variant_attributes.return_value = {"Colour": "Red"}

		def calculated_rows(ipd, attributes, quantity, cloths, stitching):
			return [
				{
					"cloth_type": "Main Fabric",
					"colour": "Red",
					"dia": "20 Dia",
					"quantity": quantity * 0.2,
					"type": "cloth",
				},
				{
					"cloth_type": "Main Fabric",
					"colour": "Red",
					"dia": "20 Dia",
					"quantity": quantity * 0.05,
					"type": "accessory",
					"accessory_name": "Folding",
				},
			]

		calculate.side_effect = calculated_rows

		result = cloth_program._calculate_cloth_program(
			self.lot, self.ipd, extra_percentage=0
		)

		self.assertEqual(len(result["rows"]), 2)
		self.assertEqual(
			[
				(
					row["requirement_type"],
					row["accessory_name"],
					row["required_weight"],
				)
				for row in result["rows"]
			],
			[("cloth", None, 3.0), ("accessory", "Folding", 0.75)],
		)
		self.assertEqual(result["totals"]["required_weight"], 3.75)

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
