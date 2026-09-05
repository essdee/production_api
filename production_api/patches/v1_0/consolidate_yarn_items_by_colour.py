"""Consolidate legacy yarn Items into colour-based Item Variants.

The mapping was transcribed from ``Item (2).xlsx``. Spreadsheet rows having
both a target Item and a Colour value are consolidation rows. Rows having a
target Item and ``Attribute = Colour`` but no Colour value keep their existing
Item and convert their default Item Variant to the Greige colour variant.

It updates normal and custom Link fields through Frappe's rename/merge
machinery, converts each legacy default Item Variant in place, and then removes
the obsolete parent Item by merging it into the new parent.
All converted yarn Items are marked as stock items, including the Items
retained under their existing names with a Greige variant.
Only mapping rows with an existing source Item or converted target variant
are processed; databases can contain any subset of the original yarn list.
"""

import json
from collections import defaultdict

import frappe
from frappe.model.rename_doc import rename_doc

from production_api.production_api.doctype.item.item import create_variant


COLOUR_ATTRIBUTE = "Colour"
DEFAULT_ATTRIBUTE_ONLY_COLOUR = "Greige"

# Target Item: ((legacy Item, Colour), ...)
#
# Spreadsheet typography is normalized in the target names:
# - straight apostrophes are used instead of curly apostrophes;
# - ``Yarn 25 's`` is consolidated into the correct ``Yarn 25's`` Item.
YARN_ITEM_GROUPS = {
	"Yarn 28's OE": (
		("Yarn 28's OE Black Solid BLK-621", "Black Solid BLK-621"),
		("Yarn 28's OE A Mel MLG926", "A Mel MLG926"),
		("Yarn 28's OE A Mel MLG273", "A Mel MLG273"),
		("Yarn 28's OE Black Solid BLK-232", "Black Solid BLK-232"),
		("Yarn 28's OE Grey Melange", "Grey Melange"),
	),
	"Yarn 25's OE": (
		("Yarn 25 's OE Royal Blue", "Royal Blue"),
		("Yarn 25 's OE Lemon Yellow", "Lemon Yellow"),
		("Yarn 25 's OE Water Green", "Water Green"),
		("Yarn 25 's OE Water Blue", "Water Blue"),
		("Yarn 25 's OE Maroon", "Maroon"),
		("Yarn 25 's OE Tomato Red", "TOMATO RED"),
		("Yarn 25's OE Coffee Brown", "Coffee Brown"),
		("Yarn 25's OE Charcoal Mel", "Charcoal Mel"),
		("Yarn 25's OE Black", "Black"),
		("Yarn 25's OE A Mel", "A Mel"),
		("Yarn 25's OE Maroon Mel", "Maroon Mel"),
		("Yarn 25's OE G Mel", "G Mel"),
		("Yarn 25's OE AF Navy", "AF Navy"),
		("Yarn 25's OE Peacock Blue", "Peacock Blue"),
		("Yarn 25's OE Navy", "Navy"),
		("Yarn 25's OE Olive Green", "Olive Green"),
		("Yarn 25's OE Maroon", "Maroon"),
		("Yarn 25's OE White", "White"),
	),
	"Yarn 30's OE": (
		("Yarn 30's OE Coffee Brown BR-412", "Coffee Brown BR-412"),
		("Yarn 30's OE Grey Mélange MLG-243", "Grey Mélange MLG-243"),
		("Yarn 30's OE Dark Maroon RD-122", "Dark Maroon RD-122"),
		("Yarn 30's OE Navy Blue NB-222", "Navy Blue NB-222"),
		("Yarn 30's OE Black Solid BLK-232", "Black Solid BLK-232"),
		("Yarn 30's OE Mustard", "Mustard"),
		("Yarn 30's OE Peacock Blue", "Peacock Blue"),
		("Yarn 30's OE Bottle Green", "Bottle Green"),
		("Yarn 30's OE Coffee Brown", "Coffee Brown"),
		("Yarn 30's OE Peacock Green", "Peacock Green"),
		("Yarn 30's OE Olive Green", "Olive Green"),
		("Yarn 30's OE Silver Grey", "Silver Grey"),
		("Yarn 30's OE White", "White"),
		("Yarn 30's OE AF Navy", "AF Navy"),
		("Yarn 30's OE Red", "Red"),
		("Yarn 30's OE G Mel", "G Mel"),
		("Yarn 30's OE A Mel", "A Mel"),
		("Yarn 30's OE Steel Grey - SG451", "Steel Grey - SG451"),
		("Yarn 30's OE Burgundy - RD123", "Burgundy - RD123"),
		("Yarn 30's OE Tomato Red - RD263", "Tomato Red - RD263"),
		("Yarn 30's OE AF.Navy - BL322", "AF.Navy - BL322"),
		("Yarn 30's OE Navy", "Navy"),
		("Yarn 30's OE Maroon", "Maroon"),
		("Yarn 30's OE Dark Brown", "Dark Brown"),
		("Yarn 30'S OE R/Brown", "R/Brown"),
		("Yarn 30's OE Water Blue WB410", "Water Blue WB410"),
		("Yarn 30's OE lemon yellow LY302", "lemon yellow LY302"),
		("Yarn 30'S OE D/MERUN", "D/MERUN"),
		("Yarn 30's OE Black", "Black"),
		("Yarn 30's OE Burgundy", "Burgundy"),
		("Yarn 30's OE Red/Maroon", "Red/Maroon"),
		("Yarn 30's OE Bottle Green - GR331", "Bottle Green - GR331"),
	),
	"Yarn 24's OE": (
		("Yarn 24's OE Black", "Black"),
		("Yarn 24's OE Navy", "Navy"),
	),
	"Yarn 26's OE": (
		("Yarn 26's OE White", "White"),
	),
	"Yarn 32's OE": (
		("Yarn 32's OE A Mel MLG273", "A Mel MLG273"),
		("Yarn 32's OE Black", "Black"),
	),
	"Yarn 34's OE": (
		("Yarn 34's OE A Mel MLG273", "A Mel MLG273"),
		("Yarn 34's OE Black", "Black"),
	),
	"Yarn 36's OE": (
		("Yarn 36's OE Black", "Black"),
		("Yarn 36's OE Coffee Brown", "Coffee Brown"),
		("Yarn 36's OE White", "White"),
	),
	"Yarn 40's OE": (
		("Yarn 40's OE White", "White"),
	),
	"Yarn 25's": (
		("Yarn 25's G Mel", "G Mel"),
		("Yarn 25's Light GMel", "Light GMel"),
		("Yarn 25's Navy Light - NL401", "Navy Light - NL401"),
		("Yarn 25's PG708 Peacock Green", "PG708 Peacock Green"),
		("Yarn 25 's AF Navy", "AF Navy"),
	),
	"Yarn 30's": (
		("Yarn 30's A Mel", "A Mel"),
		("Yarn 30's A Mel MLG273", "A Mel MLG273"),
		("Yarn 30's BLACK BLK232", "BLACK BLK232"),
		("Yarn 30's Charcoal Melange MLG274", "Charcoal Melange MLG274"),
		("Yarn 30's D/Merun RD122", "D/Merun RD122"),
		("Yarn 30's G Mel", "G Mel"),
		("Yarn 30's G.MEL MLG243", "G.MEL MLG243"),
		("Yarn 30's Light GMel", "Light GMel"),
		("Yarn 30's Navy", "Navy"),
		("Yarn 30's Navy NB222", "Navy NB222"),
	),
	"Yarn 34's": (
		("Yarn 34's A Mel", "A Mel"),
		("Yarn 34's Black", "Black"),
		("Yarn 34's G Mel", "G Mel"),
		("Yarn 34's G Mel(88/12)(C/P)", "G Mel(88/12)(C/P)"),
		("Yarn 34's GMel", "GMel"),
		("Yarn 34's Light GMel", "Light GMel"),
	),
	"Cotton Yarn 40's": (
		("Cotton Yarn 40's Red", "Red"),
	),
	"Yarn 20's": (
		("Yarn 20's G Mel MLG 5921", "G Mel MLG 5921"),
	),
}

