# Copyright (c) 2026, Essdee and Contributors
# See license.txt

"""Integration tests for the Lot "Update Colour" feature.

The fixture builds a small, self-contained Item -> IPD -> Lot chain (no
set item, no dependent attribute) so every assertion is deterministic.
FrappeTestCase rolls each test back, so nothing leaks onto the site.
"""

import json

import frappe
from frappe.model.document import Document as FrappeDocument
from frappe.tests.utils import FrappeTestCase

from production_api.essdee_production.doctype.lot import colour_update as CU
from production_api.production_api.doctype.item.item import get_or_create_variant


class ColourUpdateFixture:
	"""Builds: Item(Colour x Size) -> IPD(Colour packing) -> Lot(Black rows)."""

	def __init__(self, prefix="CU", panel_wise=False):
		self.prefix = prefix
		self.panel_wise = panel_wise
		self.colours = ["Black", "Black 2", "Red"]
		self.sizes = ["S", "M"]
		self._ensure_masters()
		self.item = self._make_item()
		self.ipd = self._make_ipd()
		self.lot = self._make_lot()

	def _name(self, base):
		return "{0}-{1}".format(base, frappe.generate_hash(length=6))

	def _ensure_masters(self):
		for attribute in ("Colour", "Size", "Stage", "Panel"):
			if not frappe.db.exists("Item Attribute", attribute):
				frappe.get_doc(
					{"doctype": "Item Attribute", "attribute_name": attribute}
				).insert(ignore_permissions=True)
		self.stages = ["Pack", "Piece"]
		self.panels = ["Front"]
		values = [(colour, "Colour") for colour in self.colours]
		values += [(size, "Size") for size in self.sizes]
		values += [(stage, "Stage") for stage in self.stages]
		values += [(panel, "Panel") for panel in self.panels]
		for value, attribute in values:
			if not frappe.db.exists("Item Attribute Value", {"attribute_name": attribute, "attribute_value": value}):
				frappe.get_doc(
					{
						"doctype": "Item Attribute Value",
						"attribute_name": attribute,
						"attribute_value": value,
					}
				).insert(ignore_permissions=True)
		# IPD Settings keeps its own mandatory process defaults; the fixture
		# restores its scalars after insert instead of editing the Single.

	def _make_item(self):
		item_group = frappe.get_all("Item Group", limit_page_length=1)
		if not item_group:
			item_group_name = self._name("CU Group")
			frappe.get_doc({"doctype": "Item Group", "item_group_name": item_group_name}).insert(
				ignore_permissions=True
			)
		else:
			item_group_name = item_group[0].name
		doc = frappe.new_doc("Item")
		doc.name1 = self._name("CU Item")
		doc.item_group = item_group_name
		doc.default_unit_of_measure = (
			frappe.db.get_value("UOM", {"name": "Pieces"}, "name")
			or frappe.db.get_value("UOM", {}, "name")
		)
		doc.append("attributes", {"attribute": "Colour"})
		doc.append("attributes", {"attribute": "Size"})
		doc.append("attributes", {"attribute": "Stage"})
		doc.insert(ignore_permissions=True)

		# Fill the auto-created attribute mappings.
		for row in doc.attributes:
			mapping = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			values = {
				"Colour": self.colours,
				"Size": self.sizes,
				"Stage": self.stages,
			}[row.attribute]
			for value in values:
				if value not in [entry.attribute_value for entry in mapping.values]:
					mapping.append("values", {"attribute_value": value})
			mapping.save(ignore_permissions=True)

		# Dependent Stage attribute: Pack keeps only Size (colour-independent
		# order items); Piece keeps Colour + Size (order detail rows).
		doc.primary_attribute = "Size"
		doc.dependent_attribute = "Stage"
		doc.save(ignore_permissions=True)
		dependent_mapping = frappe.get_doc(
			"Item Dependent Attribute Mapping", doc.dependent_attribute_mapping
		)
		dependent_mapping.set(
			"mapping",
			[
				{"dependent_attribute_value": "Pack", "depending_attribute": "Size"},
				{"dependent_attribute_value": "Piece", "depending_attribute": "Colour"},
				{"dependent_attribute_value": "Piece", "depending_attribute": "Size"},
			],
		)
		dependent_mapping.save(ignore_permissions=True)
		return doc.name

	def _make_ipd(self):
		doc = frappe.new_doc("Item Production Detail")
		doc.item = self.item
		doc.primary_item_attribute = "Size"
		doc.packing_attribute = "Colour"
		doc.dependent_attribute = "Stage"
		doc.dependent_attribute_mapping = frappe.db.get_value(
			"Item", self.item, "dependent_attribute_mapping"
		)
		doc.pack_in_stage = "Piece"
		doc.is_same_packing_attribute = 1
		doc.packing_combo = 1
		doc.packing_attribute_no = 1
		doc.auto_calculate = 1
		doc.append("item_attributes", {"attribute": "Colour"})
		doc.append("item_attributes", {"attribute": "Size"})
		if self.panel_wise:
			doc.append("item_attributes", {"attribute": "Panel"})
		doc.append("packing_attribute_details", {"attribute_value": "Black", "quantity": 0})
		doc.append("cutting_attributes", {"attribute": "Size"})
		if self.panel_wise:
			doc.append("cutting_attributes", {"attribute": "Panel"})
		doc.append("cutting_attributes", {"attribute": "Colour"})
		if self.panel_wise:
			doc.append("cloth_attributes", {"attribute": "Panel"})
			doc.append("cloth_attributes", {"attribute": "Colour"})
		else:
			doc.append("cloth_attributes", {"attribute": "Colour"})
		doc.cutting_items_json = json.dumps(
			{
				"combination_type": "Cutting",
				"attributes": ["Size", "Colour", "Dia", "Weight"],
				"items": [
					{"Size": "S", "Colour": "Black", "Dia": "20 Dia", "Weight": 0.1},
					{"Size": "M", "Colour": "Black", "Dia": "22 Dia", "Weight": 0.2},
				],
				"select_list": {},
			}
		)
		cloth_attributes = ["Panel", "Colour"] if self.panel_wise else ["Colour"]
		cloth_items = (
			[{"Panel": "Front", "Colour": "Black", "Cloth": "OE Fabric"}]
			if self.panel_wise
			else [{"Colour": "Black", "Cloth": "OE Fabric"}]
		)
		doc.cutting_cloths_json = json.dumps(
			{
				"combination_type": "Cloth",
				"attributes": cloth_attributes + ["Cloth"],
				"items": cloth_items,
				"select_list": ["OE Fabric"],
			}
		)
		doc.insert(ignore_permissions=True)

		# Populate the auto-created attribute mappings with the fixture values
		# BEFORE the corrected second save so packing/panel validation passes.
		values_by_attribute = {"Colour": self.colours, "Size": self.sizes}
		if self.panel_wise:
			values_by_attribute["Panel"] = self.panels
		for row in doc.item_attributes:
			mapping = frappe.get_doc("Item Item Attribute Mapping", row.mapping)
			for value in values_by_attribute.get(row.attribute, []):
				if value not in [entry.attribute_value for entry in mapping.values]:
					mapping.append("values", {"attribute_value": value})
			mapping.save(ignore_permissions=True)

		# before_save applied the site's IPD Settings defaults on insert; the
		# fixture uses no processes so validation stays focused on packing data.
		doc.packing_attribute = "Colour"
		doc.primary_item_attribute = "Size"
		doc.packing_process = None
		doc.stiching_process = None
		doc.cutting_process = None
		doc.stiching_attribute = None
		doc.pack_in_stage = None
		doc.pack_out_stage = None
		doc.stiching_in_stage = None
		doc.stiching_out_stage = None
		doc.pack_in_stage = "Piece"
		doc.dependent_attribute = "Stage"
		doc.dependent_attribute_mapping = frappe.db.get_value(
			"Item", self.item, "dependent_attribute_mapping"
		)
		if self.panel_wise:
			doc.stiching_attribute = "Panel"
			doc.append(
				"stiching_item_details",
				{"stiching_attribute_value": "Front", "quantity": 1, "is_default": 1, "category": "Body"},
			)
			doc.append("cloth_detail", {"name1": "OE Fabric", "cloth": self.item})
			doc.enable_panel_wise_consumption_matrix = 1
			doc.panel_wise_consumption_matrix_json = json.dumps(
				{
					"schema_version": 4,
					"attributes": {"primary": "Size", "panel": "Panel", "packing": "Colour"},
					"primary_values": ["S", "M"],
					"packing_values": ["Black"],
					"panel_values": ["Front"],
					"panels": [
						{
							"group_id": "Front",
							"panel_value": "Front",
							"panel_values": ["Front"],
							"packing_values": ["Black"],
							"rows": [
								{
									"primary_value": size,
									"values": {"Black": {"dia": "20 Dia", "weight": 0.1}},
								}
								for size in self.sizes
							],
						}
					],
				}
			)
			doc.panel_wise_cloth_mapping_json = json.dumps(
				{
					"schema_version": 1,
					"attributes": ["Panel", "Colour"],
					"panel_attribute": "Panel",
					"packing_attribute": "Colour",
					"other_attributes": [],
					"cloth_options": ["OE Fabric"],
					"panels": [
						{
							"group_id": "Front",
							"panel_value": "Front",
							"panel_values": ["Front"],
							"packing_values": ["Black"],
							"rows": [
								{"attribute_values": {}, "values": {"Black": {"cloth": "OE Fabric"}}}
							],
						}
					],
				}
			)
		doc.save(ignore_permissions=True)
		doc.approval_status = "Approved"
		doc.approved_by = frappe.session.user
		doc.save(ignore_permissions=True)
		return doc.name

	def _variant(self, colour, size):
		return get_or_create_variant(
			self.item, {"Colour": colour, "Size": size, "Stage": "Piece"}
		)

	def _order_item_variant(self, size):
		return get_or_create_variant(self.item, {"Size": size, "Stage": "Pack"})

	def _make_lot(self):
		doc = frappe.new_doc("Lot")
		doc.lot_name = self._name("CU Lot")
		doc.item = self.item
		doc.production_detail = self.ipd
		doc.append("items", {"item_variant": self._order_item_variant("S"), "qty": 5})
		doc.append("items", {"item_variant": self._order_item_variant("M"), "qty": 5})
		doc.flags.items_derived = True  # keep the hand-built detail rows below
		doc.append(
			"lot_order_details",
			{"item_variant": self._variant("Black", "S"), "quantity": 10, "set_combination": {"major_colour": "Black"}},
		)
		doc.append(
			"lot_order_details",
			{"item_variant": self._variant("Black", "M"), "quantity": 20, "set_combination": {"major_colour": "Black"}},
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def grid(self):
		lot = frappe.get_doc("Lot", self.lot)
		ipd = frappe.get_doc("Item Production Detail", self.production_detail if hasattr(self, "production_detail") else self.ipd)
		return CU._colour_size_grid(lot, ipd)

	def split_payload(self, target="Black 2", s=4, m=8):
		return {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black", "size_quantities": {"S": 10 - s, "M": 20 - m}},
				{"colour": target, "size_quantities": {"S": s, "M": m}},
			],
		}


