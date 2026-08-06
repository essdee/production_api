# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt
"""Matrix entry aid for panel-wise Cutting Cloth mappings.

The compact matrix may contain blanks while an IPD is being prepared.
``cutting_cloths_json`` remains the canonical contract used by Lot and BOM flows.
"""

from itertools import product

import frappe
from frappe import _

from production_api.panel_wise_consumption import (
	_as_json,
	_group_id,
	_group_label,
	_group_packing_values,
	_panel_values,
	_unique,
	get_matrix_context,
	make_panel_wise_matrix,
)


SCHEMA_VERSION = 1
SINGLE_VALUE_KEY = "__single__"


def _mapping_values(doc, attribute):
	for row in doc.get("item_attributes") or []:
		if row.get("attribute") == attribute and row.get("mapping"):
			mapping = frappe.get_cached_doc(
				"Item Item Attribute Mapping", row.get("mapping")
			)
			return [value.attribute_value for value in mapping.get("values") or []]
	return []


def _cloth_attributes(doc, consumption_context):
	attributes = _unique(
		row.get("attribute") for row in doc.get("cloth_attributes") or []
	)
	if not attributes:
		attributes = [
			attribute
			for attribute in _as_json(doc.get("cutting_cloths_json")).get("attributes") or []
			if attribute != "Cloth"
		]
	if not attributes:
		attributes = [
			consumption_context["panel_attribute"],
			consumption_context["packing_attribute"],
		]
	return _unique(attributes)


def get_cloth_matrix_context(doc):
	consumption_context = get_matrix_context(doc)
	attributes = _cloth_attributes(doc, consumption_context)
	panel_attribute = consumption_context["panel_attribute"]
	packing_attribute = consumption_context["packing_attribute"]
	primary_attribute = consumption_context["primary_attribute"]
	other_attributes = [
		attribute
		for attribute in attributes
		if attribute not in {panel_attribute, packing_attribute}
	]
	attribute_values = {}
	for attribute in other_attributes:
		if attribute == primary_attribute:
			values = consumption_context["primary_values"]
		else:
			values = _mapping_values(doc, attribute)
		if not values:
			frappe.throw(
				_("No values are configured for Cloth Mapping attribute {0}.").format(
					attribute
				)
			)
		attribute_values[attribute] = values

	cloth_options = _unique(
		row.get("name1")
		for row in doc.get("cloth_detail") or []
		if row.get("name1") and row.get("cloth")
	)
	return {
		"attributes": attributes,
		"panel_attribute": panel_attribute,
		"packing_attribute": packing_attribute,
		"other_attributes": other_attributes,
		"attribute_values": attribute_values,
		"cloth_options": cloth_options,
		"uses_panel": panel_attribute in attributes,
		"uses_packing": packing_attribute in attributes,
		"consumption": consumption_context,
	}


def _row_combinations(context):
	attributes = context["other_attributes"]
	if not attributes:
		return [{}]
	return [
		dict(zip(attributes, values))
		for values in product(*(context["attribute_values"][attr] for attr in attributes))
	]


def _row_key(attribute_values, context):
	return tuple(attribute_values.get(attr) for attr in context["other_attributes"])


def _blank_matrix(doc, context):
	consumption_matrix, _ = make_panel_wise_matrix(doc)
	if context["uses_panel"]:
		groups = [
			{
				"group_id": group.get("group_id") or _group_id(_panel_values(group)),
				"panel_value": _group_label(_panel_values(group)),
				"panel_values": _panel_values(group),
				"packing_values": (
					list(group.get("packing_values") or [])
					if context["uses_packing"]
					else [SINGLE_VALUE_KEY]
				),
			}
			for group in consumption_matrix.get("panels") or []
		]
	else:
		groups = [
			{
				"group_id": SINGLE_VALUE_KEY,
				"panel_value": "",
				"panel_values": [],
				"packing_values": (
					list(context["consumption"]["source_packing_values"])
					if context["uses_packing"]
					else [SINGLE_VALUE_KEY]
				),
			}
		]

	rows = _row_combinations(context)
	return {
		"schema_version": SCHEMA_VERSION,
		"attributes": list(context["attributes"]),
		"panel_attribute": context["panel_attribute"],
		"packing_attribute": context["packing_attribute"],
		"other_attributes": list(context["other_attributes"]),
		"cloth_options": list(context["cloth_options"]),
		"panels": [
			{
				**group,
				"rows": [
					{
						"attribute_values": dict(row),
						"values": {
							packing: {"cloth": None}
							for packing in group["packing_values"]
						},
					}
					for row in rows
				],
			}
			for group in groups
		],
	}