# Existing Items which stay under their current names. The spreadsheet asks
# for the Colour attribute but does not provide a value, so their existing
# default Item Variants are converted to Greige variants.
ATTRIBUTE_ONLY_ITEMS = (
	"Yarn 32's OE Cotton",
	"Yarn 34's OE Cotton",
	"Yarn 25's RL",
	"Yarn 25's VL",
	"Yarn 25's GL",
	"Compact Yarn 25's RL",
	"Yarn 30's VL Compact",
	"Yarn 30's CCH 100% Cotton",
	"Yarn 30's GL",
	"Yarn 30's PV 60/40 MVS wine Dyed",
	"Yarn 30's RL",
	"Yarn 30's RL Compact",
	"Yarn 30's SCHY",
	"Yarn 30's VL",
	"Yarn 34's  SCH Cotton",
	"Yarn 34's VL",
	"Yarn 34's GL",
	"Yarn 34's RL Compact",
	"Yarn 36's GL",
	"Yarn 36's RL",
	"Yarn 36's VL",
	"36's LYO Cheese Yarn",
	"Compact Yarn 36's RL",
	"Cotton Yarn 60'S",
	"Polyester Grey Yarn",
	"Yarn 100D Poly Yarn",
	"Yarn 24's CCH 100% Cotton",
	"Yarn 24's RL Compact",
	"Yarn 40's Bamboo Siro Compact",
	"Yarn 40's Birla Viscose Vortex",
	"Yarn 40's GL",
	"Yarn 40's VL",
	"Yarn 53'S PC",
	"Yarn 57'S PC",
	"Yarn 60's RL",
)