class TestColourUpdateContext(FrappeTestCase):
	def test_context_returns_grid_requirements_and_shared_state(self):
		fixture = ColourUpdateFixture()
		context = CU.get_colour_update_context(fixture.lot)
		self.assertEqual(context["packing_attribute"], "Colour")
		self.assertEqual([colour["colour"] for colour in context["colours"]], ["Black"])
		self.assertEqual(context["colours"][0]["size_quantities"], {"S": 10, "M": 20})
		self.assertFalse(context["shared_ipd"]["is_shared"])
		self.assertTrue(context["requirements"]["cutting"]["uses_colour"])
		self.assertTrue(context["requirements"]["cloth"]["uses_colour"])
		self.assertEqual(
			context["requirements"]["cutting"]["combinations"],
			[{"Size": "S"}, {"Size": "M"}],
		)
		self.assertEqual(context["requirements"]["cloth"]["combinations"], [{}])
		self.assertIn("Black 2", context["available_colours"])


class TestColourUpdateApply(FrappeTestCase):
	def _add_real_shape_structures(self, fixture):
		"""Mirror the Polar Sweat Shirt-1 IPD shape: stitching index groups,
		stitching accessory JSON and typed BOM attribute mappings."""
		process_name = frappe.db.get_value("Process", {"process_name": "CU Test Process"}, "name")
		if not process_name:
			process = frappe.new_doc("Process")
			process.process_name = "CU Test Process"
			process.insert(ignore_permissions=True)
			process_name = process.name
		for attribute in ("Name",):
			if not frappe.db.exists("Item Attribute", attribute):
				frappe.get_doc(
					{"doctype": "Item Attribute", "attribute_name": attribute}
				).insert(ignore_permissions=True)
		for value, attribute in (("ESSDEE", "Name"), ("White", "Colour")):
			if not frappe.db.exists(
				"Item Attribute Value", {"attribute_name": attribute, "attribute_value": value}
			):
				frappe.get_doc(
					{
						"doctype": "Item Attribute Value",
						"attribute_name": attribute,
						"attribute_value": value,
					}
				).insert(ignore_permissions=True)

		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		for part in ("Front", "Back"):
			ipd.append(
				"stiching_item_combination_details",
				{
					"major_attribute_value": "Black",
					"attribute_value": "Black",
					"set_item_attribute_value": part,
					"index": 0,
				},
			)
		ipd.stiching_accessory_json = json.dumps(
			{
				"select_list": ["MAIN FABRIC"],
				"attributes": ["Accessory", "Major Colour", "Accessory Colour", "Cloth"],
				"items": [
					{
						"accessory": "FOLDING",
						"major_colour": "Black",
						"accessory_colour": "Black",
						"cloth_type": "MAIN FABRIC",
					}
				],
				"is_set_item": 0,
			}
		)

		item_group = frappe.get_all("Item Group", limit_page_length=1)[0].name
		bom_item = frappe.new_doc("Item")
		bom_item.name1 = fixture._name("CU BOM Item")
		bom_item.item_group = item_group
		bom_item.default_unit_of_measure = frappe.db.get_value(
			"UOM", {"name": "Pieces"}, "name"
		) or frappe.db.get_value("UOM", {}, "name")
		bom_item.append("attributes", {"attribute": "Name"})
		bom_item.append("attributes", {"attribute": "Colour"})
		bom_item.append("attributes", {"attribute": "Size"})
		bom_item.insert(ignore_permissions=True)
		size_mapping_name = next(
			row.mapping for row in bom_item.attributes if row.attribute == "Size"
		)
		size_mapping = frappe.get_doc("Item Item Attribute Mapping", size_mapping_name)
		for size in fixture.sizes:
			size_mapping.append("values", {"attribute_value": size})
		size_mapping.save(ignore_permissions=True)

		mapping = frappe.new_doc("Item BOM Attribute Mapping")
		mapping.item_production_detail = fixture.ipd
		mapping.bom_item = bom_item.name
		mapping.append("item_attributes", {"attribute": "Colour"})
		mapping.append("item_attributes", {"attribute": "Size", "same_attribute": 1})
		mapping.append("bom_item_attributes", {"attribute": "Name"})
		mapping.append("bom_item_attributes", {"attribute": "Colour"})
		mapping.append("bom_item_attributes", {"attribute": "Size", "same_attribute": 1})
		for index, rows in (
			(
				0,
				[
					{"attribute": "Colour", "attribute_value": "Black", "type": "item", "quantity": 1},
					{"attribute": "Name", "attribute_value": "ESSDEE", "type": "bom", "quantity": 2.5},
					{"attribute": "Colour", "attribute_value": "White", "type": "bom", "quantity": 0.75},
				],
			),
		):
			for row in rows:
				row["index"] = index
				mapping.append("values", row)
		mapping.insert(ignore_permissions=True)
		ipd.append(
			"item_bom",
			{
				"item": bom_item.name,
				"process_name": process_name,
				"based_on_attribute_mapping": 1,
				"attribute_mapping": mapping.name,
				"qty_of_product": 1,
				"qty_of_bom_item": 1,
			},
		)
		ipd.save(ignore_permissions=True)
		return bom_item.name, mapping.name

	def test_split_clones_every_target_across_real_structures(self):
		# Regression for the Polar Sweat Shirt split (Navy -> Navy 1 + Navy 2):
		# BOTH targets must appear in stitching combinations (with one shared
		# group index each), stitching accessory JSON and every BOM mapping.
		fixture = ColourUpdateFixture()
		_, mapping_name = self._add_real_shape_structures(fixture)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black 2", "size_quantities": {"S": 6, "M": 12}},
				{"colour": "Red", "size_quantities": {"S": 4, "M": 8}},
			],
			"reason": "real shape split",
		}

		result = CU.apply_colour_update(
			fixture.lot,
			payload,
			expected_lot_modified=frappe.db.get_value("Lot", fixture.lot, "modified"),
			expected_ipd_modified=ipd.modified,
		)

		self.assertTrue(result["ok"])
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		groups = {}
		for row in ipd.stiching_item_combination_details:
			groups.setdefault(row.index, []).append(row)
		self.assertNotIn("Black", {r.major_attribute_value for r in ipd.stiching_item_combination_details})
		for colour in ("Black 2", "Red"):
			colour_indexes = [idx for idx, rows in groups.items() if rows[0].major_attribute_value == colour]
			self.assertEqual(len(colour_indexes), 1, "{0} stitching rows must share ONE group index".format(colour))
			rows = groups[colour_indexes[0]]
			self.assertEqual(
				sorted(r.set_item_attribute_value for r in rows), ["Back", "Front"]
			)
			self.assertTrue(all(r.attribute_value == colour for r in rows))
		self.assertEqual(
			[row.idx for row in ipd.stiching_item_combination_details],
			list(range(1, len(ipd.stiching_item_combination_details) + 1)),
		)

		accessory = json.loads(ipd.stiching_accessory_json)
		accessory_map = {i["major_colour"]: i["accessory_colour"] for i in accessory["items"]}
		# With the same packing/stitching attribute, an accessory colour that
		# matched the source follows each target; cloth selection stays intact.
		self.assertEqual(accessory_map.get("Black 2"), "Black 2")
		self.assertEqual(accessory_map.get("Red"), "Red")
		self.assertTrue(
			all(row["cloth_type"] == "MAIN FABRIC" for row in accessory["items"])
		)

		mapping = frappe.get_doc("Item BOM Attribute Mapping", mapping_name)
		self.assertEqual([row.idx for row in mapping.values], list(range(1, len(mapping.values) + 1)))
		bom_groups = {}
		for v in mapping.values:
			bom_groups.setdefault(v.index, []).append(v)
		for colour in ("Black 2", "Red"):
			colour_indexes = [
				idx
				for idx, rows in bom_groups.items()
				if any(r.type == "item" and r.attribute_value == colour for r in rows)
			]
			self.assertEqual(len(colour_indexes), 1, "{0} BOM rows must form ONE group".format(colour))
			rows = bom_groups[colour_indexes[0]]
			bom_side = sorted(
				(r.attribute, r.attribute_value, r.quantity) for r in rows if r.type == "bom"
			)
			self.assertEqual(
				bom_side, [("Colour", "White", 0.75), ("Name", "ESSDEE", 2.5)]
			)
		self.assertEqual(
			{(row.parentfield, row.attribute): row.same_attribute for row in mapping.item_attributes + mapping.bom_item_attributes},
			{
				("item_attributes", "Colour"): 0,
				("item_attributes", "Size"): 1,
				("bom_item_attributes", "Name"): 0,
				("bom_item_attributes", "Colour"): 0,
				("bom_item_attributes", "Size"): 1,
			},
		)

		lot = frappe.get_doc("Lot", fixture.lot)
		colour_row_indexes = {}
		for row in lot.lot_order_details:
			colour = frappe.db.get_value(
				"Item Variant Attribute",
				{"parent": row.item_variant, "attribute": "Colour"},
				"attribute_value",
			)
			set_combination = row.set_combination
			if isinstance(set_combination, str):
				set_combination = json.loads(set_combination)
			self.assertEqual(set_combination["major_colour"], colour)
			colour_row_indexes.setdefault(colour, set()).add(row.row_index)
		self.assertEqual(len(colour_row_indexes["Black 2"]), 1)
		self.assertEqual(len(colour_row_indexes["Red"]), 1)
		self.assertNotEqual(colour_row_indexes["Black 2"], colour_row_indexes["Red"])
		self.assertEqual([row.idx for row in lot.lot_order_details], list(range(1, len(lot.lot_order_details) + 1)))

	def test_split_preserves_configuration_and_totals(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		result = CU.apply_colour_update(
			fixture.lot,
			fixture.split_payload(),
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)

		self.assertTrue(result["ok"])
		self.assertFalse(result["duplicated_ipd"])

		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		packing_rows = {(row.attribute_value, row.quantity) for row in ipd.packing_attribute_details}
		self.assertIn(("Black 2", 0), packing_rows)
		self.assertIn(("Black", 0), packing_rows)
		self.assertEqual(ipd.packing_attribute_no, 2)
		self.assertEqual(ipd.approval_status, "Not Approved")
		self.assertIsNone(ipd.approved_by)

		cutting = json.loads(ipd.cutting_items_json)
		by_key = {(row["Size"], row["Colour"]): row for row in cutting["items"]}
		self.assertEqual(by_key[("S", "Black 2")]["Dia"], "20 Dia")
		self.assertEqual(by_key[("S", "Black 2")]["Weight"], 0.1)
		self.assertEqual(by_key[("M", "Black 2")]["Dia"], "22 Dia")
		self.assertEqual(by_key[("M", "Black 2")]["Weight"], 0.2)

		cloths = json.loads(ipd.cutting_cloths_json)
		self.assertIn(
			{"Colour": "Black 2", "Cloth": "OE Fabric"}, cloths["items"]
		)

		lot = frappe.get_doc("Lot", fixture.lot)
		rows = {}
		for row in lot.lot_order_details:
			attrs = frappe.get_all(
				"Item Variant Attribute",
				filters={"parent": row.item_variant},
				pluck="attribute_value",
			)
			rows[tuple(sorted(attrs))] = row.quantity
		self.assertEqual(rows[("Black 2", "Piece", "S")], 4)
		self.assertEqual(rows[("Black 2", "M", "Piece")], 8)
		self.assertEqual(rows[("Black", "Piece", "S")], 6)
		self.assertEqual(rows[("Black", "M", "Piece")], 12)
		self.assertEqual(lot.total_order_quantity, 30)
		# Split keeps the colour-independent item quantities untouched.
		self.assertEqual([item.qty for item in lot.items], [5, 5])
		self.assertIsNone(lot.bom_summary_json)
		self.assertEqual(lot.bom_summary, [])

	def test_split_allows_target_total_to_exceed_source(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black", "size_quantities": {"S": 2, "M": 4}},
				{"colour": "Black 2", "size_quantities": {"S": 12, "M": 24}},
			],
			"reason": "unbalanced split",
		}

		result = CU.apply_colour_update(
			fixture.lot,
			payload,
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)

		self.assertTrue(result["ok"])
		lot = frappe.get_doc("Lot", fixture.lot)
		rows = {}
		for row in lot.lot_order_details:
			attrs = frappe.get_all(
				"Item Variant Attribute",
				filters={"parent": row.item_variant},
				pluck="attribute_value",
			)
			rows[tuple(sorted(attrs))] = row.quantity
		self.assertEqual(rows[("Black", "Piece", "S")], 2)
		self.assertEqual(rows[("Black", "M", "Piece")], 4)
		self.assertEqual(rows[("Black 2", "Piece", "S")], 12)
		self.assertEqual(rows[("Black 2", "M", "Piece")], 24)
		self.assertEqual(lot.total_order_quantity, 42)

	def test_split_allows_target_total_below_source(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black", "size_quantities": {"S": 2, "M": 4}},
				{"colour": "Black 2", "size_quantities": {"S": 3, "M": 6}},
			],
			"reason": "reduced split quantity",
		}
		result = CU.apply_colour_update(
			fixture.lot,
			payload,
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)
		self.assertTrue(result["ok"])
		lot = frappe.get_doc("Lot", fixture.lot)
		self.assertEqual(lot.total_order_quantity, 15)
		self.assertEqual([item.qty for item in lot.items], [5, 10])

	def test_split_succeeds_when_mapping_only_has_source(self):
		# Regression: on real data the packing attribute mapping only contains
		# the colours configured so far. apply must persist the transformed
		# mapping BEFORE the IPD save, because packing_tab_validations reads it
		# from the DB and requires len(values) >= packing_attribute_no.
		fixture = ColourUpdateFixture()
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		mapping_name = next(
			row.mapping for row in ipd.item_attributes if row.attribute == "Colour"
		)
		mapping = frappe.get_doc("Item Item Attribute Mapping", mapping_name)
		mapping.set(
			"values",
			[row for row in mapping.values if row.attribute_value == "Black"],
		)
		mapping.save(ignore_permissions=True)

		lot = frappe.get_doc("Lot", fixture.lot)
		result = CU.apply_colour_update(
			fixture.lot,
			fixture.split_payload(),
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)

		self.assertTrue(result["ok"])
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual(ipd.packing_attribute_no, 2)
		mapping = frappe.get_doc("Item Item Attribute Mapping", mapping_name)
		self.assertEqual(
			sorted(row.attribute_value for row in mapping.values), ["Black", "Black 2"]
		)

	def test_conversion_removes_source_rows(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = fixture.split_payload()
		payload["targets"] = [{"colour": "Black 2", "size_quantities": {"S": 10, "M": 20}}]

		CU.apply_colour_update(
			fixture.lot, payload,
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual([row.attribute_value for row in ipd.packing_attribute_details], ["Black 2"])
		cutting = json.loads(ipd.cutting_items_json)
		self.assertFalse([row for row in cutting["items"] if row["Colour"] == "Black"])
		# The fully-removed source value is dropped from the packing mapping.
		mapping_name = next(
			row.mapping for row in ipd.item_attributes if row.attribute == "Colour"
		)
		mapping_values = frappe.get_all(
			"Item Item Attribute Mapping Value",
			filters={"parent": mapping_name},
			pluck="attribute_value",
		)
		self.assertNotIn("Black", mapping_values)
		self.assertIn("Black 2", mapping_values)
		lot = frappe.get_doc("Lot", fixture.lot)
		colours = set()
		for row in lot.lot_order_details:
			colours.add(
				frappe.db.get_value(
					"Item Variant Attribute",
					{"parent": row.item_variant, "attribute": "Colour"},
					"attribute_value",
				)
			)
		self.assertEqual(colours, {"Black 2"})
		self.assertEqual(lot.total_order_quantity, 30)

	def test_zero_quantity_source_target_does_not_retain_ipd_rows(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {
			"operation": "split_convert",
			"source_colour": "Black",
			"targets": [
				{"colour": "Black", "size_quantities": {"S": 0, "M": 0}},
				{"colour": "Black 2", "size_quantities": {"S": 10, "M": 20}},
			],
			"reason": "test zero source conversion",
		}
		CU.apply_colour_update(
			fixture.lot,
			payload,
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual(
			[row.attribute_value for row in ipd.packing_attribute_details], ["Black 2"]
		)
		cutting = json.loads(ipd.cutting_items_json)
		self.assertFalse([row for row in cutting["items"] if row["Colour"] == "Black"])

	def test_remove_reduces_total(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		CU.apply_colour_update(
			fixture.lot, fixture.split_payload(),
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {"operation": "remove", "source_colour": "Black", "targets": [], "reason": "test remove"}
		CU.apply_colour_update(
			fixture.lot, payload,
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		lot = frappe.get_doc("Lot", fixture.lot)
		colours = set()
		for row in lot.lot_order_details:
			colours.add(
				frappe.db.get_value(
					"Item Variant Attribute",
					{"parent": row.item_variant, "attribute": "Colour"},
					"attribute_value",
				)
			)
		self.assertEqual(colours, {"Black 2"})
		self.assertEqual(lot.total_order_quantity, 12)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual(
			[row.attribute_value for row in ipd.packing_attribute_details], ["Black 2"]
		)
		cutting = json.loads(ipd.cutting_items_json)
		self.assertFalse([row for row in cutting["items"] if row["Colour"] == "Black"])

	def test_add_increases_total_and_uses_inputs(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		ipd.cloth_accessory_json = json.dumps(
			{
				"combination_type": "Accessory",
				"attributes": ["Colour", "Accessory", "Dia", "Weight"],
				"items": [
					{
						"Colour": "Black",
						"Accessory": "FOLDING",
						"Dia": "26 Dia",
						"Weight": 0.01,
					}
				],
				"select_list": ["FOLDING"],
			}
		)
		ipd.stiching_accessory_json = json.dumps(
			{
				"attributes": ["Accessory", "Major Colour", "Accessory Colour", "Cloth"],
				"items": [
					{
						"accessory": "FOLDING",
						"major_colour": "Black",
						"accessory_colour": "Black",
						"cloth_type": "MAIN FABRIC",
					}
				],
				"select_list": ["MAIN FABRIC"],
			}
		)
		ipd.save(ignore_permissions=True)
		payload = {
			"operation": "add",
			"source_colour": None,
			"targets": [
				{
					"colour": "Red",
					"size_quantities": {"S": 7, "M": 3},
					"packing_quantity": 0,
					"set_or_stitching_mapping": {},
					"cutting_rows": [
						{"Size": "S", "Dia": "24 Dia", "Weight": 0.3},
						{"Size": "M", "Dia": "24 Dia", "Weight": 0.3},
					],
					"cloth_rows": [{"Cloth": "OE Fabric"}],
				}
			],
			"reference_colour": "Black",
			"reason": "test add",
		}

		CU.apply_colour_update(
			fixture.lot, payload,
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		lot = frappe.get_doc("Lot", fixture.lot)
		self.assertEqual(lot.total_order_quantity, 40)
		red_rows = {}
		for row in lot.lot_order_details:
			colour = frappe.db.get_value(
				"Item Variant Attribute",
				{"parent": row.item_variant, "attribute": "Colour"},
				"attribute_value",
			)
			size = frappe.db.get_value(
				"Item Variant Attribute",
				{"parent": row.item_variant, "attribute": "Size"},
				"attribute_value",
			)
			if colour == "Red":
				red_rows[size] = row.quantity
		self.assertEqual(red_rows, {"S": 7, "M": 3})

		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertIn(
			"Red", [row.attribute_value for row in ipd.packing_attribute_details]
		)
		cutting = json.loads(ipd.cutting_items_json)
		red_cutting = next(
			row for row in cutting["items"] if row.get("Size") == "S" and row.get("Colour") == "Red"
		)
		self.assertEqual(red_cutting, {"Size": "S", "Colour": "Red", "Dia": "24 Dia", "Weight": 0.3})
		self.assertEqual(list(red_cutting), cutting["attributes"])

		cloth = json.loads(ipd.cutting_cloths_json)
		red_cloth = next(row for row in cloth["items"] if row.get("Colour") == "Red")
		self.assertEqual(red_cloth, {"Colour": "Red", "Cloth": "OE Fabric"})
		self.assertEqual(list(red_cloth), cloth["attributes"])

		cloth_accessory = json.loads(ipd.cloth_accessory_json)
		red_accessory = next(
			row for row in cloth_accessory["items"] if row.get("Colour") == "Red"
		)
		self.assertEqual(
			red_accessory,
			{"Colour": "Red", "Accessory": "FOLDING", "Dia": "26 Dia", "Weight": 0.01},
		)
		self.assertEqual(list(red_accessory), cloth_accessory["attributes"])

		stitching_accessory = json.loads(ipd.stiching_accessory_json)
		red_stitching_accessory = next(
			row for row in stitching_accessory["items"] if row.get("major_colour") == "Red"
		)
		self.assertEqual(red_stitching_accessory["accessory_colour"], "Red")
		self.assertEqual(red_stitching_accessory["cloth_type"], "MAIN FABRIC")

	def test_add_requires_every_cutting_and_cloth_input(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = {
			"operation": "add",
			"source_colour": None,
			"targets": [
				{
					"colour": "Red",
					"size_quantities": {"S": 1},
					"cutting_rows": [],
					"cloth_rows": [],
				}
			],
			"reason": "missing configuration",
		}
		with self.assertRaises(frappe.ValidationError):
			CU.apply_colour_update(
				fixture.lot,
				payload,
				expected_lot_modified=lot.modified,
				expected_ipd_modified=ipd.modified,
			)
		self.assertEqual(
			[row.attribute_value for row in frappe.get_doc("Item Production Detail", fixture.ipd).packing_attribute_details],
			["Black"],
		)

	def test_stale_modified_blocks_without_partial_writes(self):
		fixture = ColourUpdateFixture()
		with self.assertRaises(frappe.ValidationError):
			CU.apply_colour_update(
				fixture.lot,
				fixture.split_payload(),
				expected_lot_modified="2000-01-01 00:00:00.000000",
				expected_ipd_modified=None,
			)
		lot = frappe.get_doc("Lot", fixture.lot)
		self.assertEqual(lot.total_order_quantity, 30)


class TestColourUpdateBlockers(FrappeTestCase):
	def _db_insert(self, doctype, values, docstatus=0):
		doc = frappe.new_doc(doctype)
		doc.update(values)
		doc.set_new_name()
		doc.docstatus = docstatus
		doc.db_insert()
		return doc.name

	def test_submitted_work_order_blocks_all_operations(self):
		fixture = ColourUpdateFixture()
		self._db_insert(
			"Work Order",
			{"lot": fixture.lot, "status": "Submitted", "wo_date": "2026-01-01"},
			docstatus=1,
		)
		for payload in (
			fixture.split_payload(),
			{"operation": "remove", "source_colour": "Black", "targets": [], "reason": "r"},
			{
				"operation": "add",
				"source_colour": None,
				"targets": [{"colour": "Red", "size_quantities": {"S": 1}}],
				"reason": "r",
			},
		):
			with self.assertRaises(frappe.ValidationError):
				CU.apply_colour_update(fixture.lot, payload)

	def test_draft_work_order_does_not_block(self):
		fixture = ColourUpdateFixture()
		self._db_insert(
			"Work Order", {"lot": fixture.lot, "status": "Draft", "wo_date": "2026-01-01"}
		)
		blockers, has = CU.find_colour_update_blockers(fixture.lot, "Black")
		self.assertFalse(has)

	def _make_laysheet(self, fixture, colour, status="Started"):
		name = self._db_insert("Cutting LaySheet", {"lot": fixture.lot, "status": status})
		detail = frappe.new_doc("Cutting LaySheet Detail")
		detail.update({"colour": colour})
		detail.parent = name
		detail.parenttype = "Cutting LaySheet"
		detail.parentfield = "details"
		detail.set_new_name()
		detail.db_insert()
		return name

	def test_affected_colour_laysheet_blocks_split_and_remove(self):
		fixture = ColourUpdateFixture()
		self._make_laysheet(fixture, "Black")
		blockers, has_blockers = CU.find_colour_update_blockers(fixture.lot, "Black")
		self.assertTrue(has_blockers)
		self.assertEqual(len(blockers["laysheets"]), 1)
		with self.assertRaises(frappe.ValidationError):
			CU.apply_colour_update(fixture.lot, fixture.split_payload())

	def test_other_colour_and_cancelled_laysheets_do_not_block(self):
		fixture = ColourUpdateFixture()
		self._make_laysheet(fixture, "Red")
		self._make_laysheet(fixture, "Black", status="Cancelled")
		blockers, has_blockers = CU.find_colour_update_blockers(fixture.lot, "Black")
		self.assertFalse(has_blockers)

	def test_add_ignores_source_laysheet_blocker(self):
		fixture = ColourUpdateFixture()
		self._make_laysheet(fixture, "Black")
		blockers, has_blockers = CU.find_colour_update_blockers(fixture.lot, None)
		self.assertFalse(has_blockers)


class TestSharedIPDHandling(FrappeTestCase):
	def test_shared_ipd_requires_confirmation_then_duplicates(self):
		fixture = ColourUpdateFixture()
		other = frappe.new_doc("Lot")
		other.lot_name = fixture._name("CU Other Lot")
		other.item = fixture.item
		other.production_detail = fixture.ipd
		other.flags.items_derived = True
		other.insert(ignore_permissions=True)

		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		payload = fixture.split_payload()

		with self.assertRaises(frappe.ValidationError):
			CU.apply_colour_update(
				fixture.lot, payload,
				expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
			)

		result = CU.apply_colour_update(
			fixture.lot, payload,
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
			confirmed_shared_ipd=True,
		)
		self.assertTrue(result["duplicated_ipd"])
		self.assertNotEqual(result["ipd"], fixture.ipd)

		# Current lot moved to the private duplicate; the other lot and the
		# original IPD are untouched.
		self.assertEqual(frappe.db.get_value("Lot", fixture.lot, "production_detail"), result["ipd"])
		self.assertEqual(frappe.db.get_value("Lot", other.name, "production_detail"), fixture.ipd)
		original = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual(
			[row.attribute_value for row in original.packing_attribute_details], ["Black"]
		)

		duplicate = frappe.get_doc("Item Production Detail", result["ipd"])
		self.assertIn(
			"Black 2", [row.attribute_value for row in duplicate.packing_attribute_details]
		)
		# Mappings must be independent: the duplicate's Colour mapping is a
		# different document whose rows can change without touching the source.
		source_mapping = next(
			row.mapping for row in original.item_attributes if row.attribute == "Colour"
		)
		duplicate_mapping = next(
			row.mapping for row in duplicate.item_attributes if row.attribute == "Colour"
		)
		self.assertNotEqual(source_mapping, duplicate_mapping)
		source_values = frappe.get_all(
			"Item Item Attribute Mapping Value",
			filters={"parent": source_mapping},
			pluck="attribute_value",
			order_by="idx",
		)
		duplicate_values = frappe.get_all(
			"Item Item Attribute Mapping Value",
			filters={"parent": duplicate_mapping},
			pluck="attribute_value",
		)
		self.assertEqual(source_values, ["Black", "Black 2", "Red"])
		self.assertIn("Black 2", duplicate_values)

	def test_duplicate_builder_keeps_sd_yrp_suppressed(self):
		fixture = ColourUpdateFixture()
		_, source_mapping_name = TestColourUpdateApply._add_real_shape_structures(self, fixture)
		source = frappe.get_doc("Item Production Detail", fixture.ipd)
		duplicate = CU.build_ipd_duplicate(source)
		self.assertTrue(duplicate.flags.skip_sd_yrp_sync)
		self.assertTrue(duplicate.name)
		self.assertNotEqual(duplicate.name, source.name)

		# Exactly one BOM mapping is created for the duplicate's one mapped BOM
		# row. Earlier staging created an extra empty/orphan mapping.
		duplicate_mapping_names = frappe.get_all(
			"Item BOM Attribute Mapping",
			filters={"item_production_detail": duplicate.name},
			pluck="name",
		)
		self.assertEqual(len(duplicate_mapping_names), 1)
		duplicate_mapping = frappe.get_doc(
			"Item BOM Attribute Mapping", duplicate_mapping_names[0]
		)
		self.assertNotEqual(duplicate_mapping.name, source_mapping_name)
		self.assertEqual(duplicate.item_bom[0].attribute_mapping, duplicate_mapping.name)

		source_mapping = frappe.get_doc("Item BOM Attribute Mapping", source_mapping_name)
		def attribute_configuration(mapping):
			return sorted(
				(row.parentfield, row.idx, row.attribute, row.same_attribute)
				for row in mapping.item_attributes + mapping.bom_item_attributes
			)

		def value_configuration(mapping):
			return sorted(
				(row.index, row.type, row.attribute, row.attribute_value, row.quantity)
				for row in mapping.values
			)

		self.assertEqual(
			attribute_configuration(duplicate_mapping),
			attribute_configuration(source_mapping),
		)
		self.assertEqual(
			value_configuration(duplicate_mapping),
			value_configuration(source_mapping),
		)


class TestProcessCostHandling(FrappeTestCase):
	def _make_process_cost(self, fixture, docstatus=0):
		uom = frappe.db.get_value("UOM", {}, "name")
		doc = frappe.new_doc("Process Cost")
		doc.item = fixture.item
		doc.from_date = "2026-01-01"
		doc.to_date = "2026-12-31"
		doc.process_name = frappe.get_value("Process", {}, "name") or "_Test Process"
		doc.uom = uom
		doc.tax_slab = frappe.get_value("Tax Slab", {}, "name")
		doc.lot = fixture.lot
		doc.supplier = frappe.get_value("Supplier", {}, "name")
		doc.depends_on_attribute = 1
		doc.attribute = "Colour"
		doc.append("process_cost_values", {"attribute_value": "Black", "price": 10, "min_order_qty": 100})
		doc.insert(ignore_permissions=True)
		if docstatus:
			doc.submit()
		return doc.name

	def test_draft_process_cost_updates_in_place(self):
		fixture = ColourUpdateFixture()
		name = self._make_process_cost(fixture)
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		CU.apply_colour_update(
			fixture.lot, fixture.split_payload(),
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		values = frappe.get_all(
			"Process Cost Value",
			filters={"parent": name, "parentfield": "process_cost_values"},
			fields=["attribute_value", "price", "min_order_qty"],
			order_by="idx",
		)
		by_colour = {row.attribute_value: row for row in values}
		self.assertIn("Black 2", by_colour)
		self.assertEqual(by_colour["Black 2"].price, 10)
		self.assertEqual(by_colour["Black 2"].min_order_qty, 100)

	def test_submitted_process_cost_gets_draft_replacement(self):
		fixture = ColourUpdateFixture()
		name = self._make_process_cost(fixture, docstatus=1)
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		result = CU.apply_colour_update(
			fixture.lot, fixture.split_payload(),
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)

		self.assertEqual(len(result["process_costs"]), 1)
		replacement = result["process_costs"][0]
		self.assertNotEqual(replacement, name)
		self.assertEqual(frappe.db.get_value("Process Cost", name, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Process Cost", replacement, "docstatus"), 0)
		self.assertIsNone(frappe.db.get_value("Process Cost", replacement, "amended_from"))
		values = frappe.get_all(
			"Process Cost Value",
			filters={"parent": replacement, "parentfield": "process_cost_values"},
			pluck="attribute_value",
		)
		self.assertIn("Black 2", values)
		self.assertIn("Black", values)


class TestRollback(FrappeTestCase):
	def test_exception_after_duplication_rolls_everything_back(self):
		fixture = ColourUpdateFixture()
		other = frappe.new_doc("Lot")
		other.lot_name = fixture._name("CU Other")
		other.item = fixture.item
		other.production_detail = fixture.ipd
		other.flags.items_derived = True
		other.insert(ignore_permissions=True)

		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		original_add_comment = FrappeDocument.add_comment

		def boom(*args, **kwargs):
			raise RuntimeError("injected failure")

		FrappeDocument.add_comment = boom
		frappe.db.savepoint("cu_colour_update_rollback")
		try:
			CU.apply_colour_update(
				fixture.lot, fixture.split_payload(),
				expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
				confirmed_shared_ipd=True,
			)
			self.fail("expected the injected failure")
		except RuntimeError:
			# A real HTTP request rolls the transaction back on failure; undo
			# to the savepoint to assert the same atomicity guarantee.
			frappe.db.rollback(save_point="cu_colour_update_rollback")
		finally:
			FrappeDocument.add_comment = original_add_comment

		# Everything rolled back: no duplicate IPD, no relink, no row changes.
		self.assertEqual(frappe.db.get_value("Lot", fixture.lot, "production_detail"), fixture.ipd)
		duplicates = frappe.get_all(
			"Item Production Detail", filters={"item": fixture.item, "name": ["!=", fixture.ipd]}
		)
		self.assertEqual(duplicates, [])
		rows = frappe.get_all("Lot Order Detail", filters={"parent": fixture.lot}, pluck="quantity")
		self.assertEqual(sorted(rows), [10.0, 20.0])


class TestPanelWiseColourUpdate(FrappeTestCase):
	def test_split_transforms_compact_matrices_and_expanded_json(self):
		fixture = ColourUpdateFixture(panel_wise=True)
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)

		result = CU.apply_colour_update(
			fixture.lot, fixture.split_payload(),
			expected_lot_modified=lot.modified, expected_ipd_modified=ipd.modified,
		)
		self.assertTrue(result["ok"])

		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		consumption = json.loads(ipd.panel_wise_consumption_matrix_json)
		self.assertIn("Black 2", consumption["packing_values"])
		panel = consumption["panels"][0]
		self.assertIn("Black 2", panel["packing_values"])
		for row in panel["rows"]:
			self.assertEqual(row["values"]["Black 2"], {"dia": "20 Dia", "weight": 0.1})
			# Black is retained by this split, so its original cells survive.
			self.assertEqual(row["values"]["Black"], {"dia": "20 Dia", "weight": 0.1})

		cloth = json.loads(ipd.panel_wise_cloth_mapping_json)
		self.assertEqual(
			cloth["panels"][0]["rows"][0]["values"]["Black 2"], {"cloth": "OE Fabric"}
		)

		# The save-time sync regenerated the expanded cutting rows from the
		# transformed compact matrix.
		cutting = json.loads(ipd.cutting_items_json)
		black_2_rows = [row for row in cutting["items"] if row["Colour"] == "Black 2"]
		self.assertEqual(len(black_2_rows), 2)
		for row in black_2_rows:
			self.assertEqual(row["Dia"], "20 Dia")
			self.assertEqual(row["Weight"], 0.1)


class TestColourUpdatePreviewAndScope(FrappeTestCase):
	def test_preview_does_not_write(self):
		fixture = ColourUpdateFixture()
		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		result = CU.preview_colour_update(
			fixture.lot,
			fixture.split_payload(),
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)
		self.assertTrue(result["ok"])
		self.assertFalse(result["conflicts"])
		reloaded = frappe.get_doc("Item Production Detail", fixture.ipd)
		self.assertEqual(
			[row.attribute_value for row in reloaded.packing_attribute_details], ["Black"]
		)
		self.assertEqual(frappe.db.get_value("Lot", fixture.lot, "total_order_quantity"), 30)

	def test_cutting_plan_and_grn_do_not_block(self):
		fixture = ColourUpdateFixture()
		plan = frappe.new_doc("Cutting Plan")
		plan.lot = fixture.lot
		plan.set_new_name()
		plan.db_insert()
		grn = frappe.new_doc("Goods Received Note")
		grn.lot = fixture.lot
		grn.set_new_name()
		grn.db_insert()
		blockers, has_blockers = CU.find_colour_update_blockers(fixture.lot, "Black")
		self.assertFalse(has_blockers)
		self.assertEqual(blockers["submitted_work_orders"], [])
		self.assertEqual(blockers["laysheets"], [])

	def test_process_cost_on_other_attribute_is_unchanged(self):
		fixture = ColourUpdateFixture()
		uom = frappe.db.get_value("UOM", {}, "name")
		doc = frappe.new_doc("Process Cost")
		doc.item = fixture.item
		doc.from_date = "2026-01-01"
		doc.to_date = "2026-12-31"
		doc.process_name = frappe.get_value("Process", {}, "name") or "_Test Process"
		doc.uom = uom
		doc.tax_slab = frappe.get_value("Tax Slab", {}, "name")
		doc.lot = fixture.lot
		doc.supplier = frappe.get_value("Supplier", {}, "name")
		doc.depends_on_attribute = 1
		doc.attribute = "Size"
		doc.append("process_cost_values", {"attribute_value": "S", "price": 9, "min_order_qty": 1})
		doc.insert(ignore_permissions=True)
		name = doc.name

		lot = frappe.get_doc("Lot", fixture.lot)
		ipd = frappe.get_doc("Item Production Detail", fixture.ipd)
		CU.apply_colour_update(
			fixture.lot,
			fixture.split_payload(),
			expected_lot_modified=lot.modified,
			expected_ipd_modified=ipd.modified,
		)

		values = frappe.get_all(
			"Process Cost Value",
			filters={"parent": name, "parentfield": "process_cost_values"},
			fields=["attribute_value", "price"],
		)
		self.assertEqual(len(values), 1)
		self.assertEqual(values[0].attribute_value, "S")
		self.assertEqual(values[0].price, 9)
