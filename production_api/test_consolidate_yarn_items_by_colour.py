from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch as mock_patch

import frappe

from production_api.patches.v1_0 import consolidate_yarn_items_by_colour as patch
from production_api.patches.v1_0 import mark_consolidated_yarn_items_as_stock as stock_patch


class TestConsolidateYarnItemsByColour(TestCase):
	def test_consolidation_converts_yarn_and_retained_greige_items(self):
		target = "Yarn 25's OE"
		source = "Yarn 25's OE Black"
		greige_item = "Yarn 36's GL"
		source_rows = ((source, "Black"),)
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {
				target: source_rows + (("Absent Navy Yarn", "Navy"),),
				"Absent Target": (("Absent Source", "White"),),
			}),
			mock_patch.object(patch, "ATTRIBUTE_ONLY_ITEMS", (greige_item,)),
			mock_patch.object(patch, "prepare_migration", return_value=(
				{source: target}, {source: f"{target}-Black"},
				{greige_item: f"{greige_item}-Greige"}, [], []
			)) as prepare,
			mock_patch.object(patch, "ensure_item_colour_attribute") as ensure_attribute,
			mock_patch.object(patch, "ensure_target_colours") as ensure_colours,
			mock_patch.object(patch, "ensure_target_item") as ensure_target,
			mock_patch.object(patch, "convert_or_merge_variant") as convert_variant,
			mock_patch.object(patch, "merge_source_item") as merge_item,
			mock_patch.object(patch, "apply_json_updates") as update_json,
			mock_patch.object(patch.frappe, "clear_cache"),
		):
			patch.execute()
		prepare.assert_called_once_with()
		ensure_attribute.assert_called_once_with(greige_item)
		ensure_colours.assert_any_call(greige_item, ["Greige"])
		ensure_colours.assert_any_call(target, ["Black"])
		ensure_target.assert_called_once_with(target, source_rows)
		convert_variant.assert_any_call(greige_item, greige_item, "Greige")
		convert_variant.assert_any_call(source, target, "Black")
		self.assertEqual(convert_variant.call_count, 2)
		self.assertEqual(ensure_colours.call_count, 2)
		merge_item.assert_called_once_with(source, target)
		update_json.assert_called_once_with([])

	def test_consolidation_reports_data_errors_before_updates(self):
		with (
			mock_patch.object(
				patch, "prepare_migration", side_effect=frappe.ValidationError("Invalid mapping")
			),
			mock_patch.object(patch, "ensure_target_item") as ensure_target,
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Invalid mapping"):
				patch.execute()
		ensure_target.assert_not_called()

	def test_preflight_returns_migration_summary(self):
		with mock_patch.object(patch, "prepare_migration", return_value=(
			{}, {}, {}, [], []
		)) as prepare:
			result = patch.preflight()
		prepare.assert_called_once_with()
		self.assertEqual(result["target_item_count"], 0)
		self.assertEqual(result["source_item_count"], 0)
		self.assertEqual(len(result["skipped_source_items"]), 89)
		self.assertEqual(result["json_update_count"], 0)

	def test_preflight_reports_data_errors(self):
		with mock_patch.object(
			patch, "prepare_migration", side_effect=frappe.ValidationError("Invalid mapping")
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Invalid mapping"):
				patch.preflight()

	def test_patch_entries_retry_previously_recorded_noops_in_dependency_order(self):
		entries = Path(__file__).with_name("patches.txt").read_text().splitlines()
		consolidation = "production_api.patches.v1_0.consolidate_yarn_items_by_colour"
		stock_update = "production_api.patches.v1_0.mark_consolidated_yarn_items_as_stock"
		for module in (consolidation, stock_update):
			self.assertIn(f"{module} #3", entries)
			self.assertNotIn(f"{module} #1", entries)
			self.assertNotIn(f"{module} #2", entries)
		self.assertLess(entries.index(f"{consolidation} #3"), entries.index(f"{stock_update} #3"))

	def test_hardcoded_mapping_has_expected_shape(self):
		item_map, variant_map = patch.build_name_maps()

		self.assertEqual(len(patch.YARN_ITEM_GROUPS), 14)
		self.assertEqual(len(item_map), 89)
		self.assertEqual(len(variant_map), 89)
		self.assertEqual(len(patch.ATTRIBUTE_ONLY_ITEMS), 35)
		self.assertNotIn("’", "".join(patch.YARN_ITEM_GROUPS))

	def test_duplicate_source_names_in_configuration_are_rejected(self):
		with mock_patch.object(patch, "YARN_ITEM_GROUPS", {
			"Target A": (("Same Source", "Black"),),
			"Target B": (("Same Source", "White"),),
		}):
			with self.assertRaisesRegex(frappe.ValidationError, "duplicate legacy Item"):
				patch.build_name_maps()

	def test_absent_mapping_rows_are_excluded(self):
		item_map = {"Existing Yarn": "Target A", "Missing Yarn": "Target B"}
		variant_map = {"Existing Yarn": "Target A-Black", "Missing Yarn": "Target B-White"}
		with mock_patch.object(patch.frappe.db, "exists", side_effect=(
			lambda dt, name: dt == "Item" and name == "Existing Yarn"
		)):
			items, variants = patch.select_existing_name_maps(item_map, variant_map)
		self.assertEqual(items, {"Existing Yarn": "Target A"})
		self.assertEqual(variants, {"Existing Yarn": "Target A-Black"})

	def test_existing_target_alone_does_not_create_missing_colours(self):
		with mock_patch.object(patch.frappe.db, "exists", side_effect=(
			lambda dt, name: dt == "Item" and name == "Target"
		)):
			self.assertEqual(patch.select_existing_name_maps(
				{"Missing Yarn": "Target"}, {"Missing Yarn": "Target-Black"}
			), ({}, {}))

	def test_already_converted_variant_keeps_mapping_active_on_rerun(self):
		with mock_patch.object(patch.frappe.db, "exists", side_effect=(
			lambda dt, name: (dt, name) in {
				("Item", "Target"), ("Item Variant", "Target-Black")
			}
		)):
			self.assertEqual(patch.select_existing_name_maps(
				{"Old Yarn": "Target"}, {"Old Yarn": "Target-Black"}
			), ({"Old Yarn": "Target"}, {"Old Yarn": "Target-Black"}))

	def test_orphaned_legacy_variant_is_not_treated_as_absent(self):
		with mock_patch.object(patch.frappe.db, "exists", side_effect=(
			lambda dt, name: dt == "Item Variant" and name == "Old Yarn"
		)):
			with self.assertRaisesRegex(frappe.ValidationError, "without its parent Item"):
				patch.select_existing_name_maps(
					{"Old Yarn": "Target"}, {"Old Yarn": "Target-Black"}
				)

	def test_empty_database_needs_no_colour_master_and_performs_no_updates(self):
		with (
			mock_patch.object(patch.frappe.db, "exists", return_value=False),
			mock_patch.object(patch, "validate_mapping_state") as validate,
			mock_patch.object(patch, "collect_json_updates") as collect,
			mock_patch.object(patch, "ensure_target_item") as ensure_target,
			mock_patch.object(patch, "ensure_item_colour_attribute") as ensure_attribute,
			mock_patch.object(patch, "apply_json_updates") as apply_json,
			mock_patch.object(patch.frappe, "clear_cache") as clear_cache,
			mock_patch("builtins.print") as output,
		):
			patch.execute()
		validate.assert_not_called()
		collect.assert_not_called()
		ensure_target.assert_not_called()
		ensure_attribute.assert_not_called()
		apply_json.assert_not_called()
		clear_cache.assert_not_called()
		output.assert_called_once_with(
			"No mapped yarn Items or variants found; nothing to consolidate."
		)

	def test_prepare_uses_only_present_variants_for_json_rewrites(self):
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {
				"Target": (("Existing Yarn", "Black"), ("Missing Yarn", "White")),
			}),
			mock_patch.object(patch, "ATTRIBUTE_ONLY_ITEMS", ()),
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: dt == "Item" and name == "Existing Yarn"
			)),
			mock_patch.object(patch, "validate_mapping_state") as validate,
			mock_patch.object(patch, "validate_duplicate_variant_merges") as duplicates,
			mock_patch.object(patch, "collect_json_updates", return_value=[]) as collect,
		):
			items, variants, _, _, _ = patch.prepare_migration()
		self.assertEqual(items, {"Existing Yarn": "Target"})
		self.assertEqual(variants, {"Existing Yarn": "Target-Black"})
		validate.assert_called_once_with(items, variants)
		duplicates.assert_called_once_with(variants)
		collect.assert_called_once_with(variants)

	def test_greige_only_database_does_not_need_consolidation_sources(self):
		greige_item = "Yarn 36's GL"
		with (
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: isinstance(name, str) and (dt, name) in {
					("Item", greige_item), ("Item Attribute", "Colour")
				}
			)),
			mock_patch.object(patch, "validate_target_item") as validate_target,
			mock_patch.object(patch, "validate_attribute_only_variants"),
			mock_patch.object(patch, "validate_duplicate_variant_merges"),
			mock_patch.object(patch, "collect_json_updates", return_value=[]) as collect,
		):
			items, variants, greige, _, missing = patch.prepare_migration()
		self.assertEqual(items, {})
		self.assertEqual(variants, {})
		self.assertEqual(greige, {greige_item: f"{greige_item}-Greige"})
		self.assertEqual(len(missing), len(patch.ATTRIBUTE_ONLY_ITEMS) - 1)
		validate_target.assert_called_once_with(greige_item)
		collect.assert_called_once_with(greige)

	def test_subset_validation_ignores_absent_groups_and_colours(self):
		target, source = "Target", "Existing Yarn"
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {
				target: ((source, "Black"), ("Missing Yarn", "White")),
				"Missing Target": (("Missing Source", "Navy"),),
			}),
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: dt in ("Item", "Item Attribute")
				and name in (target, source, "Colour")
			)),
			mock_patch.object(patch.frappe.db, "get_value", return_value=None) as get_value,
			mock_patch.object(patch.frappe, "get_all", return_value=[]),
			mock_patch.object(patch, "validate_target_item") as validate_target,
		):
			patch.validate_mapping_state({source: target}, {source: "Target-Black"})
		validate_target.assert_called_once_with(target)
		get_value.assert_called_once_with("Item Attribute Value", "Black", "attribute_name")

	def test_existing_source_still_requires_colour_master(self):
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {"Target": (("Existing Yarn", "Black"),)}),
			mock_patch.object(patch, "ATTRIBUTE_ONLY_ITEMS", ()),
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: dt == "Item" and name == "Existing Yarn"
			)),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Item Attribute Colour"):
				patch.prepare_migration()

	def test_existing_target_variant_is_validated_before_migration(self):
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {"Target": (("Old Yarn", "Black"),)}),
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: (dt, name) in {
					("Item", "Target"), ("Item Attribute", "Colour"),
					("Item Variant", "Target-Black"),
				}
			)),
			mock_patch.object(patch.frappe.db, "get_value", return_value=None),
			mock_patch.object(patch, "validate_target_item"),
			mock_patch.object(patch, "validate_target_variant") as validate_variant,
		):
			patch.validate_mapping_state({"Old Yarn": "Target"}, {"Old Yarn": "Target-Black"})
		validate_variant.assert_called_once_with("Target-Black", "Target", "Black")

	def test_existing_source_with_unexpected_variants_still_fails(self):
		with (
			mock_patch.object(patch, "YARN_ITEM_GROUPS", {"Target": (("Old Yarn", "Black"),)}),
			mock_patch.object(patch.frappe.db, "exists", side_effect=(
				lambda dt, name: dt in ("Item", "Item Attribute")
				and name in ("Old Yarn", "Target", "Colour")
			)),
			mock_patch.object(patch.frappe.db, "get_value", return_value=None),
			mock_patch.object(patch.frappe, "get_all", return_value=["Unexpected Variant"]),
			mock_patch.object(patch, "validate_target_item"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "unexpected variants"):
				patch.validate_mapping_state({"Old Yarn": "Target"}, {"Old Yarn": "Target-Black"})

	def test_duplicate_sources_with_stock_history_still_fail(self):
		def exists(doctype, value):
			if doctype == "Item Variant":
				return value in ("Source A", "Source B")
			if doctype == "DocType":
				return value == "Bin"
			if doctype == "Bin":
				return value.get("item_code") in ("Source A", "Source B")
			return False

		with mock_patch.object(patch.frappe.db, "exists", side_effect=exists):
			with self.assertRaisesRegex(frappe.ValidationError, "more than one has Bin records"):
				patch.validate_duplicate_variant_merges({
					"Source A": "Target-Black", "Source B": "Target-Black"
				})

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
			mock_patch.object(stock_patch.frappe, "get_all", return_value=[
				frappe._dict(name=name, is_stock_item=1)
				for name in (*patch.YARN_ITEM_GROUPS, *patch.ATTRIBUTE_ONLY_ITEMS)
			]),
			mock_patch.object(stock_patch.frappe.db, "set_value") as set_value,
		):
			stock_patch.execute()
		set_value.assert_not_called()

	def test_stock_backfill_handles_no_matching_items(self):
		with (
			mock_patch.object(stock_patch.frappe, "get_all", return_value=[]) as get_all,
			mock_patch.object(stock_patch.frappe.db, "set_value") as set_value,
			mock_patch.object(stock_patch.frappe, "clear_document_cache") as clear_cache,
		):
			stock_patch.execute()
		get_all.assert_called_once()
		set_value.assert_not_called()
		clear_cache.assert_not_called()

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
