from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from production_api.essdee_production.doctype.item_production_detail import (
	item_production_detail,
)


class LotStub(SimpleNamespace):
	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def save(self):
		self.saved = True


class TestBOMProcessGrouping(TestCase):
	def test_same_mapped_variant_is_split_between_its_bom_processes(self):
		fusing_item = "Fusing Sticker-MoveWarm (40-73)"
		fusing_variant = f"{fusing_item}-40 cm-White"
		bom_rows = [
			SimpleNamespace(
				item=fusing_item,
				process_name="Yolk Fusing",
				based_on_attribute_mapping=1,
				qty_of_product=1,
				qty_of_bom_item=1,
				dependent_attribute_value="Piece",
			),
			SimpleNamespace(
				item=fusing_item,
				process_name="Bottom Fusing",
				based_on_attribute_mapping=1,
				qty_of_product=1,
				qty_of_bom_item=1,
				dependent_attribute_value="Piece",
			),
		]
		ipd = SimpleNamespace(
			item_bom=bom_rows,
			cloth_detail=[],
			dependent_attribute="Part",
			dependent_attribute_mapping="Part Mapping",
			cutting_process="Cutting",
			packing_attribute="Colour",
			packing_combo=1,
			is_set_item=1,
		)
		lot = LotStub(
			item="Garment",
			total_order_quantity=1300,
			pack_in_stage="Piece",
			pack_out_stage="Packed",
			packing_uom="Nos",
		)
		lot_item = SimpleNamespace(
			default_unit_of_measure="Nos",
			uom_conversion_details=[],
		)
		variants = {
			"Garment-40 cm-Top": SimpleNamespace(
				attributes=[
					SimpleNamespace(attribute="Size", attribute_value="40 cm"),
					SimpleNamespace(attribute="Part", attribute_value="Top"),
				]
			),
			"Garment-40 cm-Bottom": SimpleNamespace(
				attributes=[
					SimpleNamespace(attribute="Size", attribute_value="40 cm"),
					SimpleNamespace(attribute="Part", attribute_value="Bottom"),
				]
			),
		}
		bom_combination = {
			fusing_item: [
				{
					"keys": ["Part"],
					"same_attributes": ["Size"],
					0: {
						"key": {"Part": "Top"},
						"value": {"Colour": "White"},
						"qty_of_bom": 1,
					},
				},
				{
					"keys": ["Part"],
					"same_attributes": ["Size"],
					0: {
						"key": {"Part": "Bottom"},
						"value": {"Colour": "White"},
						"qty_of_bom": 1,
					},
				},
			]
		}

		def get_cached_doc(doctype, name):
			if doctype == "Item Production Detail":
				return ipd
			if doctype == "Lot":
				return lot
			if doctype == "Item":
				return lot_item
			if doctype == "Item Variant":
				return variants[name]
			raise AssertionError(f"Unexpected document lookup: {doctype} {name}")

		with (
			patch.object(
				item_production_detail.frappe,
				"get_cached_doc",
				side_effect=get_cached_doc,
			),
			patch.object(
				item_production_detail.frappe,
				"get_value",
				return_value="Nos",
			),
			patch.object(item_production_detail, "get_cloth_combination", return_value={}),
			patch.object(item_production_detail, "get_stitching_combination", return_value={}),
			patch.object(
				item_production_detail,
				"get_bom_combination",
				return_value=bom_combination,
			),
			patch.object(item_production_detail, "calculate_cloth", return_value=[]),
			patch.object(
				item_production_detail,
				"get_dependent_attribute_details",
				return_value={"attr_list": {"Piece": {"uom": "Nos"}}},
			),
			patch.object(
				item_production_detail,
				"get_or_create_variant",
				return_value=fusing_variant,
			),
			patch.object(item_production_detail, "now_datetime", return_value="2026-10-07"),
		):
			item_production_detail.get_calculated_bom.__wrapped__(
				"IPD-001",
				[
					{"item_variant": "Garment-40 cm-Top", "quantity": 650},
					{"item_variant": "Garment-40 cm-Bottom", "quantity": 650},
				],
				"LOT-001",
			)
			single_process_bom = item_production_detail.get_calculated_bom.__wrapped__(
				"IPD-001",
				[
					{"item_variant": "Garment-40 cm-Top", "quantity": 650},
					{"item_variant": "Garment-40 cm-Bottom", "quantity": 650},
				],
				"LOT-001",
				process_name="Yolk Fusing",
			)

		self.assertEqual(
			sorted(
				(row["process_name"], row["required_qty"])
				for row in lot.bom_summary
			),
			[("Bottom Fusing", 650), ("Yolk Fusing", 650)],
		)
		self.assertEqual({row["item_name"] for row in lot.bom_summary}, {fusing_variant})
		self.assertEqual(
			single_process_bom,
			{fusing_item: {fusing_variant: [650, "Yolk Fusing", "Nos"]}},
		)
