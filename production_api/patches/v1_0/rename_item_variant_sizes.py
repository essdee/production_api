import frappe
import json

ITEM_NAME = "Hamic - May Capri Set RNS(Cord)"
SIZE_MAPPING = {
	"45 cm": "40 cm",
	"50 cm": "45 cm",
	"55 cm": "50 cm",
	"60 cm": "55 cm",
	"65 cm": "60 cm",
	"70 cm": "65 cm",
	"75 cm": "70 cm",
	"80 cm": "75 cm",
}

def execute():
	if not frappe.db.exists("Item", ITEM_NAME):
		return
	# Step 1: Update Item Variant Attributes & Rename Variants
	variant_name_map = update_variant_attributes_and_rename()

	# Step 2: Update Item Attribute Mappings (Item + IPD)
	update_item_attribute_mappings()

	# Step 3: Update Cutting Marker Ratio size Link field
	update_cutting_marker_ratios()

	# Step 4: Update Cutting Laysheet Bundle size Link field
	update_cutting_laysheet_bundles()

	# Step 5: Update JSON fields in Work Order, Cutting Plan, IPD
	update_json_fields()

	# Step 6: Commit
	frappe.db.commit()


def update_variant_attributes_and_rename():
	"""Update Item Variant Attribute rows and rename variants. Process in ascending order."""
	variant_name_map = {}

	variants = frappe.get_all("Item Variant", filters={"item": ITEM_NAME}, pluck="name")
	if not variants:
		return variant_name_map

	# Process each old→new size pair in ascending order of old size
	for old_size, new_size in SIZE_MAPPING.items():
		# Find Item Variant Attribute rows for this item's variants with the old size
		attrs = frappe.get_all(
			"Item Variant Attribute",
			filters={
				"parent": ["in", variants],
				"attribute_value": old_size,
			},
			fields=["name", "parent", "display_name"],
		)

		affected_variant_names = set()
		for attr in attrs:
			update_fields = {"attribute_value": new_size}
			if attr.display_name == old_size:
				update_fields["display_name"] = new_size
			frappe.db.set_value("Item Variant Attribute", attr.name, update_fields, update_modified=False)
			affected_variant_names.add(attr.parent)

		# Rebuild item_tuple_attribute and rename each affected variant
		for vname in affected_variant_names:
			doc = frappe.get_doc("Item Variant", vname)
			# Rebuild item_tuple_attribute
			d = {}
			for attribute in doc.attributes:
				d[attribute.attribute] = attribute.attribute_value
			tup = tuple(sorted(d.items()))
			if tup:
				frappe.db.set_value("Item Variant", vname, "item_tuple_attribute", str(tup), update_modified=False)

			# Reload to pick up updated attribute values
			doc.reload()
			old_name = doc.name
			doc.rename_variant()
			new_name = doc.name
			if old_name != new_name:
				variant_name_map[old_name] = new_name
				# Update our working list of variant names
				idx = variants.index(old_name)
				variants[idx] = new_name

	return variant_name_map


def update_item_attribute_mappings():
	"""Update size values in Item and IPD attribute mappings."""
	# 2a. Item's attribute mapping
	item_doc = frappe.get_doc("Item", ITEM_NAME)
	for attr_row in item_doc.attributes:
		if attr_row.mapping:
			_update_mapping_values(attr_row.mapping)

	# 2b. Item's dependent attribute mapping
	if item_doc.dependent_attribute_mapping:
		_update_dependent_mapping(item_doc.dependent_attribute_mapping)

	# 2c. IPD attribute mappings
	ipds = frappe.get_all("Item Production Detail", filters={"item": ITEM_NAME}, pluck="name")
	for ipd_name in ipds:
		ipd_doc = frappe.get_doc("Item Production Detail", ipd_name)
		for attr_row in ipd_doc.item_attributes:
			if attr_row.mapping:
				_update_mapping_values(attr_row.mapping)
		if ipd_doc.dependent_attribute_mapping:
			_update_dependent_mapping(ipd_doc.dependent_attribute_mapping)


def _update_mapping_values(mapping_name):
	"""Update Item Item Attribute Mapping Value rows."""
	values = frappe.get_all(
		"Item Item Attribute Mapping Value",
		filters={"parent": mapping_name, "attribute_value": ["in", list(SIZE_MAPPING.keys())]},
		fields=["name", "attribute_value"],
	)
	for v in values:
		new_val = SIZE_MAPPING.get(v.attribute_value)
		if new_val:
			frappe.db.set_value("Item Item Attribute Mapping Value", v.name, "attribute_value", new_val, update_modified=False)


