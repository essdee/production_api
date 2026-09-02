from unittest import TestCase
from unittest.mock import MagicMock, patch as mock_patch

import frappe

from production_api.patches.v1_0 import consolidate_yarn_items_by_colour as patch


class TestConsolidateYarnItemsByColour(TestCase):
	def test_hardcoded_mapping_has_expected_shape(self):
		item_map, variant_map = patch.build_name_maps()

		self.assertEqual(len(patch.YARN_ITEM_GROUPS), 14)
		self.assertEqual(len(item_map), 89)
		self.assertEqual(len(variant_map), 89)
		self.assertEqual(len(patch.ATTRIBUTE_ONLY_ITEMS), 35)
		self.assertNotIn("’", "".join(patch.YARN_ITEM_GROUPS))

	def test_spaced_yarn_25_item_maps_to_correct_parent_and_variant(self):
		item_map, variant_map = patch.build_name_maps()

		self.assertEqual(item_map["Yarn 25 's AF Navy"], "Yarn 25's")
		self.assertEqual(
			variant_map["Yarn 25 's AF Navy"],
			"Yarn 25's-AF Navy",
		)

	def test_duplicate_maroon_items_merge_into_one_variant(self):
		_item_map, variant_map = patch.build_name_maps()

		self.assertEqual(
			variant_map["Yarn 25 's OE Maroon"],
			"Yarn 25's OE-Maroon",
		)
		self.assertEqual(
			variant_map["Yarn 25's OE Maroon"],
			"Yarn 25's OE-Maroon",
		)

	def test_tomato_red_uses_the_existing_canonical_colour_value(self):
		_item_map, variant_map = patch.build_name_maps()

		self.assertEqual(
			variant_map["Yarn 25 's OE Tomato Red"],
			"Yarn 25's OE-TOMATO RED",
		)

	def test_blank_colour_rows_use_greige_without_parent_consolidation(self):
		item_map, _variant_map = patch.build_name_maps()
		attribute_only_variant_map = patch.build_attribute_only_variant_map()

		self.assertNotIn("Yarn 30's OE Cotton", item_map)
		self.assertNotIn("Yarn 28's OE Black", item_map)
		self.assertNotIn("Yarn 100D Poly Yarn", item_map)
		self.assertIn("Yarn 100D Poly Yarn", patch.ATTRIBUTE_ONLY_ITEMS)
		self.assertIn("Yarn 25's RL", patch.ATTRIBUTE_ONLY_ITEMS)
		self.assertEqual(
			attribute_only_variant_map["Yarn 36's GL"],
			"Yarn 36's GL-Greige",
		)
		self.assertEqual(
			len(attribute_only_variant_map),
			len(patch.ATTRIBUTE_ONLY_ITEMS),
		)

	def test_colour_is_not_kept_as_the_primary_attribute(self):
		doc = MagicMock()
		doc.attributes = [
			frappe._dict(attribute=patch.COLOUR_ATTRIBUTE, mapping="COLOUR-MAPPING")
		]
		doc.primary_attribute = patch.COLOUR_ATTRIBUTE

		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=True),
			mock_patch.object(patch.frappe, "get_doc", return_value=doc),
			mock_patch.object(patch.frappe, "clear_document_cache"),
		):
			patch.ensure_item_colour_attribute("Yarn 36's GL")

		self.assertIsNone(doc.primary_attribute)
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_json_replacement_changes_only_exact_keys_and_values(self):
		old_variant = "Yarn 25's OE Black"
		new_variant = "Yarn 25's OE-Black"
		value = {
			old_variant: {
				"item": old_variant,
				"description": f"Uses {old_variant}",
			},
			"items": [old_variant, "Unchanged"],
		}

		updated, changed = patch.replace_exact_json_values(
			value,
			{old_variant: new_variant},
		)

		self.assertTrue(changed)
		self.assertIn(new_variant, updated)
		self.assertEqual(updated[new_variant]["item"], new_variant)
		self.assertEqual(
			updated[new_variant]["description"],
			f"Uses {old_variant}",
		)
		self.assertEqual(updated["items"], [new_variant, "Unchanged"])

	def test_json_key_collision_is_rejected(self):
		with self.assertRaises(patch.JsonKeyCollisionError):
			patch.replace_exact_json_values(
				{"Old A": 1, "Old B": 2},
				{"Old A": "New", "Old B": "New"},
			)