def _matrix_indexes(matrix, context):
	row_index = {}
	for group in matrix.get("panels") or []:
		panel_values = _panel_values(group)
		panel_keys = panel_values if context["uses_panel"] else [SINGLE_VALUE_KEY]
		for row in group.get("rows") or []:
			key = _row_key(row.get("attribute_values") or {}, context)
			for panel in panel_keys:
				row_index[(panel, key)] = row
	return row_index


def _set_cloth(cell, cloth, description):
	if not cloth:
		return
	if cell.get("cloth") and cell.get("cloth") != cloth:
		frappe.throw(
			_("Grouped Cloth Mapping {0} points to both {1} and {2}.").format(
				description, cell.get("cloth"), cloth
			)
		)
	cell["cloth"] = cloth


def _merge_expanded_rows(matrix, cutting_cloths, context):
	row_index = _matrix_indexes(matrix, context)
	for item in _as_json(cutting_cloths).get("items") or []:
		panel = (
			item.get(context["panel_attribute"])
			if context["uses_panel"]
			else SINGLE_VALUE_KEY
		)
		row_values = {
			attribute: item.get(attribute)
			for attribute in context["other_attributes"]
		}
		row = row_index.get((panel, _row_key(row_values, context)))
		if not row:
			continue
		packing = (
			item.get(context["packing_attribute"])
			if context["uses_packing"]
			else SINGLE_VALUE_KEY
		)
		cell = (row.get("values") or {}).get(packing)
		if cell is not None:
			_set_cloth(cell, item.get("Cloth"), " / ".join(filter(None, [panel, packing])))


def _merge_saved_matrix(matrix, saved, context):
	saved = _as_json(saved)
	if not saved or saved.get("attributes") != context["attributes"]:
		return
	target_groups = {
		tuple(_panel_values(group)): group for group in matrix.get("panels") or []
	}
	if not context["uses_panel"]:
		target_groups = {(): matrix["panels"][0]}
	target_row_index = _matrix_indexes(matrix, context)
	for source_group in saved.get("panels") or []:
		key = tuple(_panel_values(source_group)) if context["uses_panel"] else ()
		target_group = target_groups.get(key)
		target_rows = (
			{
				_row_key(row.get("attribute_values") or {}, context): row
				for row in target_group.get("rows") or []
			}
			if target_group
			else {}
		)
		for source_row in source_group.get("rows") or []:
			row_key = _row_key(source_row.get("attribute_values") or {}, context)
			target_row = target_rows.get(row_key)
			for packing, source_cell in (source_row.get("values") or {}).items():
				if target_row and packing in target_row.get("values", {}):
					target_row["values"][packing]["cloth"] = (
						(source_cell or {}).get("cloth") or None
					)
					continue
				# Panel grouping may have changed after this draft was entered.
				# Re-apply each old panel's value to the new shared/split target cell.
				panel_keys = (
					_panel_values(source_group)
					if context["uses_panel"]
					else [SINGLE_VALUE_KEY]
				)
				for panel in panel_keys:
					regrouped_row = target_row_index.get((panel, row_key))
					if regrouped_row and packing in regrouped_row.get("values", {}):
						_set_cloth(
							regrouped_row["values"][packing],
							(source_cell or {}).get("cloth"),
							" / ".join(filter(None, [panel, packing])),
						)