# These fields store Item Variant names as JSON keys or values rather than as
# Link fields, so Frappe's rename_doc cannot update them automatically.
VARIANT_JSON_FIELDS = {
	"Work Order": (
		"completed_items_json",
		"incompleted_items_json",
		"wo_delivered_completed_json",
		"wo_delivered_incompleted_json",
		"received_types_json",
	),
	"Cutting Plan": (
		"completed_items_json",
		"incomplete_items_json",
	),
	"Item Production Detail": (
		"cutting_items_json",
		"cutting_cloths_json",
		"stiching_accessory_json",
		"cloth_accessory_json",
		"accessory_clothtype_json",
		"emblishment_details_json",
		"variants_json",
	),
}

# Two legacy Items map to the same Maroon variant. If both have stock history
# or another unique one-to-one record, an automatic merge would be unsafe.
UNIQUE_OR_STOCK_VARIANT_LINKS = {
	"Bin": "item_code",
	"Stock Ledger Entry": "item",
	"Sales Item Price": "item_variant",
}


class JsonKeyCollisionError(ValueError):
	pass


def execute():
	(
		item_name_map,
		_variant_name_map,
		attribute_only_variant_map,
		json_updates,
		missing_attribute_items,
	) = prepare_migration()
	if not item_name_map and not attribute_only_variant_map:
		print("No mapped yarn Items or variants found; nothing to consolidate.")
		return
	skipped_count = sum(len(rows) for rows in YARN_ITEM_GROUPS.values()) - len(item_name_map)
	if skipped_count:
		print(f"Skipping {skipped_count} absent legacy yarn mapping(s).")

	for item_name in ATTRIBUTE_ONLY_ITEMS:
		if item_name not in attribute_only_variant_map:
			continue
		ensure_item_colour_attribute(item_name)
		ensure_target_colours(item_name, [DEFAULT_ATTRIBUTE_ONLY_COLOUR])
		convert_or_merge_variant(
			item_name,
			item_name,
			DEFAULT_ATTRIBUTE_ONLY_COLOUR,
		)
	if missing_attribute_items:
		frappe.logger("yarn_item_consolidation").warning(
			"Could not add Colour to missing Items: %s",
			", ".join(missing_attribute_items),
		)

	for target_item, source_rows in YARN_ITEM_GROUPS.items():
		source_rows = tuple(
			(source, colour) for source, colour in source_rows
			if source in item_name_map
		)
		if not source_rows:
			continue
		ensure_target_item(target_item, source_rows)
		ensure_target_colours(target_item, [colour for _source, colour in source_rows])

		for source_item, colour in source_rows:
			convert_or_merge_variant(source_item, target_item, colour)

		for source_item, _colour in source_rows:
			merge_source_item(source_item, target_item)

	apply_json_updates(json_updates)
	frappe.clear_cache(doctype="Item")
	frappe.clear_cache(doctype="Item Variant")


