# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt
"""Panel-wise editor for Item Production Detail Cutting combinations.

The compact matrix is an entry aid. ``cutting_items_json`` and
``cutting_attributes`` remain the canonical data consumed by production and
Lot calculations.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import flt


SCHEMA_VERSION = 4
PANEL_COLOUR_SCHEMA_VERSION = 2
CELL_SCHEMA_VERSION = 3


def _as_json(value):
	if isinstance(value, str):
		return json.loads(value) if value else {}
	return value or {}


def _unique(values):
	return list(dict.fromkeys(value for value in values if value))


def _panel_values(panel):
	values = panel.get("panel_values") or [panel.get("panel_value")]
	return _unique(values)


def _group_id(panel_values):
	return "\x1f".join(panel_values)


def _group_label(panel_values):
	return " + ".join(panel_values)


def _group_packing_values(context, panel_values):
	packing_lists = [context["panel_packing_values"][panel] for panel in panel_values]
	if any(values != packing_lists[0] for values in packing_lists[1:]):
		frappe.throw(
			_("Panels {0} cannot be grouped because their fabric colour columns differ.").format(
				", ".join(panel_values)
			)
		)
	return list(packing_lists[0])


def _mapping_values(doc, attribute):
	for row in doc.get("item_attributes") or []:
		if row.attribute == attribute and row.mapping:
			mapping = frappe.get_cached_doc("Item Item Attribute Mapping", row.mapping)
			return [value.attribute_value for value in mapping.get("values") or []]
	return []


def _natural_key(value):
	return [
		int(part) if part.isdigit() else part.lower()
		for part in re.split(r"(\d+)", value or "")
	]


def _panel_colour_context(doc, panel_values, source_packing_values):
	"""Return the actual fabric colours consumed by each stitched panel."""
	panel_colour_map = {panel: {} for panel in panel_values}
	panel_packing_values = {panel: [] for panel in panel_values}

	for detail in doc.get("stiching_item_combination_details") or []:
		panel = detail.get("set_item_attribute_value")
		source_colour = detail.get("major_attribute_value")
		panel_colour = detail.get("attribute_value")
		if panel not in panel_colour_map or not source_colour or not panel_colour:
			continue

		existing = panel_colour_map[panel].get(source_colour)
		if existing and existing != panel_colour:
			frappe.throw(
				_(
					"Panel {0} maps garment colour {1} to both {2} and {3} in "
					"the Stitching tab."
				).format(panel, source_colour, existing, panel_colour)
			)
		panel_colour_map[panel][source_colour] = panel_colour
		if panel_colour not in panel_packing_values[panel]:
			panel_packing_values[panel].append(panel_colour)

	for panel in panel_values:
		if not panel_packing_values[panel]:
			panel_packing_values[panel] = list(source_packing_values)
			panel_colour_map[panel] = {
				colour: colour for colour in source_packing_values
			}

	return panel_colour_map, panel_packing_values


def get_matrix_context(doc):
	primary_attribute = doc.get("primary_item_attribute")
	panel_attribute = doc.get("stiching_attribute")
	packing_attribute = doc.get("packing_attribute")
	attributes = [primary_attribute, panel_attribute, packing_attribute]

	if any(not attribute for attribute in attributes):
		frappe.throw(
			_(
				"Panel-wise Consumption Matrix needs Primary, Stitching/Panel, "
				"and Packing attributes."
			)
		)
	if len(set(attributes)) != 3:
		frappe.throw(
			_(
				"Primary, Stitching/Panel, and Packing attributes must be different "
				"for the Panel-wise Consumption Matrix."
			)
		)
	if doc.get("is_set_item") and doc.get("set_item_attribute") not in attributes:
		frappe.throw(
			_(
				"Panel-wise Consumption Matrix cannot omit the Set Item Attribute {0}."
			).format(doc.get("set_item_attribute"))
		)

	primary_values = _mapping_values(doc, primary_attribute)
	source_packing_values = _unique(
		row.attribute_value for row in doc.get("packing_attribute_details") or []
	)
	panel_values = _unique(
		row.stiching_attribute_value for row in doc.get("stiching_item_details") or []
	)
	if not panel_values:
		panel_values = _mapping_values(doc, panel_attribute)

	missing = []
	if not primary_values:
		missing.append(primary_attribute)
	if not panel_values:
		missing.append(panel_attribute)
	if not source_packing_values:
		missing.append(packing_attribute)
	if missing:
		frappe.throw(
			_("No values are configured for matrix attribute(s): {0}.").format(
				", ".join(missing)
			)
		)

	panel_colour_map, panel_packing_values = _panel_colour_context(
		doc, panel_values, source_packing_values
	)
	packing_values = _unique(
		colour
		for panel in panel_values
		for colour in panel_packing_values[panel]
	)

	return {
		"primary_attribute": primary_attribute,
		"panel_attribute": panel_attribute,
		"packing_attribute": packing_attribute,
		"primary_values": primary_values,
		"panel_values": panel_values,
		"packing_values": packing_values,
		"source_packing_values": source_packing_values,
		"panel_packing_values": panel_packing_values,
		"panel_colour_map": panel_colour_map,
	}


def _blank_matrix(context, panel_groups=None):
	panel_groups = panel_groups or [[panel] for panel in context["panel_values"]]
	return {
		"schema_version": SCHEMA_VERSION,
		"attributes": {
			"primary": context["primary_attribute"],
			"panel": context["panel_attribute"],
			"packing": context["packing_attribute"],
		},
		"primary_values": list(context["primary_values"]),
		"packing_values": list(context["packing_values"]),
		"panel_values": list(context["panel_values"]),
		"panels": [
			{
				"group_id": _group_id(panel_values),
				"panel_value": _group_label(panel_values),
				"panel_values": list(panel_values),
				"packing_values": _group_packing_values(context, panel_values),
				"rows": [
					{
						"primary_value": primary,
						"values": {
							packing: {"dia": None, "weight": None}
							for packing in _group_packing_values(context, panel_values)
						},
					}
					for primary in context["primary_values"]
				],
			}
			for panel_values in panel_groups
		],
	}


def _matrix_indexes(matrix):
	panel_index = {
		tuple(_panel_values(panel)): panel
		for panel in matrix.get("panels") or []
		if _panel_values(panel)
	}
	row_index = {}
	for panel_values, panel in panel_index.items():
		for row in panel.get("rows") or []:
			if row.get("primary_value"):
				for panel_value in panel_values:
					row_index[(panel_value, row.get("primary_value"))] = row
	return panel_index, row_index


def _matrix_schema(value):
	try:
		return int((_as_json(value).get("schema_version") or 1))
	except (TypeError, ValueError):
		return 1


def _saved_panel_groups(saved_matrix, context):
	"""Keep a saved group layout while adapting safely to changed panel mappings."""
	saved_matrix = _as_json(saved_matrix)
	if _matrix_schema(saved_matrix) < SCHEMA_VERSION:
		return [[panel] for panel in context["panel_values"]]

	valid_panels = set(context["panel_values"])
	seen = set()
	groups = []
	for group in saved_matrix.get("panels") or []:
		panel_values = [
			panel
			for panel in _panel_values(group)
			if panel in valid_panels and panel not in seen
		]
		if not panel_values:
			continue
		_group_packing_values(context, panel_values)
		groups.append(panel_values)
		seen.update(panel_values)

	groups.extend([panel] for panel in context["panel_values"] if panel not in seen)
	return groups


def _target_packing_values(context, panel_value, source_value, source_schema):
	panel_values = context["panel_packing_values"][panel_value]
	if not source_value:
		return panel_values
	if source_schema >= PANEL_COLOUR_SCHEMA_VERSION:
		return [source_value] if source_value in panel_values else []

	mapped = context["panel_colour_map"][panel_value].get(source_value)
	return [mapped] if mapped in panel_values else []


def _merge_cell(target, destination, dia, weight, panel_value, primary_value):
	cell = target["values"].setdefault(destination, {"dia": None, "weight": None})
	if dia:
		existing_dia = cell.get("dia")
		if existing_dia and existing_dia != dia:
			frappe.throw(
				_(
					"Cannot convert the existing Cutting rows: panel {0}, {1}, "
					"fabric colour {2} has more than one Dia ({3}, {4})."
				).format(panel_value, primary_value, destination, existing_dia, dia)
			)
		cell["dia"] = dia
	if weight in (None, ""):
		return
	existing = cell.get("weight")
	if existing not in (None, "") and flt(existing, 6) != flt(weight, 6):
		frappe.throw(
			_(
				"Cannot convert the existing Cutting rows: panel {0}, {1}, "
				"fabric colour {2} has different consumptions ({3} and {4}). "
				"Align the old garment-colour rows before enabling this matrix."
			).format(panel_value, primary_value, destination, existing, weight)
		)
	cell["weight"] = weight


def _merge_cutting_rows(matrix, cutting_json, context, source_schema=1):
	"""Hydrate the matrix from standard Cutting rows.

	Older Cutting rows often omit Colour. Their value is copied across every
	configured packing value as a useful starting point when enabling the matrix.
	"""
	cutting_json = _as_json(cutting_json)
	_panel_index, row_index = _matrix_indexes(matrix)
	packing_attribute = context["packing_attribute"]
	contributions = {}

	for item in cutting_json.get("items") or []:
		panel_value = item.get(context["panel_attribute"])
		primary_value = item.get(context["primary_attribute"])
		if not panel_value and len(context["panel_values"]) == 1:
			panel_value = context["panel_values"][0]
		if not primary_value and len(context["primary_values"]) == 1:
			primary_value = context["primary_values"][0]

		target = row_index.get((panel_value, primary_value))
		if not target:
			continue

		packing_value = item.get(packing_attribute)
		destinations = _target_packing_values(
			context, panel_value, packing_value, source_schema
		)
		for destination in destinations:
			cell = target["values"].setdefault(
				destination, {"dia": None, "weight": None}
			)
			dia = item.get("Dia")
			if dia:
				existing_dia = cell.get("dia")
				if existing_dia and existing_dia != dia:
					frappe.throw(
						_(
							"Cannot group Cutting rows: {0}, {1}, {2} has more "
							"than one Dia ({3}, {4})."
						).format(
							panel_value,
							primary_value,
							destination,
							existing_dia,
							dia,
						)
					)
				cell["dia"] = dia

			weight = item.get("Weight")
			if weight in (None, ""):
				continue
			key = (id(target), destination)
			panel_contributions = contributions.setdefault(key, {})
			existing = panel_contributions.get(panel_value)
			if existing not in (None, "") and flt(existing, 6) != flt(weight, 6):
				frappe.throw(
					_(
						"Cannot convert the existing Cutting rows: panel {0}, {1}, "
						"fabric colour {2} has different consumptions ({3} and {4})."
					).format(
						panel_value, primary_value, destination, existing, weight
					)
				)
			panel_contributions[panel_value] = weight

	for panel in matrix.get("panels") or []:
		for row in panel.get("rows") or []:
			for packing in panel.get("packing_values") or []:
				values = contributions.get((id(row), packing), {})
				if values:
					row["values"][packing]["weight"] = flt(
						sum(flt(value, 6) for value in values.values()), 6
					)


def _merge_saved_matrix(matrix, saved_matrix, context):
	saved_matrix = _as_json(saved_matrix)
	if not saved_matrix:
		return

	source_schema = _matrix_schema(saved_matrix)
	_, target_rows = _matrix_indexes(matrix)
	reset_rows = set()
	for panel in saved_matrix.get("panels") or []:
		panel_values = _panel_values(panel)
		if not panel_values:
			continue
		panel_value = panel_values[0]
		for source in panel.get("rows") or []:
			row_key = (panel_value, source.get("primary_value"))
			target = target_rows.get(row_key)
			if not target:
				continue
			target_key = id(target)
			if target_key not in reset_rows:
				target["values"] = {
					colour: {"dia": None, "weight": None}
					for colour in target.get("values") or {}
				}
				reset_rows.add(target_key)
			if source_schema >= CELL_SCHEMA_VERSION:
				source_values = source.get("values") or {}
			else:
				source_values = {
					colour: {"dia": source.get("dia"), "weight": weight}
					for colour, weight in (source.get("weights") or {}).items()
				}
			for source_colour, cell in source_values.items():
				for destination in _target_packing_values(
					context, panel_value, source_colour, source_schema
				):
					_merge_cell(
						target,
						destination,
						(cell or {}).get("dia"),
						(cell or {}).get("weight"),
						panel_value,
						source.get("primary_value"),
					)


def make_panel_wise_matrix(doc, include_saved=True):
	context = get_matrix_context(doc)
	saved_matrix = doc.get("panel_wise_consumption_matrix_json")
	panel_groups = (
		_saved_panel_groups(saved_matrix, context) if include_saved else None
	)
	matrix = _blank_matrix(context, panel_groups=panel_groups)
	source_schema = _matrix_schema(doc.get("panel_wise_consumption_matrix_json"))
	_merge_cutting_rows(
		matrix,
		doc.get("cutting_items_json"),
		context,
		source_schema=source_schema,
	)
	if include_saved:
		# The compact editor is newer and wins over its expanded copy on save.
		_merge_saved_matrix(
			matrix, doc.get("panel_wise_consumption_matrix_json"), context
		)
	return matrix, context


def expand_panel_wise_matrix(matrix, context, require_complete=True):
	"""Validate and expand a compact matrix into the existing Cutting contract."""
	matrix = _as_json(matrix)
	expected_attributes = {
		"primary": context["primary_attribute"],
		"panel": context["panel_attribute"],
		"packing": context["packing_attribute"],
	}
	if matrix.get("attributes") != expected_attributes:
		frappe.throw(
			_(
				"The Panel-wise Consumption Matrix attributes changed. Reload the "
				"IPD and review the matrix before saving."
			)
		)

	items = []
	seen_panels = set()
	for panel in matrix.get("panels") or []:
		panel_values = _panel_values(panel)
		if not panel_values:
			frappe.throw(_("A panel group cannot be empty."))
		unknown = [value for value in panel_values if value not in context["panel_values"]]
		if unknown:
			frappe.throw(
				_("Unknown panel(s) in the consumption matrix: {0}.").format(
					", ".join(unknown)
				)
			)
		duplicates = [value for value in panel_values if value in seen_panels]
		if duplicates:
			frappe.throw(
				_("Duplicate panel(s) in the consumption matrix: {0}.").format(
					", ".join(duplicates)
				)
			)
		seen_panels.update(panel_values)
		packing_values = _group_packing_values(context, panel_values)
		panel_label = _group_label(panel_values)

		rows = {}
		for row in panel.get("rows") or []:
			primary_value = row.get("primary_value")
			if primary_value in rows:
				frappe.throw(
					_("Duplicate {0} row for panel {1}.").format(
						primary_value, panel_label
					)
				)
			rows[primary_value] = row

		for primary_value in context["primary_values"]:
			row = rows.get(primary_value)
			if not row:
				frappe.throw(
					_("{0} is missing for panel {1}.").format(
						primary_value, panel_label
					)
				)
			for packing_value in packing_values:
				cell = (row.get("values") or {}).get(packing_value) or {}
				dia = cell.get("dia")
				raw_weight = cell.get("weight")
				has_weight = raw_weight not in (None, "")
				weight = flt(raw_weight, 6) if has_weight else 0
				if has_weight and weight <= 0:
					frappe.throw(
						_(
							"Enter consumption in kg/piece for panel {0}, {1}, "
							"{2} (example: 0.0300 for 30 grams)."
						).format(panel_label, primary_value, packing_value)
					)
				if not dia and not has_weight and not require_complete:
					continue
				if not dia:
					if not require_complete:
						continue
					frappe.throw(
						_("Enter Dia for panel {0}, {1}, {2}.").format(
							panel_label, primary_value, packing_value
						)
					)
				if not has_weight:
					if not require_complete:
						continue
					frappe.throw(
						_(
							"Enter consumption in kg/piece for panel {0}, {1}, "
							"{2} (example: 0.0300 for 30 grams)."
						).format(panel_label, primary_value, packing_value)
					)
				share = flt(weight / len(panel_values), 6)
				shares = [share] * len(panel_values)
				shares[-1] = flt(weight - sum(shares[:-1]), 6)
				for panel_value, panel_weight in zip(panel_values, shares):
					items.append(
						{
							context["primary_attribute"]: primary_value,
							context["panel_attribute"]: panel_value,
							context["packing_attribute"]: packing_value,
							"Dia": dia,
							"Weight": panel_weight,
						}
					)

	missing_panels = [
		panel for panel in context["panel_values"] if panel not in seen_panels
	]
	if missing_panels:
		frappe.throw(
			_("Panel(s) missing from the consumption matrix: {0}.").format(
				", ".join(missing_panels)
			)
		)

	attributes = [
		context["primary_attribute"],
		context["panel_attribute"],
		context["packing_attribute"],
	]
	return {
		"combination_type": "Cutting",
		"attributes": attributes + ["Dia", "Weight"],
		"items": items,
		"select_list": {},
	}


def sync_panel_wise_consumption_matrix(doc):
	"""Server-side save hook: compact matrix -> standard Cutting combination."""
	if not doc.get("enable_panel_wise_consumption_matrix"):
		return

	matrix, context = make_panel_wise_matrix(doc)
	expanded = expand_panel_wise_matrix(matrix, context, require_complete=False)
	valid_dias = set(
		frappe.get_all(
			"Item Attribute Value",
			filters={"attribute_name": "Dia"},
			pluck="name",
		)
	)
	matrix_dias = _unique(
		cell.get("dia")
		for panel in matrix.get("panels") or []
		for row in panel.get("rows") or []
		for cell in (row.get("values") or {}).values()
		if cell.get("dia")
	)
	invalid_dias = [dia for dia in matrix_dias if dia not in valid_dias]
	if invalid_dias:
		frappe.throw(
			_("Invalid Dia value(s) in the Panel-wise Consumption Matrix: {0}.").format(
				", ".join(invalid_dias)
			)
		)

	doc.panel_wise_consumption_matrix_json = matrix
	doc.cutting_items_json = expanded
	doc.set(
		"cutting_attributes",
		[
			{"attribute": context["primary_attribute"]},
			{"attribute": context["panel_attribute"]},
			{"attribute": context["packing_attribute"]},
		],
	)


@frappe.whitelist()
def get_panel_wise_consumption_matrix(doc):
	"""Return a matrix seeded from unsaved form data and standard Cutting rows."""
	if isinstance(doc, str):
		doc = (
			frappe.parse_json(doc)
			if doc.lstrip().startswith("{")
			else frappe.get_doc("Item Production Detail", doc)
		)
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)

	# Preserve saved draft cells and panel groups while the matrix remains enabled.
	# If it was just enabled over a document saved in standard mode, rebuild from
	# the standard Cutting rows and start with singleton groups.
	include_saved = True
	if not doc.is_new() and doc.name:
		stored_enabled = frappe.db.get_value(
			"Item Production Detail", doc.name, "enable_panel_wise_consumption_matrix"
		)
		include_saved = bool(stored_enabled)
	matrix, context = make_panel_wise_matrix(doc, include_saved=include_saved)
	dia_values = frappe.get_all(
		"Item Attribute Value",
		filters={"attribute_name": "Dia"},
		pluck="name",
	)
	dia_values = sorted(_unique(dia_values), key=_natural_key)
	for panel in matrix["panels"]:
		for row in panel["rows"]:
			for cell in (row.get("values") or {}).values():
				if cell.get("dia") and cell["dia"] not in dia_values:
					dia_values.append(cell["dia"])

	return {
		"matrix": matrix,
		"dia_values": dia_values,
		"row_count": sum(
			len(context["primary_values"])
			* len(context["panel_packing_values"][panel])
			for panel in context["panel_values"]
		),
	}
