from unittest import TestCase
from unittest.mock import MagicMock, patch as mock_patch

import frappe

from production_api.patches.v1_0 import consolidate_yarn_items_by_colour as patch
from production_api.patches.v1_0 import mark_consolidated_yarn_items_as_stock as stock_patch


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
		doc.is_stock_item = 1

		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=True),
			mock_patch.object(patch.frappe, "get_doc", return_value=doc),
			mock_patch.object(patch.frappe, "clear_document_cache"),
		):
			patch.ensure_item_colour_attribute("Yarn 36's GL")

		self.assertIsNone(doc.primary_attribute)
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_existing_targets_and_greige_items_are_enabled_for_stock(self):
		for item_name in (*patch.YARN_ITEM_GROUPS, *patch.ATTRIBUTE_ONLY_ITEMS):
			with self.subTest(item=item_name):
				doc = MagicMock()
				doc.attributes = [
					frappe._dict(attribute=patch.COLOUR_ATTRIBUTE, mapping="COLOUR-MAPPING")
				]
				doc.primary_attribute = None
				doc.is_stock_item = 0
				with (
					mock_patch.object(patch.frappe.db, "exists", return_value=True),
					mock_patch.object(patch.frappe, "get_doc", return_value=doc),
					mock_patch.object(patch.frappe, "clear_document_cache"),
				):
					self.assertTrue(patch.ensure_item_colour_attribute(item_name))
				self.assertEqual(doc.is_stock_item, 1)
				self.assertIsNone(doc.primary_attribute)
				doc.save.assert_called_once_with(ignore_permissions=True)

	def test_stock_enabled_item_is_not_saved_again_on_rerun(self):
		doc = MagicMock()
		doc.attributes = [
			frappe._dict(attribute=patch.COLOUR_ATTRIBUTE, mapping="COLOUR-MAPPING")
		]
		doc.primary_attribute = None
		doc.is_stock_item = 1
		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=True),
			mock_patch.object(patch.frappe, "get_doc", return_value=doc),
			mock_patch.object(patch.frappe, "clear_document_cache"),
		):
			patch.ensure_item_colour_attribute("Yarn 36's GL")
		doc.save.assert_not_called()

	def test_missing_attribute_only_item_is_not_created(self):
		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=False),
			mock_patch.object(patch.frappe, "get_doc") as get_doc,
		):
			self.assertFalse(patch.ensure_item_colour_attribute("Missing Yarn"))
		get_doc.assert_not_called()

	def test_new_target_is_stock_item_even_when_source_is_not(self):
		target = "Yarn 25's OE"
		source = "Yarn 25's OE Black"
		source_doc = MagicMock(is_stock_item=0)
		doc = MagicMock()
		doc.name = target
		doc.is_stock_item = 0
		doc.insert.side_effect = lambda **kwargs: self.assertEqual(doc.is_stock_item, 1)
		with (
			mock_patch.object(patch.frappe.db, "exists", side_effect=lambda dt, name: name == source),
			mock_patch.object(patch.frappe, "get_doc", return_value=source_doc),
			mock_patch.object(patch.frappe, "copy_doc", return_value=doc),
		):
			self.assertIs(patch.ensure_target_item(target, [(source, "Black")]), doc)
		doc.insert.assert_called_once_with(ignore_permissions=True)
		self.assertIsNone(doc.primary_attribute)
		self.assertEqual(source_doc.is_stock_item, 0)

	def test_existing_target_uses_stock_and_colour_normalization(self):
		target = "Yarn 25's OE"
		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=True),
			mock_patch.object(patch, "ensure_item_colour_attribute") as ensure_item,
			mock_patch.object(patch.frappe, "get_doc"),
			mock_patch.object(patch.frappe, "copy_doc") as copy_doc,
		):
			patch.ensure_target_item(target, [("Yarn 25's OE Black", "Black")])
		ensure_item.assert_called_once_with(target)
		copy_doc.assert_not_called()

	def test_stock_backfill_only_updates_existing_nonstock_mapped_items(self):
		items = [
			frappe._dict(name="Yarn 25's OE", is_stock_item=0),
			frappe._dict(name="Yarn 36's GL", is_stock_item=None),
			frappe._dict(name="Yarn 40's GL", is_stock_item=1),
		]
		with (
			mock_patch.object(stock_patch.frappe.local, "site", patch.TARGET_SITE),
			mock_patch.object(stock_patch.frappe, "get_all", return_value=items) as get_all,
			mock_patch.object(stock_patch.frappe.db, "set_value") as set_value,
			mock_patch.object(stock_patch.frappe, "clear_document_cache") as clear_cache,
		):
			stock_patch.execute()
		get_all.assert_called_once_with(
			"Item",
			filters={"name": ["in", list(patch.YARN_ITEM_GROUPS) + list(patch.ATTRIBUTE_ONLY_ITEMS)]},
			fields=["name", "is_stock_item"],
		)
		self.assertEqual(set_value.call_count, 2)
		set_value.assert_any_call("Item", "Yarn 25's OE", "is_stock_item", 1)
		set_value.assert_any_call("Item", "Yarn 36's GL", "is_stock_item", 1)
		self.assertEqual(clear_cache.call_count, 2)

	def test_stock_backfill_is_noop_after_items_are_enabled(self):
		with (
			mock_patch.object(stock_patch.frappe.local, "site", patch.TARGET_SITE),
			mock_patch.object(stock_patch.frappe, "get_all", return_value=[
				frappe._dict(name=name, is_stock_item=1)
				for name in (*patch.YARN_ITEM_GROUPS, *patch.ATTRIBUTE_ONLY_ITEMS)
			]),
			mock_patch.object(stock_patch.frappe.db, "set_value") as set_value,
		):
			stock_patch.execute()
		set_value.assert_not_called()

	def test_stock_backfill_skips_other_sites(self):
		with (
			mock_patch.object(stock_patch.frappe.local, "site", "other.site"),
			mock_patch.object(stock_patch.frappe, "get_all") as get_all,
		):
			stock_patch.execute()
		get_all.assert_not_called()

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