def prepare_migration():
	item_name_map, variant_name_map = build_name_maps()
	item_name_map, variant_name_map = select_existing_name_maps(
		item_name_map, variant_name_map
	)
	missing_attribute_items = validate_attribute_only_items()
	attribute_only_variant_map = build_attribute_only_variant_map(
		missing_attribute_items
	)
	if not item_name_map and not attribute_only_variant_map:
		return ({}, {}, {}, [], missing_attribute_items)
	validate_mapping_state(item_name_map, variant_name_map)
	validate_attribute_only_variants(attribute_only_variant_map)
	all_variant_name_map = {**variant_name_map, **attribute_only_variant_map}
	validate_duplicate_variant_merges(all_variant_name_map)
	json_updates = collect_json_updates(all_variant_name_map)
	return (
		item_name_map,
		variant_name_map,
		attribute_only_variant_map,
		json_updates,
		missing_attribute_items,
	)


def preflight():
	"""Run every read-only validation without applying the migration."""
	(
		item_name_map,
		variant_name_map,
		attribute_only_variant_map,
		json_updates,
		missing_attribute_items,
	) = prepare_migration()
	all_item_names, _ = build_name_maps()
	return {
		"target_item_count": len(set(item_name_map.values())),
		"source_item_count": len(item_name_map),
		"target_variant_count": len(set(variant_name_map.values())),
		"skipped_source_items": [name for name in all_item_names if name not in item_name_map],
		"attribute_only_item_count": len(ATTRIBUTE_ONLY_ITEMS),
		"attribute_only_target_variant_count": len(attribute_only_variant_map),
		"missing_attribute_only_items": missing_attribute_items,
		"json_update_count": len(json_updates),
	}


def build_name_maps():
	item_name_map = {}
	variant_name_map = {}
	for target_item, source_rows in YARN_ITEM_GROUPS.items():
		for source_item, colour in source_rows:
			item_name_map[source_item] = target_item
			variant_name_map[source_item] = get_target_variant_name(target_item, colour)
	if len(item_name_map) != sum(len(rows) for rows in YARN_ITEM_GROUPS.values()):
		frappe.throw("The yarn mapping contains a duplicate legacy Item name")
	return item_name_map, variant_name_map


def select_existing_name_maps(item_name_map, variant_name_map):
	"""Do not create yarns or rewrite JSON links for absent mapping rows.

	An existing converted variant keeps the row active on reruns. A legacy
	variant without its parent Item is inconsistent data, not an absent yarn.
	"""
	existing_items = {}
	existing_variants = {}
	for source_item, target_item in item_name_map.items():
		source_exists = frappe.db.exists("Item", source_item)
		if not source_exists and frappe.db.exists("Item Variant", source_item):
			frappe.throw(f"Legacy Item Variant {source_item} exists without its parent Item")
		target_variant = variant_name_map[source_item]
		if source_exists or frappe.db.exists("Item Variant", target_variant):
			existing_items[source_item] = target_item
			existing_variants[source_item] = target_variant
	return existing_items, existing_variants


def get_target_variant_name(target_item, colour):
	return f"{target_item}-{colour}"


def build_attribute_only_variant_map(missing_items=()):
	missing_items = set(missing_items)
	return {
		item_name: get_target_variant_name(
			item_name,
			DEFAULT_ATTRIBUTE_ONLY_COLOUR,
		)
		for item_name in ATTRIBUTE_ONLY_ITEMS
		if item_name not in missing_items
	}


