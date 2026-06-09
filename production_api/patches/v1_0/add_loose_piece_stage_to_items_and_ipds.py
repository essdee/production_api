import frappe


STAGE_ATTRIBUTE = "Stage"
DEPENDING_ATTRIBUTE = "Size"
LOOSE_PIECE_VALUE = "Loose Piece"
LOOSE_PIECE_UOM = "Pieces"


def execute():
	"""Add the Loose Piece stage to Items, their IPDs, and their IDAM documents."""
	validate_prerequisites()
	ensure_loose_piece_attribute_value()

	sources_changed = []
	sources_ready_for_idam_update = []
	dependent_attribute_mappings_to_update = []

	for item_name in get_items_with_stage_dependency():
		item_doc = frappe.get_doc("Item", item_name)

		item_stage_status = ensure_loose_piece_in_stage_attribute_mapping(
			source_doc=item_doc,
			attribute_table_field="attributes",
		)
		track_source(
			source_doc=item_doc,
			stage_status=item_stage_status,
			sources_changed=sources_changed,
			sources_ready=sources_ready_for_idam_update,
			dependent_attribute_mappings=dependent_attribute_mappings_to_update,
		)

		for ipd_name in get_item_production_details(item_doc.name):
			ipd_doc = frappe.get_doc("Item Production Detail", ipd_name)
			if ipd_doc.dependent_attribute != STAGE_ATTRIBUTE:
				continue

			ipd_stage_status = ensure_loose_piece_in_stage_attribute_mapping(
				source_doc=ipd_doc,
				attribute_table_field="item_attributes",
			)
			track_source(
				source_doc=ipd_doc,
				stage_status=ipd_stage_status,
				sources_changed=sources_changed,
				sources_ready=sources_ready_for_idam_update,
				dependent_attribute_mappings=dependent_attribute_mappings_to_update,
			)

	for mapping_name in unique(dependent_attribute_mappings_to_update):
		add_loose_piece_to_dependent_attribute_mapping(mapping_name)

	frappe.logger("production_api.patches").info(
		"Loose Piece stage patch added the Stage value to %s sources and checked %s IDAM sources.",
		len(sources_changed),
		len(sources_ready_for_idam_update),
	)


def validate_prerequisites():
	"""Fail early with a clear message if the master data is not available."""
	for doctype, name in (
		("Item Attribute", STAGE_ATTRIBUTE),
		("Item Attribute", DEPENDING_ATTRIBUTE),
		("UOM", LOOSE_PIECE_UOM),
	):
		if not frappe.db.exists(doctype, name):
			frappe.throw(f"{doctype} {name} is required before running this patch.")


def ensure_loose_piece_attribute_value():
	"""Ensure the Link value exists before child rows point to it."""
	if frappe.db.exists("Item Attribute Value", LOOSE_PIECE_VALUE):
		return

	attribute_value = frappe.new_doc("Item Attribute Value")
	attribute_value.attribute_name = STAGE_ATTRIBUTE
	attribute_value.attribute_value = LOOSE_PIECE_VALUE
	attribute_value.save(ignore_permissions=True)


def get_items_with_stage_dependency():
	return frappe.get_all(
		"Item",
		filters={"dependent_attribute": STAGE_ATTRIBUTE},
		pluck="name",
	)


def get_item_production_details(item_name):
	return frappe.get_all(
		"Item Production Detail",
		filters={
			"item": item_name,
			"dependent_attribute": STAGE_ATTRIBUTE,
		},
		pluck="name",
	)


def ensure_loose_piece_in_stage_attribute_mapping(source_doc, attribute_table_field):
	"""Add Loose Piece to the Stage attribute mapping of an Item or IPD."""
	stage_mapping_name = get_stage_attribute_mapping_name(source_doc, attribute_table_field)
	if not stage_mapping_name:
		return {"changed": False, "has_loose_piece": False}

	stage_mapping = frappe.get_doc("Item Item Attribute Mapping", stage_mapping_name)
	if has_stage_value(stage_mapping):
		return {"changed": False, "has_loose_piece": True}

	stage_mapping.append("values", {"attribute_value": LOOSE_PIECE_VALUE})
	stage_mapping.save(ignore_permissions=True)
	return {"changed": True, "has_loose_piece": True}


def get_stage_attribute_mapping_name(source_doc, attribute_table_field):
	for attribute_row in source_doc.get(attribute_table_field):
		if attribute_row.attribute == STAGE_ATTRIBUTE:
			return attribute_row.mapping
	return None


def has_stage_value(stage_mapping):
	for value_row in stage_mapping.values:
		if value_row.attribute_value == LOOSE_PIECE_VALUE:
			return True
	return False


def track_source(
	source_doc,
	stage_status,
	sources_changed,
	sources_ready,
	dependent_attribute_mappings,
):
	"""Keep the human-readable source list and the IDAM work list together."""
	source_detail = {
		"doctype": source_doc.doctype,
		"name": source_doc.name,
		"dependent_attribute_mapping": source_doc.dependent_attribute_mapping,
	}

	if stage_status["changed"]:
		sources_changed.append(source_detail)

	if stage_status["has_loose_piece"] and source_doc.dependent_attribute_mapping:
		sources_ready.append(source_detail)
		dependent_attribute_mappings.append(source_doc.dependent_attribute_mapping)


def add_loose_piece_to_dependent_attribute_mapping(mapping_name):
	"""Add Loose Piece rows to the IDAM mapping and details tables."""
	dependent_mapping = frappe.get_doc("Item Dependent Attribute Mapping", mapping_name)
	if dependent_mapping.dependent_attribute != STAGE_ATTRIBUTE:
		return

	changed = False

	if not has_depending_attribute_row(dependent_mapping):
		dependent_mapping.append(
			"mapping",
			{
				"dependent_attribute_value": LOOSE_PIECE_VALUE,
				"depending_attribute": DEPENDING_ATTRIBUTE,
			},
		)
		changed = True

	if not has_dependent_attribute_detail_row(dependent_mapping):
		dependent_mapping.append(
			"details",
			{
				"attribute_value": LOOSE_PIECE_VALUE,
				"uom": LOOSE_PIECE_UOM,
				"display_name": LOOSE_PIECE_VALUE,
			},
		)
		changed = True

	if changed:
		dependent_mapping.save(ignore_permissions=True)


def has_depending_attribute_row(dependent_mapping):
	for row in dependent_mapping.mapping:
		if (
			row.dependent_attribute_value == LOOSE_PIECE_VALUE
			and row.depending_attribute == DEPENDING_ATTRIBUTE
		):
			return True
	return False


def has_dependent_attribute_detail_row(dependent_mapping):
	for row in dependent_mapping.details:
		if row.attribute_value == LOOSE_PIECE_VALUE:
			return True
	return False


def unique(values):
	seen = set()
	unique_values = []
	for value in values:
		if value in seen:
			continue
		seen.add(value)
		unique_values.append(value)
	return unique_values