def make_panel_wise_cloth_mapping_matrix(doc, include_saved=True):
	context = get_cloth_matrix_context(doc)
	matrix = _blank_matrix(doc, context)
	_merge_expanded_rows(matrix, doc.get("cutting_cloths_json"), context)
	if include_saved:
		_merge_saved_matrix(
			matrix, doc.get("panel_wise_cloth_mapping_json"), context
		)
	return matrix, context


def expand_panel_wise_cloth_mapping_matrix(matrix, context):
	matrix = _as_json(matrix)
	if matrix.get("attributes") != context["attributes"]:
		frappe.throw(
			_("The Cloth Mapping attributes changed. Reload the IPD and review the matrix.")
		)
	valid_cloths = set(context["cloth_options"])
	seen_panels = set()
	items = []
	for group in matrix.get("panels") or []:
		panel_values = _panel_values(group) if context["uses_panel"] else [None]
		if context["uses_panel"]:
			unknown = [
				panel
				for panel in panel_values
				if panel not in context["consumption"]["panel_values"]
			]
			if unknown:
				frappe.throw(
					_("Unknown panel(s) in Cloth Mapping: {0}.").format(
						", ".join(unknown)
					)
				)
			duplicates = [panel for panel in panel_values if panel in seen_panels]
			if duplicates:
				frappe.throw(
					_("Duplicate panel(s) in Cloth Mapping: {0}.").format(
						", ".join(duplicates)
					)
				)
			seen_panels.update(panel_values)
		expected_packings = [SINGLE_VALUE_KEY]
		if context["uses_packing"]:
			expected_packings = (
				_group_packing_values(context["consumption"], panel_values)
				if context["uses_panel"]
				else context["consumption"]["source_packing_values"]
			)
		for row in group.get("rows") or []:
			row_values = row.get("attribute_values") or {}
			for packing, cell in (row.get("values") or {}).items():
				if packing not in expected_packings:
					frappe.throw(
						_("Invalid colour column in Cloth Mapping: {0}.").format(packing)
					)
				cloth = (cell or {}).get("cloth")
				if not cloth:
					continue
				if cloth not in valid_cloths:
					frappe.throw(_("Invalid Cloth label in Cloth Mapping: {0}.").format(cloth))
				for panel in panel_values:
					item = {
						attribute: row_values.get(attribute)
						for attribute in context["other_attributes"]
					}
					if context["uses_panel"]:
						item[context["panel_attribute"]] = panel
					if context["uses_packing"]:
						item[context["packing_attribute"]] = packing
					item["Cloth"] = cloth
					items.append(item)

	if context["uses_panel"]:
		missing = [
			panel
			for panel in context["consumption"]["panel_values"]
			if panel not in seen_panels
		]
		if missing:
			frappe.throw(
				_("Panel(s) missing from Cloth Mapping: {0}.").format(", ".join(missing))
			)
	return {
		"combination_type": "Cloth",
		"attributes": list(context["attributes"]) + ["Cloth"],
		"items": items,
		"select_list": list(context["cloth_options"]),
	}


def sync_panel_wise_cloth_mapping_matrix(doc):
	if not doc.get("enable_panel_wise_consumption_matrix"):
		return
	matrix, context = make_panel_wise_cloth_mapping_matrix(doc)
	expanded = expand_panel_wise_cloth_mapping_matrix(matrix, context)
	doc.panel_wise_cloth_mapping_json = matrix
	doc.cutting_cloths_json = expanded
	doc.set(
		"cloth_attributes",
		[{"attribute": attribute} for attribute in context["attributes"]],
	)


@frappe.whitelist()
def get_panel_wise_cloth_mapping_matrix(doc):
	if isinstance(doc, str):
		doc = (
			frappe.parse_json(doc)
			if doc.lstrip().startswith("{")
			else frappe.get_doc("Item Production Detail", doc)
		)
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)

	include_saved = True
	if not doc.is_new() and doc.name:
		stored_enabled = frappe.db.get_value(
			"Item Production Detail", doc.name, "enable_panel_wise_consumption_matrix"
		)
		include_saved = bool(stored_enabled)
	matrix, _context = make_panel_wise_cloth_mapping_matrix(
		doc, include_saved=include_saved
	)
	return {"matrix": matrix}