def validate_mapping_state(item_name_map, variant_name_map):
	if not frappe.db.exists("Item Attribute", COLOUR_ATTRIBUTE):
		frappe.throw(f"Item Attribute {COLOUR_ATTRIBUTE} does not exist")

	if len(variant_name_map) != len(item_name_map):
		frappe.throw("The Item and Item Variant mappings are inconsistent")

	for target_item, source_rows in YARN_ITEM_GROUPS.items():
		source_rows = tuple(
			(source, colour) for source, colour in source_rows
			if source in item_name_map
		)
		if not source_rows:
			continue
		validate_target_item(target_item)
		if not frappe.db.exists("Item", target_item):
			source_item = next(
				(
					name
					for name, _colour in source_rows
					if frappe.db.exists("Item", name)
				),
				None,
			)
			if source_item:
				source_doc = frappe.get_doc("Item", source_item)
				generated_name = source_doc.get_name(source_doc.brand, target_item)
				if generated_name != target_item:
					frappe.throw(
						f"Source Item {source_item} would create target Item "
						f"{generated_name}, expected {target_item}"
					)
		for source_item, colour in source_rows:
			existing_attribute = frappe.db.get_value(
				"Item Attribute Value",
				colour,
				"attribute_name",
			)
			if existing_attribute and existing_attribute != COLOUR_ATTRIBUTE:
				frappe.throw(
					f"Item Attribute Value {colour} belongs to "
					f"{existing_attribute}, not {COLOUR_ATTRIBUTE}"
				)

			target_variant = get_target_variant_name(target_item, colour)
			source_exists = frappe.db.exists("Item", source_item)
			target_exists = frappe.db.exists("Item", target_item)
			target_variant_exists = frappe.db.exists("Item Variant", target_variant)
			if target_variant_exists:
				validate_target_variant(target_variant, target_item, colour)

			if not source_exists:
				if not (target_exists and target_variant_exists):
					frappe.throw(
						f"Legacy Item {source_item} is missing and its target "
						f"variant {target_variant} does not exist"
					)
				continue

			source_variants = frappe.get_all(
				"Item Variant",
				filters={"item": source_item},
				pluck="name",
			)
			unexpected_variants = [name for name in source_variants if name != source_item]
			if unexpected_variants:
				frappe.throw(
					f"Legacy Item {source_item} has unexpected variants: "
					f"{', '.join(unexpected_variants)}"
				)

			if source_item in source_variants:
				if frappe.db.exists(
					"Item Variant Attribute",
					{"parent": source_item},
				):
					frappe.throw(
						f"Legacy Item Variant {source_item} already has attributes"
					)


def validate_target_item(target_item):
	if not frappe.db.exists("Item", target_item):
		return

	doc = frappe.get_doc("Item", target_item)
	attributes = [row.attribute for row in doc.attributes]
	if attributes.count(COLOUR_ATTRIBUTE) > 1:
		frappe.throw(f"Target Item {target_item} has duplicate Colour attributes")
	unexpected = [attribute for attribute in attributes if attribute != COLOUR_ATTRIBUTE]
	if unexpected:
		frappe.throw(
			f"Target Item {target_item} has unexpected attributes: "
			f"{', '.join(unexpected)}"
		)
	if doc.primary_attribute not in (None, "", COLOUR_ATTRIBUTE):
		frappe.throw(
			f"Target Item {target_item} has primary attribute "
			f"{doc.primary_attribute}; expected no primary attribute"
		)
	if doc.dependent_attribute:
		frappe.throw(f"Target Item {target_item} has a dependent attribute")


def validate_attribute_only_items():
	missing_items = []
	for item_name in ATTRIBUTE_ONLY_ITEMS:
		if not frappe.db.exists("Item", item_name):
			missing_items.append(item_name)
			continue
		validate_target_item(item_name)
	return missing_items


def validate_attribute_only_variants(attribute_only_variant_map):
	for item_name, target_variant in attribute_only_variant_map.items():
		variants = frappe.get_all(
			"Item Variant",
			filters={"item": item_name},
			pluck="name",
		)
		unexpected_variants = [
			name for name in variants if name not in (item_name, target_variant)
		]
		if unexpected_variants:
			frappe.throw(
				f"Item {item_name} has unexpected variants: "
				f"{', '.join(unexpected_variants)}"
			)

		if target_variant in variants:
			validate_target_variant(
				target_variant,
				item_name,
				DEFAULT_ATTRIBUTE_ONLY_COLOUR,
			)