def _update_dependent_mapping(mapping_name):
	"""Update Item Dependent Attribute Mapping detail and value rows."""
	# Detail rows (attribute_value)
	details = frappe.get_all(
		"Item Dependent Attribute Mapping Detail",
		filters={"parent": mapping_name, "attribute_value": ["in", list(SIZE_MAPPING.keys())]},
		fields=["name", "attribute_value"],
	)
	for d in details:
		new_val = SIZE_MAPPING.get(d.attribute_value)
		if new_val:
			frappe.db.set_value("Item Dependent Attribute Mapping Detail", d.name, "attribute_value", new_val, update_modified=False)

	# Value rows (dependent_attribute_value)
	values = frappe.get_all(
		"Item Dependent Attribute Mapping Value",
		filters={"parent": mapping_name, "dependent_attribute_value": ["in", list(SIZE_MAPPING.keys())]},
		fields=["name", "dependent_attribute_value"],
	)
	for v in values:
		new_val = SIZE_MAPPING.get(v.dependent_attribute_value)
		if new_val:
			frappe.db.set_value("Item Dependent Attribute Mapping Value", v.name, "dependent_attribute_value", new_val, update_modified=False)


def update_cutting_marker_ratios():
	"""Update size Link field in Cutting Marker Ratio for this item's cutting markers."""
	markers = frappe.get_all("Cutting Marker", filters={"item": ITEM_NAME}, pluck="name")
	if not markers:
		return

	for old_size, new_size in SIZE_MAPPING.items():
		frappe.db.sql("""
			UPDATE `tabCutting Marker Ratio`
			SET `size` = %s
			WHERE `parent` IN %s AND `size` = %s
		""", (new_size, markers, old_size))


def update_cutting_laysheet_bundles():
	"""Update size Link field in Cutting LaySheet Bundle and Cutting Marker Ratio for laysheets."""
	laysheets = frappe.get_all("Cutting LaySheet", filters={"item": ITEM_NAME}, pluck="name")
	if not laysheets:
		return

	for old_size, new_size in SIZE_MAPPING.items():
		# Bundle rows
		frappe.db.sql("""
			UPDATE `tabCutting LaySheet Bundle`
			SET `size` = %s
			WHERE `parent` IN %s AND `size` = %s
		""", (new_size, laysheets, old_size))

		# Marker ratio rows within laysheets
		frappe.db.sql("""
			UPDATE `tabCutting Marker Ratio`
			SET `size` = %s
			WHERE `parent` IN %s AND `size` = %s
		""", (new_size, laysheets, old_size))


def update_json_fields():
	"""Update JSON fields in Work Order, Cutting Plan, and IPD."""
	# 5a. Work Order
	wo_json_fields = [
		"completed_items_json", "incompleted_items_json",
		"wo_delivered_completed_json", "wo_delivered_incompleted_json",
		"received_types_json",
	]
	_update_doctype_json("Work Order", wo_json_fields)

	# 5b. Cutting Plan
	cp_json_fields = ["completed_items_json", "incomplete_items_json"]
	_update_doctype_json("Cutting Plan", cp_json_fields)

	# 5c. Item Production Detail
	ipd_json_fields = [
		"cutting_items_json", "cutting_cloths_json",
		"stiching_accessory_json", "cloth_accessory_json",
		"accessory_clothtype_json", "emblishment_details_json",
		"variants_json",
	]
	_update_doctype_json("Item Production Detail", ipd_json_fields)


def _update_doctype_json(doctype, json_fields):
	"""For each doc of `doctype` with item=ITEM_NAME, update the specified JSON fields."""
	docs = frappe.get_all(doctype, filters={"item": ITEM_NAME}, pluck="name")
	if not docs:
		return

	for doc_name in docs:
		updates = {}
		for field in json_fields:
			raw = frappe.db.get_value(doctype, doc_name, field)
			if not raw:
				continue
			try:
				data = json.loads(raw) if isinstance(raw, str) else raw
			except (json.JSONDecodeError, TypeError):
				continue

			new_data = replace_sizes_in_json(data)
			new_raw = json.dumps(new_data, separators=(',', ':'))
			if new_raw != raw:
				updates[field] = new_raw

		if updates:
			frappe.db.set_value(doctype, doc_name, updates, update_modified=False)


def replace_sizes_in_json(data):
	"""Recursively replace old size strings with new sizes in JSON data.

	Dict keys and string values matching SIZE_MAPPING are replaced.
	Replacement is done all-at-once per dict to avoid chain-replace issues.
	"""
	if isinstance(data, dict):
		new_dict = {}
		for key, value in data.items():
			new_key = SIZE_MAPPING.get(key, key)
			new_dict[new_key] = replace_sizes_in_json(value)
		return new_dict
	elif isinstance(data, list):
		return [replace_sizes_in_json(item) for item in data]
	elif isinstance(data, str):
		return SIZE_MAPPING.get(data, data)
	else:
		return data
