# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
	ItemProductionDetail,
	calculate_cloth,
	copy_duplicate_ipd_scalar_fields,
	get_approval_roles,
	get_cloth_combination,
	get_dict_table,
	get_stitching_combination,
	_require_cutting_cloth_mapping,
	revert_ipd_approval,
)
from production_api.panel_wise_consumption import (
	_blank_matrix,
	_merge_cutting_rows,
	expand_panel_wise_matrix,
	get_matrix_context,
)
from production_api.sd_yrp_sync import clean_doc_for_publish, enqueue_sd_yrp_publish


def _context():
	return {
		"primary_attribute": "Size",
		"panel_attribute": "Panel",
		"packing_attribute": "Colour",
		"primary_values": ["75 cm", "80 cm"],
		"panel_values": ["Back", "Front"],
		"panel_quantities": {"Back": 1, "Front": 1},
		"packing_values": ["Black", "Maroon"],
		"source_packing_values": ["Black", "Maroon"],
		"panel_packing_values": {
			"Back": ["Black", "Maroon"],
			"Front": ["Black", "Maroon"],
		},
		"panel_colour_map": {
			"Back": {"Black": "Black", "Maroon": "Maroon"},
			"Front": {"Black": "Black", "Maroon": "Maroon"},
		},
	}


def _centre_panel_context():
	return {
		"primary_attribute": "Size",
		"panel_attribute": "Panel",
		"packing_attribute": "Colour",
		"primary_values": ["75 cm"],
		"panel_values": ["Center Panel"],
		"panel_quantities": {"Center Panel": 1},
		"packing_values": ["Red", "A Mel", "G Mel", "Black"],
		"source_packing_values": ["Black", "Maroon", "Navy", "A Mel", "G Mel"],
		"panel_packing_values": {
			"Center Panel": ["Red", "A Mel", "G Mel", "Black"],
		},
		"panel_colour_map": {
			"Center Panel": {
				"Black": "Red",
				"Maroon": "A Mel",
				"Navy": "G Mel",
				"A Mel": "Red",
				"G Mel": "Black",
			},
		},
	}