def validate_duplicate_variant_merges(variant_name_map):
	sources_by_target = defaultdict(list)
	for source_variant, target_variant in variant_name_map.items():
		sources_by_target[target_variant].append(source_variant)

	for target_variant, source_variants in sources_by_target.items():
		candidates = [
			variant
			for variant in source_variants
			if frappe.db.exists("Item Variant", variant)
		]
		if (
			frappe.db.exists("Item Variant", target_variant)
			and target_variant not in candidates
		):
			candidates.append(target_variant)
		if len(candidates) < 2:
			continue

		for doctype, fieldname in UNIQUE_OR_STOCK_VARIANT_LINKS.items():
			if not frappe.db.exists("DocType", doctype):
				continue
			referenced = [
				variant
				for variant in candidates
				if frappe.db.exists(doctype, {fieldname: variant})
			]
			if len(referenced) > 1:
				frappe.throw(
					f"Cannot safely merge {', '.join(referenced)} into "
					f"{target_variant}: more than one has {doctype} records"
				)


def ensure_target_item(target_item, source_rows):
	if frappe.db.exists("Item", target_item):
		ensure_item_colour_attribute(target_item)
		return frappe.get_doc("Item", target_item)

	source_item = next(
		(
			name
			for name, _colour in source_rows
			if frappe.db.exists("Item", name)
		),
		None,
	)
	if not source_item:
		frappe.throw(f"No source Item is available to create {target_item}")

	doc = frappe.copy_doc(frappe.get_doc("Item", source_item))
	doc.name1 = target_item
	doc.is_stock_item = 1
	doc.item_hash_value = None
	doc.primary_attribute = None
	doc.dependent_attribute = None
	doc.dependent_attribute_mapping = None
	doc.set("attributes", [])
	doc.append("attributes", {"attribute": COLOUR_ATTRIBUTE})
	doc.insert(ignore_permissions=True)
	if doc.name != target_item:
		frappe.throw(
			f"Created target Item name {doc.name}, expected {target_item}"
		)
	return doc


def ensure_item_colour_attribute(item_name):
	"""Enable stock and Colour mapping without making Colour the primary attribute."""
	if not frappe.db.exists("Item", item_name):
		return False

	doc = frappe.get_doc("Item", item_name)
	attribute_row = next(
		(row for row in doc.attributes if row.attribute == COLOUR_ATTRIBUTE),
		None,
	)
	needs_save = False
	if not attribute_row:
		attribute_row = doc.append("attributes", {"attribute": COLOUR_ATTRIBUTE})
		needs_save = True
	elif attribute_row.mapping and not frappe.db.exists(
		"Item Item Attribute Mapping",
		attribute_row.mapping,
	):
		attribute_row.mapping = None
		needs_save = True
	elif not attribute_row.mapping:
		needs_save = True

	if doc.primary_attribute == COLOUR_ATTRIBUTE:
		doc.primary_attribute = None
		needs_save = True

	if not doc.is_stock_item:
		doc.is_stock_item = 1
		needs_save = True

	if needs_save:
		doc.save(ignore_permissions=True)
	frappe.clear_document_cache("Item", item_name)
	return True


def ensure_target_colours(target_item, colours):
	doc = frappe.get_doc("Item", target_item)
	attribute_row = next(
		(row for row in doc.attributes if row.attribute == COLOUR_ATTRIBUTE),
		None,
	)
	if not attribute_row or not attribute_row.mapping:
		frappe.throw(f"Target Item {target_item} has no Colour mapping")

	mapping = frappe.get_doc("Item Item Attribute Mapping", attribute_row.mapping)
	existing_values = {row.attribute_value for row in mapping.values}
	for colour in dict.fromkeys(colours):
		ensure_colour_value(colour)
		if colour not in existing_values:
			mapping.append("values", {"attribute_value": colour})
			existing_values.add(colour)
	mapping.save(ignore_permissions=True)
	frappe.clear_document_cache("Item", target_item)


def ensure_colour_value(colour):
	existing_attribute = frappe.db.get_value(
		"Item Attribute Value",
		colour,
		"attribute_name",
	)
	if existing_attribute:
		if existing_attribute != COLOUR_ATTRIBUTE:
			frappe.throw(
				f"Item Attribute Value {colour} belongs to "
				f"{existing_attribute}, not {COLOUR_ATTRIBUTE}"
			)
		return

	frappe.get_doc(
		{
			"doctype": "Item Attribute Value",
			"attribute_name": COLOUR_ATTRIBUTE,
			"attribute_value": colour,
		}
	).insert(ignore_permissions=True)


def convert_or_merge_variant(source_item, target_item, colour):
	target_variant = get_target_variant_name(target_item, colour)
	source_variant_exists = frappe.db.exists("Item Variant", source_item)
	target_variant_exists = frappe.db.exists("Item Variant", target_variant)

	if source_variant_exists and not target_variant_exists:
		doc = frappe.get_doc("Item Variant", source_item)
		doc.item = target_item
		doc.item_tuple_attribute = str(((COLOUR_ATTRIBUTE, colour),))
		doc.set(
			"attributes",
			[
				{
					"attribute": COLOUR_ATTRIBUTE,
					"attribute_value": colour,
					"display_name": colour,
				}
			],
		)
		doc.save(ignore_permissions=True)
		rename_doc(
			"Item Variant",
			source_item,
			target_variant,
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)
	elif source_variant_exists and target_variant_exists:
		rename_doc(
			"Item Variant",
			source_item,
			target_variant,
			force=True,
			merge=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)
	elif not target_variant_exists:
		variant = create_variant(target_item, {COLOUR_ATTRIBUTE: colour})
		variant.insert(ignore_permissions=True)
		if variant.name != target_variant:
			frappe.throw(
				f"Created Item Variant {variant.name}, expected {target_variant}"
			)

	validate_target_variant(target_variant, target_item, colour)


def validate_target_variant(target_variant, target_item, colour):
	doc = frappe.get_doc("Item Variant", target_variant)
	attribute_values = {
		row.attribute: row.attribute_value
		for row in doc.attributes
	}
	if (
		doc.item != target_item
		or len(doc.attributes) != 1
		or attribute_values != {COLOUR_ATTRIBUTE: colour}
	):
		frappe.throw(
			f"Item Variant {target_variant} does not match "
			f"{target_item} / {COLOUR_ATTRIBUTE}: {colour}"
		)


def merge_source_item(source_item, target_item):
	if source_item == target_item or not frappe.db.exists("Item", source_item):
		return
	if frappe.db.exists("Item Variant", {"item": source_item}):
		frappe.throw(
			f"Cannot remove Item {source_item}: Item Variants still reference it"
		)

	rename_doc(
		"Item",
		source_item,
		target_item,
		force=True,
		merge=True,
		ignore_permissions=True,
		show_alert=False,
		rebuild_search=False,
	)


def collect_json_updates(replacements):
	updates = []
	for doctype, fieldnames in VARIANT_JSON_FIELDS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		for fieldname in fieldnames:
			if not meta.has_field(fieldname):
				continue
			rows = frappe.get_all(
				doctype,
				filters=[[fieldname, "is", "set"]],
				fields=["name", fieldname],
				limit_page_length=0,
			)
			for row in rows:
				raw_value = row.get(fieldname)
				try:
					value = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
				except (json.JSONDecodeError, TypeError):
					continue
				updated_value, changed = replace_exact_json_values(value, replacements)
				if changed:
					updates.append(
						(
							doctype,
							row.name,
							fieldname,
							json.dumps(
								updated_value,
								ensure_ascii=False,
								separators=(",", ":"),
							),
						)
					)
	return updates


def replace_exact_json_values(value, replacements):
	if isinstance(value, dict):
		updated = {}
		changed = False
		for key, child_value in value.items():
			new_key = replacements.get(key, key) if isinstance(key, str) else key
			new_child, child_changed = replace_exact_json_values(
				child_value,
				replacements,
			)
			if new_key in updated:
				raise JsonKeyCollisionError(
					f"JSON keys {key!r} and another key both map to {new_key!r}"
				)
			updated[new_key] = new_child
			changed = changed or new_key != key or child_changed
		return updated, changed

	if isinstance(value, list):
		updated = []
		changed = False
		for child_value in value:
			new_child, child_changed = replace_exact_json_values(
				child_value,
				replacements,
			)
			updated.append(new_child)
			changed = changed or child_changed
		return updated, changed

	if isinstance(value, str) and value in replacements:
		return replacements[value], True

	return value, False


def apply_json_updates(updates):
	for doctype, docname, fieldname, value in updates:
		frappe.db.set_value(
			doctype,
			docname,
			fieldname,
			value,
			update_modified=False,
		)