class TestPanelWiseConsumption(FrappeTestCase):
	def test_matrix_context_includes_physical_panel_quantities(self):
		doc = frappe._dict(
			primary_item_attribute="Size",
			stiching_attribute="Panel",
			packing_attribute="Colour",
			is_set_item=0,
			item_attributes=[],
			packing_attribute_details=[frappe._dict(attribute_value="Black")],
			stiching_item_details=[
				frappe._dict(stiching_attribute_value="Front", quantity=1),
				frappe._dict(stiching_attribute_value="Back", quantity=1),
				frappe._dict(stiching_attribute_value="Sleeve", quantity=2),
			],
			stiching_item_combination_details=[],
		)

		with patch(
			"production_api.panel_wise_consumption._mapping_values",
			return_value=["75 cm"],
		):
			context = get_matrix_context(doc)

		self.assertEqual(
			context["panel_quantities"],
			{"Front": 1, "Back": 1, "Sleeve": 2},
		)

	def test_panel_copy_resynchronizes_the_dia_link_control(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"PanelWiseConsumptionMatrix.vue",
			)
		).read_text()

		self.assertIn("updated(el, binding)", source)
		self.assertIn("syncDiaLink(el, binding.value)", source)
		self.assertIn("state.control.set_value(value)", source)

	def test_panel_can_fetch_details_from_another_panel(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"PanelWiseConsumptionMatrix.vue",
			)
		).read_text()

		self.assertIn('v-model="sourcePanelValue"', source)
		self.assertIn('@click="applyPanelDetails"', source)
		self.assertIn("targetRow.values = copiedValues", source)

	def test_panel_groups_and_vertical_keyboard_navigation_are_available(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"PanelWiseConsumptionMatrix.vue",
			)
		).read_text()

		self.assertIn("groupSelectedPanels", source)
		self.assertIn("ungroupCurrentPanel", source)
		self.assertIn('event.key !== "ArrowDown"', source)
		self.assertIn("event.ctrlKey || event.shiftKey", source)

	def test_panel_consumption_has_overwriting_column_fill(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"PanelWiseConsumptionMatrix.vue",
			)
		).read_text()

		self.assertIn("fillConsumptionColumn(packing)", source)
		self.assertIn('primary_action_label: "Fill Column"', source)
		self.assertIn("currentPanel.value.rows.forEach", source)
		self.assertIn("row.values[packing] =", source)

	def test_cutting_and_cloth_accessory_weights_use_four_decimal_precision(self):
		component_paths = (
			("Item_Po_detail", "CuttingItemDetail.vue"),
			("Item_Po_detail", "ClothAccessory.vue"),
		)
		for component_path in component_paths:
			source = Path(
				frappe.get_app_path(
					"production_api",
					"public",
					"js",
					*component_path,
				)
			).read_text()
			self.assertIn("df['precision'] = 4", source)

		matrix_source = Path(
			frappe.get_app_path(
				"production_api",
				"public",
				"js",
				"Item_Po_detail",
				"PanelWiseConsumptionMatrix.vue",
			)
		).read_text()
		self.assertIn("Number(parsed.toFixed(4))", matrix_source)
		self.assertIn("Number(value).toFixed(4)", matrix_source)

	def test_stitching_attribute_rows_receive_entry_defaults(self):
		source = Path(
			frappe.get_app_path(
				"production_api",
				"essdee_production",
				"doctype",
				"item_production_detail",
				"item_production_detail.js",
			)
		).read_text()

		self.assertIn("quantity: 1", source)
		self.assertIn('category: "Body"', source)

	def test_colour_yarn_recipe_table_is_not_in_ipd(self):
		self.assertIsNone(
			frappe.get_meta("Item Production Detail").get_field("colour_yarn_recipes")
		)

	def test_system_manager_is_always_an_approver(self):
		self.assertIn("System Manager", get_approval_roles())

	def test_configured_approver_can_revert_ipd(self):
		doc = SimpleNamespace(
			approval_status="Approved",
			approved_by="approver@example.com",
			save=Mock(),
		)
		module = (
			"production_api.essdee_production.doctype.item_production_detail."
			"item_production_detail"
		)
		with patch(
			f"{module}.get_approval_roles",
			return_value=["Merchandising Manager", "System Manager"],
		), patch.object(
			frappe,
			"get_roles",
			return_value=["Merchandising Manager"],
		), patch.object(
			frappe,
			"get_doc",
			return_value=doc,
		):
			result = revert_ipd_approval("TEST-IPD")

		self.assertEqual(result, {"status": "success"})
		self.assertEqual(doc.approval_status, "Not Approved")
		self.assertIsNone(doc.approved_by)
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_duplicate_keeps_matrix_and_sync_payload(self):
		source = frappe.new_doc("Item Production Detail")
		source.item = "TEST MATRIX ITEM"
		source.enable_panel_wise_consumption_matrix = 1
		source.panel_wise_consumption_matrix_json = {
			"schema_version": 2,
			"panels": [{"panel_value": "Back", "rows": []}],
		}
		source.panel_wise_cloth_mapping_json = {
			"schema_version": 1,
			"panels": [{"panel_values": ["Back"], "rows": []}],
		}
		source.cutting_items_json = {
			"attributes": ["Size", "Panel", "Colour", "Dia", "Weight"],
			"items": [],
		}
		target = frappe.new_doc("Item Production Detail")

		copy_duplicate_ipd_scalar_fields(source, target)
		payload = clean_doc_for_publish(target)

		self.assertEqual(target.enable_panel_wise_consumption_matrix, 1)
		self.assertEqual(
			frappe.parse_json(target.panel_wise_consumption_matrix_json),
			source.panel_wise_consumption_matrix_json,
		)
		self.assertEqual(
			frappe.parse_json(target.cutting_items_json),
			source.cutting_items_json,
		)
		self.assertEqual(
			frappe.parse_json(target.panel_wise_cloth_mapping_json),
			source.panel_wise_cloth_mapping_json,
		)
		self.assertEqual(payload["enable_panel_wise_consumption_matrix"], 1)
		self.assertEqual(
			frappe.parse_json(payload["panel_wise_consumption_matrix_json"]),
			source.panel_wise_consumption_matrix_json,
		)
		self.assertEqual(
			frappe.parse_json(payload["cutting_items_json"]),
			source.cutting_items_json,
		)

	def test_duplicate_intermediate_save_is_not_published(self):
		doc = frappe.new_doc("Item Production Detail")
		doc.flags.skip_sd_yrp_sync = True
		with patch("production_api.sd_yrp_sync.publish_sd_yrp_event") as publish:
			enqueue_sd_yrp_publish(doc, "on_update")
		publish.assert_not_called()

	def test_duplicate_final_save_is_published(self):
		doc = frappe.new_doc("Item Production Detail")
		doc.flags.skip_sd_yrp_sync = False
		with patch.dict(frappe.conf, {"developer_mode": True}), patch(
			"production_api.sd_yrp_sync.publish_sd_yrp_event"
		) as publish:
			enqueue_sd_yrp_publish(doc, "on_update")
		publish.assert_called_once_with(doc, "on_update", ())

	def test_duplicate_child_rows_do_not_reuse_source_identity(self):
		source = frappe.new_doc("Item Production Detail")
		source.name = "SOURCE-IPD"
		row = source.append("item_attributes", {"attribute": "Size"})
		row.name = "SOURCE-ROW"
		row.parent = source.name

		copied_row = get_dict_table(source.item_attributes)[0]

		for fieldname in ("doctype", "name", "parent", "parentfield", "parenttype", "idx"):
			self.assertNotIn(fieldname, copied_row)
		self.assertEqual(copied_row["attribute"], "Size")

	def test_initial_draft_can_save_before_stitching_tab_is_visible(self):
		doc = frappe._dict(
			stiching_item_details=[],
			is_new=lambda: True,
		)
		ItemProductionDetail.stiching_tab_validations(doc)

		doc.is_new = lambda: False
		with self.assertRaises(frappe.ValidationError):
			ItemProductionDetail.stiching_tab_validations(doc)

	def test_legacy_rows_are_expanded_across_packing_values(self):
		context = _context()
		matrix = _blank_matrix(context)
		_merge_cutting_rows(
			matrix,
			{
				"items": [
					{
						"Panel": "Back",
						"Size": "75 cm",
						"Dia": "26 Dia",
						"Weight": 0.03,
					}
				]
			},
			context,
		)
		row = matrix["panels"][0]["rows"][0]
		self.assertEqual(row["values"]["Black"], {"dia": "26 Dia", "weight": 0.03})
		self.assertEqual(row["values"]["Maroon"], {"dia": "26 Dia", "weight": 0.03})

	def test_matrix_expands_to_standard_cutting_contract(self):
		context = _context()
		matrix = _blank_matrix(context)
		for panel_index, panel in enumerate(matrix["panels"]):
			for size_index, row in enumerate(panel["rows"]):
				base_dia = 26 + panel_index * 2 + size_index * 2
				row["values"] = {
					"Black": {
						"dia": f"{base_dia} Dia",
						"weight": 0.03 + panel_index * 0.01 + size_index * 0.001,
					},
					"Maroon": {
						"dia": f"{base_dia + 1} Dia",
						"weight": 0.031 + panel_index * 0.01 + size_index * 0.001,
					},
				}

		expanded = expand_panel_wise_matrix(matrix, context)
		self.assertEqual(
			expanded["attributes"], ["Size", "Panel", "Colour", "Dia", "Weight"]
		)
		self.assertEqual(len(expanded["items"]), 8)
		self.assertEqual(
			expanded["items"][0],
			{
				"Size": "75 cm",
				"Panel": "Back",
				"Colour": "Black",
				"Dia": "26 Dia",
				"Weight": 0.03,
			},
		)
		self.assertEqual(expanded["items"][1]["Dia"], "27 Dia")

	def test_group_total_is_split_into_individual_panel_rows(self):
		context = _context()
		matrix = _blank_matrix(context, panel_groups=[["Back", "Front"]])
		cell = matrix["panels"][0]["rows"][0]["values"]["Black"]
		cell.update({"dia": "26 Dia", "weight": 0.1})

		expanded = expand_panel_wise_matrix(
			matrix, context, require_complete=False
		)

		self.assertEqual(len(expanded["items"]), 2)
		self.assertEqual(
			[row["Panel"] for row in expanded["items"]], ["Back", "Front"]
		)
		self.assertEqual(
			[row["Weight"] for row in expanded["items"]], [0.05, 0.05]
		)

	def test_group_total_is_normalized_by_physical_panel_quantities(self):
		context = _context()
		context["panel_values"] = ["Front", "Back", "Sleeve"]
		context["panel_quantities"] = {"Front": 1, "Back": 1, "Sleeve": 2}
		context["panel_packing_values"] = {
			panel: ["Black", "Maroon"] for panel in context["panel_values"]
		}
		context["panel_colour_map"] = {
			panel: {"Black": "Black", "Maroon": "Maroon"}
			for panel in context["panel_values"]
		}
		matrix = _blank_matrix(
			context, panel_groups=[["Front", "Back", "Sleeve"]]
		)
		cell = matrix["panels"][0]["rows"][0]["values"]["Black"]
		cell.update({"dia": "26 Dia", "weight": 0.1})

		expanded = expand_panel_wise_matrix(
			matrix, context, require_complete=False
		)

		self.assertEqual(cell["weight"], 0.1)
		self.assertEqual(
			[row["Panel"] for row in expanded["items"]],
			["Front", "Back", "Sleeve"],
		)
		self.assertEqual(
			[row["Weight"] for row in expanded["items"]],
			[0.033333, 0.033333, 0.016667],
		)
		self.assertEqual(
			flt(
				sum(
					row["Weight"] * context["panel_quantities"][row["Panel"]]
					for row in expanded["items"]
				),
				6,
			),
			0.1,
		)

	def test_partial_matrix_can_expand_without_inventing_blank_rows(self):
		context = _context()
		matrix = _blank_matrix(context)
		matrix["panels"][0]["rows"][0]["values"]["Black"].update(
			{"dia": "26 Dia", "weight": 0.03}
		)
		matrix["panels"][0]["rows"][0]["values"]["Maroon"]["dia"] = "27 Dia"

		expanded = expand_panel_wise_matrix(
			matrix, context, require_complete=False
		)

		self.assertEqual(len(expanded["items"]), 1)
		self.assertEqual(expanded["items"][0]["Panel"], "Back")
		self.assertEqual(expanded["items"][0]["Colour"], "Black")

	def test_panel_uses_only_actual_stitching_colours(self):
		context = _centre_panel_context()
		matrix = _blank_matrix(context)
		self.assertEqual(
			matrix["panels"][0]["packing_values"],
			["Red", "A Mel", "G Mel", "Black"],
		)
		self.assertEqual(
			list(matrix["panels"][0]["rows"][0]["values"]),
			["Red", "A Mel", "G Mel", "Black"],
		)

	def test_legacy_garment_colours_collapse_to_one_panel_colour(self):
		context = _centre_panel_context()
		matrix = _blank_matrix(context)
		_merge_cutting_rows(
			matrix,
			{
				"items": [
					{
						"Panel": "Center Panel",
						"Size": "75 cm",
						"Colour": "Black",
						"Dia": "15 Dia",
						"Weight": 0.01,
					},
					{
						"Panel": "Center Panel",
						"Size": "75 cm",
						"Colour": "A Mel",
						"Dia": "15 Dia",
						"Weight": 0.01,
					},
				]
			},
			context,
			source_schema=1,
		)
		self.assertEqual(
			matrix["panels"][0]["rows"][0]["values"]["Red"]["weight"],
			0.01,
		)

	def test_conflicting_legacy_rows_for_same_panel_colour_are_rejected(self):
		context = _centre_panel_context()
		matrix = _blank_matrix(context)
		with self.assertRaises(frappe.ValidationError):
			_merge_cutting_rows(
				matrix,
				{
					"items": [
						{
							"Panel": "Center Panel",
							"Size": "75 cm",
							"Colour": "Black",
							"Dia": "15 Dia",
							"Weight": 0.01,
						},
						{
							"Panel": "Center Panel",
							"Size": "75 cm",
							"Colour": "A Mel",
							"Dia": "15 Dia",
							"Weight": 0.02,
						},
					]
				},
				context,
				source_schema=1,
			)

	def test_schema_two_calculation_looks_up_actual_panel_colour(self):
		ipd = frappe._dict({
			"stiching_attribute": "Panel",
			"packing_attribute": "Colour",
			"set_item_attribute": None,
			"is_set_item": 0,
			"is_same_packing_attribute": 0,
			"enable_panel_wise_consumption_matrix": 1,
			"panel_wise_consumption_matrix_json": {"schema_version": 2},
			"cutting_attributes": [
				frappe._dict(attribute="Size"),
				frappe._dict(attribute="Panel"),
				frappe._dict(attribute="Colour"),
			],
			"cloth_attributes": [
				frappe._dict(attribute="Panel"),
				frappe._dict(attribute="Colour"),
			],
			"accessory_attributes": [],
			"cutting_items_json": frappe.as_json({
				"items": [{
					"Size": "75 cm",
					"Panel": "Center Panel",
					"Colour": "Red",
					"Dia": "15 Dia",
					"Weight": 0.01,
				}],
			}),
			"cutting_cloths_json": frappe.as_json({
				"items": [{
					"Panel": "Center Panel",
					"Colour": "Red",
					"Cloth": "Contrast Fabric",
				}],
			}),
			"cloth_accessory_json": "{}",
			"accessory_clothtype_json": {},
			"stiching_item_details": [
				frappe._dict(
					stiching_attribute_value="Center Panel",
					set_item_attribute_value=None,
					quantity=1,
				),
			],
			"stiching_item_combination_details": [
				frappe._dict(
					major_attribute_value="Black",
					set_item_attribute_value="Center Panel",
					attribute_value="Red",
				),
			],
		})

		rows = calculate_cloth(
			ipd,
			{"Size": "75 cm", "Colour": "Black"},
			100,
			get_cloth_combination(ipd),
			get_stitching_combination(ipd),
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(
			(rows[0]["colour"], rows[0]["cloth_type"], rows[0]["quantity"]),
			("Red", "Contrast Fabric", 1.0),
		)

	def test_lot_cloth_calculation_rejects_an_unmapped_consumption_route(self):
		cloth_combination = {
			"cloth_combination": {
				("Front", "Airforce", "75 cm"): "Main Fabric",
			}
		}

		with self.assertRaisesRegex(
			frappe.ValidationError,
			"No Cutting Cloth mapping matches consumption combination "
			"Sleeve / Airforce / 75 cm",
		):
			_require_cutting_cloth_mapping(
				cloth_combination,
				("Sleeve", "Airforce", "75 cm"),
			)

	def test_incomplete_matrix_is_rejected(self):
		context = _context()
		matrix = _blank_matrix(context)
		with self.assertRaises(frappe.ValidationError):
			expand_panel_wise_matrix(matrix, context)
