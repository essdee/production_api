# Copyright (c) 2026, Essdee and Contributors
# See license.txt

"""Server orchestration for the Lot "Update Colour" feature.

Three whitelisted entry points (plan section 6.2):

* ``get_colour_update_context`` — everything the popup needs; read-only.
* ``preview_colour_update``      — validates + transforms in-memory copies;
*                                   never writes.
* ``apply_colour_update``        — locks, re-validates everything server-side,
*                                   duplicates a shared IPD after explicit
*                                   confirmation, transforms and saves in ONE
*                                   transaction (no manual commits).

All row-level transformation math lives in the pure module
``colour_update_transforms`` so preview and apply cannot drift apart.
"""

import copy
import html
import json
import math

import frappe
from frappe import _
from frappe.utils import flt

from production_api.essdee_production.doctype.lot import colour_update_transforms as T
from production_api.production_api.doctype.item.item import get_or_create_variant, get_variant
from production_api.utils import get_variant_attr_details, update_if_string_instance


LAYSHEET_COLOUR_CHILDREN = (
	("Cutting LaySheet Detail", "Cutting LaySheet"),
	("Cutting LaySheet Bundle", "Cutting LaySheet"),
	("Cutting LaySheet Accessory Detail", "Cutting LaySheet"),
	("Cutting LaySheet Manual Item", "Cutting LaySheet"),
)

JSON_COMBINATION_FIELDS = (
	"cutting_items_json",
	"cutting_cloths_json",
	"cloth_accessory_json",
)


# ---------------------------------------------------------------------------
# Permissions / shared helpers
# ---------------------------------------------------------------------------


def _parse_payload(payload):
	if isinstance(payload, str):
		payload = frappe.parse_json(payload)
	if isinstance(payload, str):
		payload = json.loads(payload)
	return payload


def _targets_for_transform(normalized):
	"""Targets for pure transforms, retaining the source only with live quantity."""
	source = normalized["source_colour"]
	return [
		{
			"colour": target["colour"],
			"retained": target["colour"] == source
			and any(flt(quantity) > 0 for quantity in target["size_quantities"].values()),
		}
		for target in normalized["targets"]
	]


def _truthy(value):
	if isinstance(value, str):
		return value.strip().lower() in ("1", "true", "yes", "on")
	return bool(value)


def _get_lot_and_ipd(lot_name):
	lot = frappe.get_doc("Lot", lot_name)
	if not lot.production_detail:
		frappe.throw(_("This Lot has no Item Production Detail configured."))
	ipd = frappe.get_doc("Item Production Detail", lot.production_detail)
	return lot, ipd


def _require_lot_write_permission(lot):
	if not frappe.has_permission("Lot", ptype="write", doc=lot):
		frappe.throw(_("You need write permission on Lot {0}.").format(lot.name), frappe.PermissionError)


def _get_linked_lots(ipd_name, current_lot):
	return sorted(
		name
		for name in frappe.get_all("Lot", filters={"production_detail": ipd_name}, pluck="name")
		if name != current_lot
	)


def _is_shared_ipd(ipd_name, current_lot):
	return len(_get_linked_lots(ipd_name, current_lot)) > 0


def _require_ipd_write_permission(ipd):
	if not frappe.has_permission("Item Production Detail", ptype="write", doc=ipd):
		frappe.throw(
			_("You need write permission on Item Production Detail {0}.").format(ipd.name),
			frappe.PermissionError,
		)


# ---------------------------------------------------------------------------
# Blockers (plan 3.2 — ONLY these two)
# ---------------------------------------------------------------------------


def find_colour_update_blockers(lot_name, source_colour=None):
	blockers = {"submitted_work_orders": [], "laysheets": []}

	blockers["submitted_work_orders"] = sorted(
		frappe.get_all(
			"Work Order",
			filters={"lot": lot_name, "docstatus": 1},
			pluck="name",
		)
	)

	if not source_colour:
		return blockers, []

	names = set()
	for child_doctype, parent_doctype in LAYSHEET_COLOUR_CHILDREN:
		parents = frappe.get_all(
			child_doctype,
			filters={"colour": source_colour, "parenttype": parent_doctype},
			pluck="parent",
		)
		if not parents:
			continue
		valid = frappe.get_all(
			parent_doctype,
			filters={
				"name": ["in", parents],
				"lot": lot_name,
				"status": ["!=", "Cancelled"],
			},
			pluck="name",
		)
		names.update(valid)
	blockers["laysheets"] = sorted(names)
	return blockers, blockers["submitted_work_orders"] or blockers["laysheets"]


def _throw_blockers(blockers):
	parts = []
	if blockers["submitted_work_orders"]:
		links = ", ".join(
			'<a href="/app/work-order/{0}">{0}</a>'.format(html.escape(str(name), quote=False))
			for name in blockers["submitted_work_orders"]
		)
		parts.append(_("Submitted Work Order(s): {0}").format(links))
	if blockers["laysheets"]:
		links = ", ".join(
			'<a href="/app/cutting-laysheet/{0}">{0}</a>'.format(html.escape(str(name), quote=False))
			for name in blockers["laysheets"]
		)
		parts.append(_("Non-cancelled Cutting LaySheet(s) containing the source colour: {0}").format(links))
	if parts:
		frappe.throw("<br>".join(parts), frappe.ValidationError)


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def _colour_size_grid(lot, ipd):
	"""Current colour x size quantity grid from the LIVE Lot rows.

	Set items: only the major part's rows count (the popup quantity is the
	major colour / primary size quantity, exactly like the order grid).
	"""
	grid = {}
	order = []
	for row in lot.lot_order_details:
		attrs = get_variant_attr_details(row.item_variant)
		if ipd.is_set_item:
			set_comb = update_if_string_instance(row.set_combination) or {}
			colour = set_comb.get("major_colour")
			if attrs.get(ipd.set_item_attribute) != ipd.major_attribute_value:
				continue
		else:
			colour = attrs.get(ipd.packing_attribute)
		size = attrs.get(ipd.primary_item_attribute)
		if not colour:
			continue
		if colour not in grid:
			grid[colour] = {}
			order.append(colour)
		grid[colour][size] = grid[colour].get(size, 0) + row.quantity
	return grid, order


def _structure_field_rows(ipd, fieldname):
	structure, _error = T.parse_json_structure(ipd.get(fieldname) or None)
	if not isinstance(structure, dict):
		return []
	return structure.get("items") or []


def _non_colour_combinations(
	ipd, fieldname, packing_attribute, configured_fields=None
):
	"""Distinct non-colour attribute combos already configured (for Add inputs)."""
	rows = _structure_field_rows(ipd, fieldname)
	structure, _error = T.parse_json_structure(ipd.get(fieldname) or None)
	if not isinstance(structure, dict):
		return []
	configured_fields = set(configured_fields or [])
	declared = [
		a
		for a in (structure.get("attributes") or [])
		if a != packing_attribute and a not in configured_fields
	]
	combos = []
	seen = set()
	for row in rows:
		if not isinstance(row, dict):
			continue
		key = json.dumps({attribute: row.get(attribute) for attribute in declared}, sort_keys=True)
		if key not in seen:
			seen.add(key)
			combos.append({attribute: row.get(attribute) for attribute in declared})
	return combos


def _available_attribute_values(attribute):
	if not attribute:
		return []
	return sorted(
		frappe.get_all("Item Attribute Value", filters={"attribute_name": attribute}, pluck="name")
	)


def _colour_dependent_bom_mappings(ipd):
	names = []
	for row in ipd.item_bom:
		if not (row.based_on_attribute_mapping and row.attribute_mapping):
			continue
		values = frappe.get_all(
			"Item BOM Attribute Mapping Value",
			filters={"parent": row.attribute_mapping, "parentfield": "values"},
			fields=["attribute", "type"],
			limit_page_length=1,
		)
		if any(v.attribute == ipd.packing_attribute and v.type == "item" for v in values):
			names.append(row.attribute_mapping)
	return sorted(set(names))


def _relevant_process_costs(lot_name, packing_attribute):
	return frappe.get_all(
		"Process Cost",
		filters={
			"lot": lot_name,
			"docstatus": ["<", 2],
			"depends_on_attribute": 1,
			"attribute": packing_attribute,
		},
		fields=["name", "docstatus", "process_name", "from_date", "to_date"],
		order_by="name asc",
	)


def _process_cost_values(name):
	return frappe.get_all(
		"Process Cost Value",
		filters={"parent": name, "parentfield": "process_cost_values"},
		fields=["attribute_value", "price", "min_order_qty"],
		order_by="idx asc",
	)


def _packing_requirement(ipd):
	rows = [
		{"attribute_value": row.attribute_value, "quantity": row.quantity}
		for row in ipd.packing_attribute_details
	]
	return {
		"auto_calculate": bool(ipd.auto_calculate),
		"packing_combo": ipd.packing_combo,
		"packing_mode": ipd.packing_mode,
		"based_on_other_attribute_mapping": bool(ipd.based_on_other_attribute_mapping),
		"current_rows": rows,
	}


def _panel_cutting_combinations(ipd):
	"""Panel-aware non-colour combos: one per (panel group, primary value)."""
	matrix, _error = T.parse_json_structure(ipd.get("panel_wise_consumption_matrix_json") or None)
	if not isinstance(matrix, dict):
		return []
	attributes = matrix.get("attributes") or {}
	primary = attributes.get("primary")
	panel = attributes.get("panel")
	combos = []
	for panel_entry in matrix.get("panels") or []:
		for row in panel_entry.get("rows") or []:
			combos.append({panel: panel_entry.get("group_id"), primary: row.get("primary_value")})
	return combos


def _panel_cloth_combinations(ipd):
	matrix, _error = T.parse_json_structure(ipd.get("panel_wise_cloth_mapping_json") or None)
	if not isinstance(matrix, dict):
		return []
	panel_attribute = matrix.get("panel_attribute")
	other_attributes = matrix.get("other_attributes") or []
	combos = []
	seen = set()
	for panel_entry in matrix.get("panels") or []:
		for row in panel_entry.get("rows") or []:
			combination = {panel_attribute: panel_entry.get("group_id")}
			combination.update(row.get("attribute_values") or {})
			key = json.dumps(combination, sort_keys=True)
			if key not in seen:
				seen.add(key)
				combos.append(combination)
	return combos


def _cutting_requirement(ipd):
	structure, _error = T.parse_json_structure(ipd.get("cutting_items_json") or None)
	uses = bool(structure and T.structure_uses_attribute(structure, ipd.packing_attribute))
	requirement = {
		"uses_colour": uses,
		"attributes": [],
		"combinations": [],
		"select_lists": {},
		"dia_options": [],
	}
	if isinstance(structure, dict):
		requirement["attributes"] = [
			attribute
			for attribute in (structure.get("attributes") or [])
			if attribute not in (ipd.packing_attribute, "Dia", "Weight")
		]
	if ipd.enable_panel_wise_consumption_matrix:
		matrix, _error = T.parse_json_structure(ipd.get("panel_wise_consumption_matrix_json") or None)
		attributes = (matrix or {}).get("attributes") or {}
		requirement["combinations"] = _panel_cutting_combinations(ipd)
		requirement["panel_attribute"] = attributes.get("panel")
		requirement["primary_attribute"] = attributes.get("primary")
		requirement["panel_mode"] = True
	else:
		requirement["combinations"] = _non_colour_combinations(
			ipd,
			"cutting_items_json",
			ipd.packing_attribute,
			configured_fields=("Dia", "Weight"),
		)
		requirement["panel_mode"] = False
	requirement["dia_options"] = sorted(
		set(
			frappe.get_all(
				"Item Attribute Value", filters={"attribute_name": "Dia"}, pluck="name"
			)
		)
	)
	return requirement


def _cloth_requirement(ipd):
	structure, _error = T.parse_json_structure(ipd.get("cutting_cloths_json") or None)
	uses = bool(structure and T.structure_uses_attribute(structure, ipd.packing_attribute))
	requirement = {"uses_colour": uses, "attributes": [], "combinations": [], "select_lists": {}}
	if isinstance(structure, dict):
		requirement["attributes"] = [
			attribute
			for attribute in (structure.get("attributes") or [])
			if attribute not in (ipd.packing_attribute, "Cloth")
		]
		requirement["select_lists"]["Cloth"] = list(structure.get("select_list") or [])
		requirement["select_lists"]["Cloth"] = [
			cloth for cloth in requirement["select_lists"]["Cloth"] if cloth
		]
	if ipd.enable_panel_wise_consumption_matrix:
		matrix, _error = T.parse_json_structure(ipd.get("panel_wise_cloth_mapping_json") or None)
		requirement["combinations"] = _panel_cloth_combinations(ipd)
		requirement["panel_attribute"] = (matrix or {}).get("panel_attribute")
		requirement["other_attributes"] = (matrix or {}).get("other_attributes") or []
		requirement["panel_mode"] = True
	else:
		requirement["combinations"] = _non_colour_combinations(
			ipd,
			"cutting_cloths_json",
			ipd.packing_attribute,
			configured_fields=("Cloth",),
		)
		requirement["panel_mode"] = False
	return requirement


def _stitching_requirement(ipd):
	parts = []
	seen = set()
	for row in ipd.stiching_item_combination_details:
		part = row.set_item_attribute_value
		if part not in seen:
			seen.add(part)
			parts.append(part)
	return {
		"is_same_packing_attribute": bool(ipd.is_same_packing_attribute),
		"stitching_parts": parts,
	}


def _colour_dependent_accessory_structures(ipd):
	"""Return populated accessory JSON fields whose rows depend on colour."""
	fields = []
	structure, _error = T.parse_json_structure(ipd.get("cloth_accessory_json") or None)
	if (
		isinstance(structure, dict)
		and structure.get("items")
		and T.structure_uses_attribute(structure, ipd.packing_attribute)
	):
		fields.append("cloth_accessory_json")
	structure, _error = T.parse_json_structure(ipd.get("stiching_accessory_json") or None)
	if isinstance(structure, dict) and structure.get("items"):
		declared = structure.get("attributes") or []
		if "Major Colour" in declared or ipd.packing_attribute in declared:
			fields.append("stiching_accessory_json")
	return fields


def _set_item_requirement(ipd):
	if not ipd.is_set_item:
		return None
	return {
		"set_item_attribute": ipd.set_item_attribute,
		"major_attribute_value": ipd.major_attribute_value,
		"parts": sorted({row.set_item_attribute_value for row in ipd.set_item_combination_details}),
	}


@frappe.whitelist()
def get_colour_update_context(lot):
	lot, ipd = _get_lot_and_ipd(lot)
	_require_lot_write_permission(lot)

	grid, colour_order = _colour_size_grid(lot, ipd)
	sizes = []
	for colour in colour_order:
		for size in grid.get(colour, {}):
			if size not in sizes:
				sizes.append(size)

	colours = []
	packing_rows = {row.attribute_value: row.quantity for row in ipd.packing_attribute_details}
	for colour in colour_order:
		colours.append(
			{
				"colour": colour,
				"packing_quantity": packing_rows.get(colour, 0),
				"size_quantities": grid.get(colour, {}),
				"total": sum(grid.get(colour, {}).values()),
			}
		)

	blockers, _has_blockers = find_colour_update_blockers(lot.name)
	process_costs = []
	for pc in _relevant_process_costs(lot.name, ipd.packing_attribute):
		process_costs.append(
			{
				"name": pc.name,
				"docstatus": pc.docstatus,
				"process_name": pc.process_name,
				"from_date": pc.from_date,
				"to_date": pc.to_date,
				"values": _process_cost_values(pc.name),
			}
		)

	return {
		"lot": lot.name,
		"lot_modified": lot.modified,
		"ipd": ipd.name,
		"ipd_modified": ipd.modified,
		"packing_attribute": ipd.packing_attribute,
		"primary_item_attribute": ipd.primary_item_attribute,
		"colours": colours,
		"sizes": sizes,
		"total_order_quantity": lot.total_order_quantity,
		"shared_ipd": {
			"is_shared": _is_shared_ipd(ipd.name, lot.name),
			"linked_lots": _get_linked_lots(ipd.name, lot.name),
		},
		"requirements": {
			"is_set_item": bool(ipd.is_set_item),
			"set_item": _set_item_requirement(ipd),
			"packing": _packing_requirement(ipd),
			"cutting": _cutting_requirement(ipd),
			"cloth": _cloth_requirement(ipd),
			"stitching": _stitching_requirement(ipd),
			"panel_wise": bool(ipd.enable_panel_wise_consumption_matrix),
			"has_colour_dependent_bom_mappings": bool(_colour_dependent_bom_mappings(ipd)),
			"has_colour_dependent_accessory_mappings": bool(
				_colour_dependent_accessory_structures(ipd)
			),
		},
		"available_colours": _available_attribute_values(ipd.packing_attribute),
		"process_costs": process_costs,
		"blockers": blockers,
	}


# ---------------------------------------------------------------------------
# Payload validation against the live IPD
# ---------------------------------------------------------------------------


def _validate_payload_against_ipd(ipd, normalized, grid, lot_name=None):
	errors = []
	operation = normalized["operation"]
	source = normalized["source_colour"]
	targets = normalized["targets"]

	if operation in ("split_convert", "remove"):
		if source not in grid:
			errors.append(
				_("Source colour {0} has no Lot Order Detail rows.").format(source)
			)
	if operation == "split_convert":
		errors.extend(
			T.validate_size_allocations(
				grid.get(source) or {},
				targets,
				precision=frappe.get_precision("Lot Order Detail", "quantity"),
			)
		)

	if operation == "add":
		target = targets[0]
		new_colour = target["colour"]
		existing = {row.attribute_value for row in ipd.packing_attribute_details}
		if new_colour in existing:
			errors.append(
				_("Colour {0} is already configured in this IPD.").format(new_colour)
			)
		if not any(quantity > 0 for quantity in target["size_quantities"].values()):
			errors.append(_("Enter at least one positive size quantity for the new colour."))

		mapping = target.get("set_or_stitching_mapping") or {}
		if ipd.is_set_item:
			required_parts = {
				row.set_item_attribute_value for row in ipd.set_item_combination_details
			}
			provided = (mapping.get("set") or {}) if isinstance(mapping, dict) else {}
			missing = sorted(part for part in required_parts if not provided.get(part))
			if missing:
				errors.append(
					_("Enter set-part colour mappings for: {0}.").format(", ".join(missing))
				)
		if not ipd.is_same_packing_attribute:
			required_stitching_parts = {
				row.set_item_attribute_value for row in ipd.stiching_item_combination_details
			}
			provided = (mapping.get("stitch") or {}) if isinstance(mapping, dict) else {}
			missing = sorted(part for part in required_stitching_parts if not provided.get(part))
			if missing:
				errors.append(
					_("Enter stitching colour mappings for: {0}.").format(", ".join(missing))
				)

		cutting = _cutting_requirement(ipd)
		if cutting["uses_colour"]:
			rows = target.get("cutting_rows") or []
			if len(rows) != len(cutting["combinations"]):
				errors.append(
					_("Enter Dia and Weight for all {0} required cutting combinations.").format(
						len(cutting["combinations"])
					)
				)
			for index, row in enumerate(rows, start=1):
				values = row.get("cell") if cutting.get("panel_mode") else row
				values = values or {}
				dia = values.get("dia") if cutting.get("panel_mode") else values.get("Dia")
				weight = values.get("weight") if cutting.get("panel_mode") else values.get("Weight")
				if dia in (None, "") or weight in (None, ""):
					errors.append(
						_("Cutting combination #{0} requires both Dia and Weight.").format(index)
					)
			if not cutting.get("panel_mode") and len(rows) == len(cutting["combinations"]):
				expected = sorted(
					json.dumps(combination, sort_keys=True)
					for combination in cutting["combinations"]
				)
				actual = sorted(
					json.dumps(
						{attribute: row.get(attribute) for attribute in cutting["attributes"]},
						sort_keys=True,
					)
					for row in rows
				)
				if actual != expected:
					errors.append(_("Cutting rows do not match the required attribute combinations."))

		cloth = _cloth_requirement(ipd)
		if cloth["uses_colour"]:
			rows = target.get("cloth_rows") or []
			if len(rows) != len(cloth["combinations"]):
				errors.append(
					_("Select Cloth for all {0} required cloth combinations.").format(
						len(cloth["combinations"])
					)
				)
			for index, row in enumerate(rows, start=1):
				values = row.get("cell") if cloth.get("panel_mode") else row
				values = values or {}
				cloth_value = values.get("cloth") if cloth.get("panel_mode") else values.get("Cloth")
				if cloth_value in (None, ""):
					errors.append(_("Cloth combination #{0} requires a Cloth value.").format(index))
			if not cloth.get("panel_mode") and len(rows) == len(cloth["combinations"]):
				expected = sorted(
					json.dumps(combination, sort_keys=True)
					for combination in cloth["combinations"]
				)
				actual = sorted(
					json.dumps(
						{attribute: row.get(attribute) for attribute in cloth["attributes"]},
						sort_keys=True,
					)
					for row in rows
				)
				if actual != expected:
					errors.append(_("Cloth rows do not match the required attribute combinations."))

	all_colours = [source] if source else []
	all_colours.extend(target["colour"] for target in targets)
	valid_values = set(_available_attribute_values(ipd.packing_attribute))
	for colour in all_colours:
		if colour and colour not in valid_values:
			errors.append(
				_("{0} is not an Item Attribute Value of {1}.").format(
					colour, ipd.packing_attribute
				)
			)

	if normalized["reference_colour"]:
		if normalized["reference_colour"] not in valid_values:
			errors.append(
				_("Reference colour {0} is not an Item Attribute Value of {1}.").format(
					normalized["reference_colour"], ipd.packing_attribute
				)
			)
		elif normalized["reference_colour"] not in {row.attribute_value for row in ipd.packing_attribute_details}:
			errors.append(
				_("Reference colour {0} is not configured in this IPD.").format(
					normalized["reference_colour"]
				)
			)

	if operation == "add" and not normalized["reference_colour"]:
		reasons = []
		if _colour_dependent_accessory_structures(ipd):
			reasons.append(_("colour-dependent accessory combinations"))
		if _colour_dependent_bom_mappings(ipd):
			reasons.append(_("colour-dependent BOM mappings"))
		if _relevant_process_costs(lot_name, ipd.packing_attribute):
			reasons.append(_("colour-dependent Process Costs"))
		if reasons:
				errors.append(
					_("A Reference Colour is required because {0} exist.").format(", ".join(reasons))
				)
	if operation == "add" and normalized["reference_colour"]:
		for mapping_name in _colour_dependent_bom_mappings(ipd):
			if not frappe.db.exists(
				"Item BOM Attribute Mapping Value",
				{
					"parent": mapping_name,
					"parentfield": "values",
					"type": "item",
					"attribute": ipd.packing_attribute,
					"attribute_value": normalized["reference_colour"],
				},
			):
				errors.append(
					_("BOM mapping {0} has no group for Reference Colour {1}.").format(
						mapping_name,
						normalized["reference_colour"],
					)
				)
		for process_cost in _relevant_process_costs(lot_name, ipd.packing_attribute):
			if not any(
				row.attribute_value == normalized["reference_colour"]
				for row in _process_cost_values(process_cost.name)
			):
				errors.append(
					_("Process Cost {0} has no value for Reference Colour {1}.").format(
						process_cost.name,
						normalized["reference_colour"],
					)
				)
	if not ipd.auto_calculate and operation in ("split_convert", "add"):
		final_rows = normalized["manual_packing_rows"]
		if not final_rows:
			errors.append(
				_("This IPD uses manual packing ratios; enter the complete rebalanced Packing Attribute Details.")
			)
		else:
			total = sum(flt(row.get("quantity")) for row in final_rows)
			if abs(total - flt(ipd.packing_combo)) > 1e-6:
				errors.append(
					_("Packing ratio total {0} must equal the Packing Combo {1}.").format(
						T.fmt_qty(total), T.fmt_qty(ipd.packing_combo)
					)
				)
			values = [row.get("attribute_value") for row in final_rows]
			if len(values) != len(set(values)):
				errors.append(_("Packing ratio rows contain duplicate colours."))
			if any(flt(row.get("quantity")) < 0 for row in final_rows):
				errors.append(_("Packing ratio quantities cannot be negative."))
			existing = {row.attribute_value for row in ipd.packing_attribute_details}
			if operation == "split_convert":
				existing.discard(source)
			expected = existing | {
				target["colour"]
				for target in targets
				if target["colour"] != source
				or any(flt(quantity) > 0 for quantity in target["size_quantities"].values())
			}
			if set(values) != expected:
				errors.append(
					_("Packing ratio rows must contain exactly these colours: {0}.").format(
						", ".join(sorted(expected))
					)
				)
			if operation == "split_convert":
				final_quantities = {
					row.get("attribute_value"): flt(row.get("quantity")) for row in final_rows
				}
				target_colours = {target["colour"] for target in targets}
				for row in ipd.packing_attribute_details:
					if row.attribute_value == source or row.attribute_value in target_colours:
						continue
					if abs(final_quantities.get(row.attribute_value, 0) - flt(row.quantity)) > 1e-6:
						errors.append(
							_("Packing ratio for unaffected colour {0} must remain {1}.").format(
								row.attribute_value, T.fmt_qty(row.quantity)
							)
						)
	return errors


def _throw_validation_errors(errors):
	if errors:
		frappe.throw(
			"<br>".join(html.escape(str(error)) for error in errors),
			frappe.ValidationError,
		)


# ---------------------------------------------------------------------------
# IPD duplication (shared-IPD path) with INDEPENDENT mappings
# ---------------------------------------------------------------------------


def _copy_item_attribute_mapping(mapping_name):
	source = frappe.get_doc("Item Item Attribute Mapping", mapping_name)
	new_doc = frappe.copy_doc(source)
	# Safe internal copy: the caller verified the initiating user may modify
	# the IPD whose configuration is being copied. The new mapping is private
	# to the duplicate IPD, so later colour edits can never leak to the source.
	new_doc.insert(ignore_permissions=True)
	return new_doc.name


def _copy_dependent_attribute_mapping(mapping_name):
	source = frappe.get_doc("Item Dependent Attribute Mapping", mapping_name)
	new_doc = frappe.copy_doc(source)
	new_doc.insert(ignore_permissions=True)
	return new_doc.name


def _copy_bom_attribute_mapping(mapping_name, duplicate_ipd_name):
	source = frappe.get_doc("Item BOM Attribute Mapping", mapping_name)
	new_doc = frappe.copy_doc(source)
	new_doc.item_production_detail = duplicate_ipd_name
	new_doc.insert(ignore_permissions=True)
	return new_doc.name


def build_ipd_duplicate(source_ipd):
	"""Assemble an independent IPD duplicate for the colour update flow.

	Mirrors ``duplicate_ipd`` (same table copy sequence, same SD/YRP
	suppression through intermediate saves) but creates INDEPENDENT Item
	Attribute / Dependent Attribute / BOM Attribute mappings so colour
	transforms can never leak into the source IPD. Returns the saved-but-
	incomplete duplicate with ``skip_sd_yrp_sync`` still set; the caller
	transforms it and performs the final publishing save.
	"""
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
		copy_duplicate_ipd_scalar_fields,
		get_dict_table,
	)

	doc = frappe.new_doc("Item Production Detail")
	doc.flags.skip_sd_yrp_sync = True
	copy_duplicate_ipd_scalar_fields(source_ipd, doc)

	# Keep the source links only on the unsaved document. IPD.validate() calls
	# create_new_mapping_values() for a new document and duplicates the Item
	# and Dependent mappings. Pre-copying those here would create an unused
	# extra generation of mappings. BOM mappings are copied after the IPD has
	# a database identity (below), because they link back to the new IPD.
	doc.set("item_attributes", get_dict_table(source_ipd.item_attributes))

	doc.set("ipd_processes", get_dict_table(source_ipd.ipd_processes))
	doc.set("packing_attribute_details", get_dict_table(source_ipd.packing_attribute_details))
	doc.set("stiching_item_details", get_dict_table(source_ipd.stiching_item_details))
	doc.set("stiching_item_combination_details", get_dict_table(source_ipd.stiching_item_combination_details))
	doc.set("cutting_attributes", get_dict_table(source_ipd.cutting_attributes))
	doc.set("cloth_detail", get_dict_table(source_ipd.cloth_detail))
	doc.set("accessory_attributes", get_dict_table(source_ipd.accessory_attributes))
	doc.set("cloth_attributes", get_dict_table(source_ipd.cloth_attributes))
	if source_ipd.is_set_item:
		doc.update(
			{
				"is_set_item": source_ipd.is_set_item,
				"set_item_attribute": source_ipd.set_item_attribute,
				"major_attribute_value": source_ipd.major_attribute_value,
			}
		)
		doc.set("set_item_combination_details", get_dict_table(source_ipd.set_item_combination_details))

	# A BOM mapping links back to the new IPD, so the IPD must exist before
	# those mapping documents can be inserted. Save the otherwise complete IPD
	# first; unlike the old flow, do not add mapping-enabled BOM rows with a
	# blank link (which made validate() create empty mappings that became
	# orphans moments later).
	doc.save(ignore_permissions=True)

	# before_save applied the site's IPD Settings defaults to the new IPD;
	# restore the source's process configuration so later saves validate
	# against the same rules the source satisfied.
	for fieldname in (
		"packing_process",
		"pack_in_stage",
		"pack_out_stage",
		"stiching_process",
		"stiching_in_stage",
		"stiching_out_stage",
		"cutting_process",
		"stiching_attribute",
	):
		doc.set(fieldname, source_ipd.get(fieldname))

	items = []
	for source_row in source_ipd.item_bom:
		mapping_name = None
		if source_row.based_on_attribute_mapping and source_row.attribute_mapping:
			mapping_name = _copy_bom_attribute_mapping(source_row.attribute_mapping, doc.name)
		items.append(
			{
				"item": source_row.item,
				"process_name": source_row.process_name,
				"dependent_attribute_value": source_row.dependent_attribute_value,
				"qty_of_product": source_row.qty_of_product,
				"qty_of_bom_item": source_row.qty_of_bom_item,
				"based_on_attribute_mapping": source_row.based_on_attribute_mapping,
				"attribute_mapping": mapping_name,
			}
		)
	doc.set("item_bom", items)

	return doc


def _ensure_private_mappings(ipd):
	"""If another IPD references one of this IPD's mappings, copy it first."""
	changed = []
	for row in ipd.item_attributes:
		if not row.mapping:
			continue
		shared = frappe.get_all(
			"Item Item Attribute",
			filters={"mapping": row.mapping, "parent": ["!=", ipd.name]},
			pluck="parent",
			limit_page_length=1,
		)
		if shared:
			row.mapping = _copy_item_attribute_mapping(row.mapping)
			changed.append(("Item Item Attribute Mapping", row.mapping))
	if ipd.dependent_attribute_mapping:
		shared = frappe.get_all(
			"Item Dependent Attribute Mapping",
			filters={"name": ipd.dependent_attribute_mapping},
			pluck="name",
			limit_page_length=1,
		)
		# Dependent mappings are single-doc; ownership check via reverse link:
		other_ipds = frappe.get_all(
			"Item Production Detail",
			filters={"dependent_attribute_mapping": ipd.dependent_attribute_mapping, "name": ["!=", ipd.name]},
			pluck="name",
			limit_page_length=1,
		)
		if other_ipds:
			ipd.dependent_attribute_mapping = _copy_dependent_attribute_mapping(
				ipd.dependent_attribute_mapping
			)
			changed.append(("Item Dependent Attribute Mapping", ipd.dependent_attribute_mapping))
	for row in ipd.item_bom:
		if not (row.based_on_attribute_mapping and row.attribute_mapping):
			continue
		other_ipds = frappe.get_all(
			"Item BOM",
			filters={
				"attribute_mapping": row.attribute_mapping,
				"parent": ["!=", ipd.name],
				"parenttype": "Item Production Detail",
			},
			pluck="parent",
			limit_page_length=1,
		)
		if other_ipds:
			row.attribute_mapping = _copy_bom_attribute_mapping(
				row.attribute_mapping, ipd.name
			)
			changed.append(("Item BOM Attribute Mapping", row.attribute_mapping))
	return changed


# ---------------------------------------------------------------------------
# IPD transformation (used identically by preview + apply)
# ---------------------------------------------------------------------------


def _get_packing_mapping_doc(ipd):
	for row in ipd.item_attributes:
		if row.attribute == ipd.packing_attribute:
			return frappe.get_doc("Item Item Attribute Mapping", row.mapping)
	return None


def _colour_still_referenced(ipd, colour):
	"""True when any post-transform IPD structure still uses the colour."""
	if any(row.attribute_value == colour for row in ipd.packing_attribute_details):
		return True
	for row in ipd.set_item_combination_details:
		if colour in (row.major_attribute_value, row.attribute_value):
			return True
	for row in ipd.stiching_item_combination_details:
		if colour in (row.major_attribute_value, row.attribute_value):
			return True
	for fieldname in JSON_COMBINATION_FIELDS:
		structure, _error = T.parse_json_structure(ipd.get(fieldname) or None)
		if not isinstance(structure, dict):
			continue
		for row in structure.get("items") or []:
			if isinstance(row, dict) and ipd.packing_attribute in row and row.get(ipd.packing_attribute) == colour:
				return True
	stitch_structure, _error = T.parse_json_structure(ipd.get("stiching_accessory_json") or None)
	if isinstance(stitch_structure, dict):
		for row in stitch_structure.get("items") or []:
			if isinstance(row, dict) and row.get("major_colour") == colour:
				return True
	for fieldname in ("panel_wise_consumption_matrix_json", "panel_wise_cloth_mapping_json"):
		matrix, _error = T.parse_json_structure(ipd.get(fieldname) or None)
		if not isinstance(matrix, dict):
			continue
		if colour in (matrix.get("packing_values") or []):
			return True
		for panel in matrix.get("panels") or []:
			if colour in (panel.get("packing_values") or []):
				return True
	return False


def _transform_ipd(ipd, normalized, conflicts):
	"""Mutate the in-memory IPD.

	Returns ``(diff, mapping_docs)``; ``mapping_docs`` are the loaded (mutated,
	unsaved) child mapping documents the caller must save after the IPD itself.
	"""
	operation = normalized["operation"]
	source = normalized["source_colour"]
	targets = normalized["targets"]
	targets_with_retained = _targets_for_transform(normalized)
	add_reference_colour = normalized["reference_colour"]
	if operation == "add" and not add_reference_colour:
		add_reference_colour = next(
			(row.attribute_value for row in ipd.packing_attribute_details), None
		)
	diff = {}

	# 1. Packing Attribute Details ------------------------------------------
	manual_rows = None
	if not ipd.auto_calculate and normalized["manual_packing_rows"]:
		manual_rows = normalized["manual_packing_rows"]
	new_packing, packing_diff = T.transform_packing_attribute_rows(
		[row.as_dict() for row in ipd.packing_attribute_details],
		source,
		targets_with_retained,
		operation,
		manual_rows=manual_rows,
	)
	ipd.set(
		"packing_attribute_details",
		[
			{
				"attribute_value": row.get("attribute_value"),
				"quantity": flt(row.get("quantity")) if not ipd.auto_calculate else 0,
			}
			for row in new_packing
		],
	)
	ipd.packing_attribute_no = len(ipd.packing_attribute_details)
	diff["packing_attribute_details"] = packing_diff

	# 2. Item Attribute mapping values --------------------------------------
	# New target values are added up-front; the SOURCE value is only removed
	# after every other structure has been transformed (it may legitimately
	# survive as an unrelated per-part colour).
	mapping_doc = _get_packing_mapping_doc(ipd)
	if mapping_doc is not None:
		existing_values = [row.attribute_value for row in mapping_doc.values]
		needed = [target["colour"] for target in targets if target["colour"] != source]
		for colour in needed:
			if colour not in existing_values:
				mapping_doc.append("values", {"attribute_value": colour})
		diff["item_attribute_mapping"] = {
			"doctype": "Item Item Attribute Mapping",
			"name": mapping_doc.name,
			"values": [row.attribute_value for row in mapping_doc.values],
		}

	# 3. Set item combinations ----------------------------------------------
	mapping_payload = targets[0].get("set_or_stitching_mapping") if operation == "add" else None
	if isinstance(mapping_payload, str):
		mapping_payload = update_if_string_instance(mapping_payload)
	set_mapping = (mapping_payload or {}).get("set") if isinstance(mapping_payload, dict) else None
	stitch_mapping = (mapping_payload or {}).get("stitch") if isinstance(mapping_payload, dict) else None
	if ipd.is_set_item:
		reference_rows = None
		mapping = None
		if operation == "add":
			new_colour = targets[0]["colour"]
			if set_mapping:
				mapping = set_mapping
			elif ipd.is_same_packing_attribute:
				# Same packing/stitching attribute: every part uses the new
				# colour automatically (plan 4.3 Stitching behavior).
				mapping = {
					part: new_colour
					for part in sorted({row.set_item_attribute_value for row in ipd.set_item_combination_details})
				}
			else:
				conflicts.append(
					{
						"structure": "set_item_combination_details",
						"message": _(
							"This IPD uses separate stitching colours; enter the set part colour mapping."
						),
					}
				)
		new_rows, set_diff = T.transform_major_colour_rows(
			[row.as_dict() for row in ipd.set_item_combination_details],
			source,
			targets_with_retained,
			operation,
			reference_rows=reference_rows,
			mapping=mapping,
		)
		ipd.set("set_item_combination_details", new_rows)
		diff["set_item_combination_details"] = set_diff

	# 4. Stitching combinations ---------------------------------------------
	stitch_reference_rows = None
	if operation == "add":
		new_colour = targets[0]["colour"]
		if ipd.is_same_packing_attribute:
			stitch_mapping = {
				part: new_colour
				for part in sorted({row.set_item_attribute_value for row in ipd.stiching_item_combination_details})
			}
		elif stitch_mapping:
			pass
		else:
			stitch_mapping = None
			conflicts.append(
				{
					"structure": "stiching_item_combination_details",
					"message": _(
						"This IPD uses a separate stitching colour; enter the stitching mapping."
					),
				}
			)
		if normalized["reference_colour"]:
			stitch_reference_rows = [
				row.as_dict()
				for row in ipd.stiching_item_combination_details
				if row.major_attribute_value == normalized["reference_colour"]
			]
	new_rows, stitch_diff = T.transform_major_colour_rows(
		[row.as_dict() for row in ipd.stiching_item_combination_details],
		source,
		targets_with_retained,
		operation,
		stitch_side_follows=bool(ipd.is_same_packing_attribute),
		reference_rows=stitch_reference_rows,
		mapping=stitch_mapping,
	)
	ipd.set("stiching_item_combination_details", new_rows)
	diff["stiching_item_combination_details"] = stitch_diff

	# 5. JSON combination structures ----------------------------------------
	for fieldname in JSON_COMBINATION_FIELDS:
		raw = ipd.get(fieldname)
		structure, error = T.parse_json_structure(raw)
		if error:
			conflicts.append({"structure": fieldname, "message": error})
			continue
		if not isinstance(structure, dict):
			continue
		if not T.structure_uses_attribute(structure, ipd.packing_attribute):
			continue
		new_rows = None
		configured_fields = {
			"cutting_items_json": ("Dia", "Weight"),
			"cutting_cloths_json": ("Cloth",),
			"cloth_accessory_json": ("Dia", "Weight"),
		}[fieldname]
		if operation == "add":
			if fieldname == "cloth_accessory_json":
				new_rows = []
				for row in structure.get("items") or []:
					if not isinstance(row, dict) or row.get(ipd.packing_attribute) != add_reference_colour:
						continue
					candidate = copy.deepcopy(row)
					candidate[ipd.packing_attribute] = targets[0]["colour"]
					new_rows.append(candidate)
			elif ipd.enable_panel_wise_consumption_matrix:
				# Panel mode: popup cells are matrix-shaped; derive the flat
				# rows so the previewed standard JSON matches what the save-time
				# sync will regenerate from the transformed matrix.
				continue  # matrices below own the source of truth
			else:
				new_rows = targets[0].get(
					"cutting_rows" if fieldname == "cutting_items_json" else "cloth_rows"
				)
				new_rows = [copy.deepcopy(row) for row in (new_rows or [])]
				for row in new_rows:
					# The server owns the target colour. Do not rely on a custom
					# dialog (or another API client) repeating it in every row.
					row[ipd.packing_attribute] = targets[0]["colour"]
		transformed, structure_diff = T.transform_combination_rows(
			structure,
			ipd.packing_attribute,
			source,
			targets_with_retained,
			operation,
			new_rows=new_rows,
			configured_fields=configured_fields,
		)
		ipd.set(fieldname, T.serialize_like_original(transformed, isinstance(raw, str)))
		diff[fieldname] = structure_diff

	# Stitching accessory JSON (declared names differ from row keys).
	raw = ipd.get("stiching_accessory_json")
	structure, error = T.parse_json_structure(raw)
	if error:
		conflicts.append({"structure": "stiching_accessory_json", "message": error})
	elif isinstance(structure, dict):
		transformed, structure_diff = T.transform_stitching_accessory_structure(
			structure,
			ipd.packing_attribute,
			source,
			targets_with_retained,
			operation,
			accessory_colour_follows=bool(ipd.is_same_packing_attribute),
			reference_colour=add_reference_colour,
		)
		ipd.set(
			"stiching_accessory_json",
			T.serialize_like_original(transformed, isinstance(raw, str)),
		)
		diff["stiching_accessory_json"] = structure_diff

	# 6. Panel-wise compact matrices ----------------------------------------
	if ipd.enable_panel_wise_consumption_matrix:
		for fieldname, transformer in (
			("panel_wise_consumption_matrix_json", T.transform_panel_consumption_matrix),
			("panel_wise_cloth_mapping_json", T.transform_panel_cloth_matrix),
		):
			raw = ipd.get(fieldname)
			matrix, error = T.parse_json_structure(raw)
			if error:
				conflicts.append({"structure": fieldname, "message": error})
				continue
			if not isinstance(matrix, dict):
				continue
			new_cells = None
			if operation == "add":
				key = "cutting_rows" if "consumption" in fieldname else "cloth_rows"
				new_cells = targets[0].get(key) or []
			transformed, matrix_diff = transformer(
				matrix, ipd.packing_attribute, source, targets_with_retained, operation, new_cells=new_cells
			)
			ipd.set(fieldname, T.serialize_like_original(transformed, isinstance(raw, str)))
			diff[fieldname] = matrix_diff

	# 7. BOM attribute mappings ----------------------------------------------
	bom_diff = []
	bom_mapping_docs = []
	for row in ipd.item_bom:
		if not (row.based_on_attribute_mapping and row.attribute_mapping):
			continue
		mapping = frappe.get_doc("Item BOM Attribute Mapping", row.attribute_mapping)
		bom_mapping_docs.append(mapping)
		new_values, mapping_diff = T.transform_bom_mapping_values(
			[row.as_dict() for row in mapping.values],
			ipd.packing_attribute,
			source,
			targets_with_retained,
			operation,
			reference_colour=normalized["reference_colour"],
		)
		mapping.set("values", new_values)
		bom_diff.extend(
			dict(entry, mapping=mapping.name) for entry in mapping_diff
		)
	diff["item_bom_mappings"] = bom_diff

	# 8. Remove the fully-removed source value from the packing mapping ------
	source_fully_removed = operation == "remove" or (
		operation == "split_convert"
		and not any(
			target["colour"] == source
			and any(flt(quantity) > 0 for quantity in target["size_quantities"].values())
			for target in targets
		)
	)
	if mapping_doc is not None and source_fully_removed and not _colour_still_referenced(ipd, source):
		mapping_doc.set(
			"values",
			[row for row in mapping_doc.values if row.attribute_value != source],
		)
		diff["item_attribute_mapping"] = {
			"doctype": "Item Item Attribute Mapping",
			"name": mapping_doc.name,
			"values": [row.attribute_value for row in mapping_doc.values],
		}

	# 9. Approval reset -------------------------------------------------------
	ipd.approval_status = "Not Approved"
	ipd.approved_by = None

	_collect_conflicts(diff, conflicts)
	mapping_docs = []
	if mapping_doc is not None:
		mapping_docs.append(mapping_doc)
	mapping_docs.extend(bom_mapping_docs)
	return diff, mapping_docs


def _collect_conflicts(diff, conflicts):
	for structure, entries in diff.items():
		if structure == "item_attribute_mapping":
			continue
		for entry in entries or []:
			if isinstance(entry, dict) and entry.get("action") == "conflict":
				conflicts.append(
					{
						"structure": structure,
						"colour": entry.get("colour"),
						"combination_key": entry.get("combination_key"),
						"details": entry.get("details"),
					}
				)


# ---------------------------------------------------------------------------
# Lot transformation
# ---------------------------------------------------------------------------


def _resolve_variant(item, attrs, dependent_mapping, create):
	if create:
		return get_or_create_variant(item, attrs, dependent_attr=dependent_mapping)
	return get_variant(item, attrs)


def _target_part_colour(ipd, major_colour, part):
	for row in ipd.set_item_combination_details:
		if row.major_attribute_value == major_colour and row.set_item_attribute_value == part:
			return row.attribute_value
	return major_colour


def _transform_lot_rows(lot, ipd, normalized, create_variants, conflicts):
	operation = normalized["operation"]
	source = normalized["source_colour"]
	targets = normalized["targets"]
	grid, _order = _colour_size_grid(lot, ipd)
	dependent_mapping = ipd.dependent_attribute_mapping

	# Validate allocations against the LIVE rows one more time.
	alloc_errors = []
	if operation == "split_convert":
		alloc_errors = T.validate_size_allocations(
			grid.get(source) or {},
			targets,
			precision=frappe.get_precision("Lot Order Detail", "quantity"),
		)
	_throw_validation_errors(alloc_errors)

	existing_rows = [row.as_dict() for row in lot.lot_order_details]
	new_rows = []
	size_pieces_after = {}
	next_row_index = max(
		[int(row.get("row_index") or 0) for row in existing_rows] or [-1]
	) + 1
	transformed_row_indexes = {}

	def target_row_index(colour, source_row_index):
		nonlocal next_row_index
		key = (colour, int(source_row_index or 0))
		if key not in transformed_row_indexes:
			transformed_row_indexes[key] = next_row_index
			next_row_index += 1
		return transformed_row_indexes[key]

	def count_size_pieces(row_attrs, quantity, is_major=True):
		if not is_major:
			return
		size = row_attrs.get(ipd.primary_item_attribute)
		size_pieces_after[size] = size_pieces_after.get(size, 0) + flt(quantity)
	summary = {
		"removed_rows": 0,
		"cloned_rows": 0,
		"merged_rows": 0,
		"retained_rows": 0,
		"new_variants": [],
		"variants_to_create": [],
	}
	retained_source = operation == "split_convert" and any(
		target["colour"] == source
		and any(flt(quantity) > 0 for quantity in target["size_quantities"].values())
		for target in targets
	)

	def row_key(row):
		set_comb = update_if_string_instance(row.get("set_combination")) or {}
		return (row.get("item_variant"), json.dumps(set_comb, sort_keys=True))

	def append_or_merge(candidate):
		for existing in new_rows:
			if row_key(existing) == row_key(candidate):
				existing["quantity"] = flt(existing.get("quantity")) + flt(candidate.get("quantity"))
				summary["merged_rows"] += 1
				return
		new_rows.append(candidate)
		summary["cloned_rows"] += 1

	for row in existing_rows:
		attrs = get_variant_attr_details(row["item_variant"])
		if ipd.is_set_item:
			set_comb = update_if_string_instance(row.get("set_combination")) or {}
			row_colour = set_comb.get("major_colour")
		else:
			row_colour = attrs.get(ipd.packing_attribute)

		if operation == "add" or row_colour != source:
			new_rows.append(copy.deepcopy(row))
			count_size_pieces(
				attrs,
				row["quantity"],
				not ipd.is_set_item
				or attrs.get(ipd.set_item_attribute) == ipd.major_attribute_value,
			)
			continue

		size = attrs.get(ipd.primary_item_attribute)
		if operation == "remove":
			summary["removed_rows"] += 1
			continue

		# split_convert
		source_qty = flt(row["quantity"])
		allocated = 0
		for target in targets:
			colour = target["colour"]
			quantity = flt(target["size_quantities"].get(size, 0))
			allocated += quantity
			if colour == source:
				if quantity <= 0:
					continue
				retained = copy.deepcopy(row)
				retained["quantity"] = quantity
				new_rows.append(retained)
				count_size_pieces(attrs, quantity, not ipd.is_set_item or attrs.get(ipd.set_item_attribute) == ipd.major_attribute_value)
				summary["retained_rows"] += 1
				continue
			new_attrs = dict(attrs)
			if ipd.is_set_item:
				part = attrs.get(ipd.set_item_attribute)
				new_attrs[ipd.packing_attribute] = _target_part_colour(ipd, colour, part)
				new_set_comb = dict(set_comb)
				new_set_comb["major_colour"] = colour
			else:
				new_attrs[ipd.packing_attribute] = colour
				new_set_comb = {"major_colour": colour}
			variant = _resolve_variant(
				frappe.get_value("Item Variant", row["item_variant"], "item"),
				new_attrs,
				dependent_mapping,
				create_variants,
			)
			if not variant:
				# Preview/probe: the variant will be created during Apply.
				variant = "__new_variant__:" + json.dumps(new_attrs, sort_keys=True)
				summary["variants_to_create"].append(new_attrs)
			else:
				summary["new_variants"].append(variant)
			candidate = copy.deepcopy(row)
			candidate["item_variant"] = variant
			candidate["quantity"] = quantity
			candidate["cut_qty"] = 0
			candidate["stich_qty"] = 0
			candidate["pack_qty"] = 0
			candidate["set_combination"] = new_set_comb
			candidate["row_index"] = target_row_index(colour, row.get("row_index"))
			count_size_pieces(new_attrs, quantity, not ipd.is_set_item or new_attrs.get(ipd.set_item_attribute) == ipd.major_attribute_value)
			append_or_merge(candidate)
		if not retained_source:
			summary["removed_rows"] += 1

	if operation == "add":
		target = targets[0]
		colour = target["colour"]
		# Seed the new colour's rows from the reference colour (or any colour)
		# so dependent attributes / stage / part shapes are preserved exactly.
		seed_colour = normalized["reference_colour"] or (
			grid and next(iter(grid))
		)
		seed_rows = []
		for row in existing_rows:
			attrs = get_variant_attr_details(row["item_variant"])
			if ipd.is_set_item:
				set_comb = update_if_string_instance(row.get("set_combination")) or {}
				row_colour = set_comb.get("major_colour")
			else:
				row_colour = attrs.get(ipd.packing_attribute)
			if row_colour == seed_colour:
				seed_rows.append(row)
		if not seed_rows:
			conflicts.append(
				{
					"structure": "lot_order_details",
					"message": _("No existing colour rows found to derive the new colour's variants."),
				}
			)
		for row in seed_rows:
			attrs = get_variant_attr_details(row["item_variant"])
			size = attrs.get(ipd.primary_item_attribute)
			quantity = flt(target["size_quantities"].get(size, 0))
			if quantity <= 0:
				continue
			new_attrs = dict(attrs)
			if ipd.is_set_item:
				part = attrs.get(ipd.set_item_attribute)
				new_attrs[ipd.packing_attribute] = _target_part_colour(ipd, colour, part)
				new_set_comb = dict(update_if_string_instance(row.get("set_combination")) or {})
				new_set_comb["major_colour"] = colour
			else:
				new_attrs[ipd.packing_attribute] = colour
				new_set_comb = {"major_colour": colour}
			variant = _resolve_variant(
				frappe.get_value("Item Variant", row["item_variant"], "item"),
				new_attrs,
				dependent_mapping,
				create_variants,
			)
			if not variant:
				variant = "__new_variant__:" + json.dumps(new_attrs, sort_keys=True)
				summary["variants_to_create"].append(new_attrs)
			else:
				summary["new_variants"].append(variant)
			candidate = copy.deepcopy(row)
			candidate["item_variant"] = variant
			candidate["quantity"] = quantity
			candidate["cut_qty"] = 0
			candidate["stich_qty"] = 0
			candidate["pack_qty"] = 0
			candidate["set_combination"] = new_set_comb
			candidate["row_index"] = target_row_index(colour, row.get("row_index"))
			count_size_pieces(new_attrs, quantity, not ipd.is_set_item or new_attrs.get(ipd.set_item_attribute) == ipd.major_attribute_value)
			append_or_merge(candidate)

	# Drop identity so Frappe treats reshaped rows as fresh children where
	# needed, but keep user-entered fields on every surviving row.
	for idx, row in enumerate(new_rows, start=1):
		row.pop("name", None)
		row["idx"] = idx
		if isinstance(row.get("item_variant"), str) and row["item_variant"].startswith("__new_variant__:"):
			row["item_variant"] = None

	lot.set("lot_order_details", new_rows)
	lot.total_order_quantity = sum(flt(row.get("quantity")) for row in new_rows)
	summary["size_pieces_after"] = size_pieces_after
	return summary


def _recompute_items_from_details(lot, ipd, size_wise_pieces=None):
	"""Mirror Lot.derive_items_from_order_details without rebuilding rows."""
	if not lot.items:
		return
	combo = flt(ipd.packing_combo)
	if not combo:
		frappe.throw(
			_("Packing Combo is not set in Item Production Detail {0}.").format(ipd.name)
		)
	if size_wise_pieces is None:
		size_wise_pieces = _size_piece_totals(lot, ipd)
	missing = []
	for item in lot.items:
		attrs = get_variant_attr_details(item.item_variant)
		size = attrs.get(ipd.primary_item_attribute)
		pieces = size_wise_pieces.pop(size, 0)
		item.qty = math.ceil(flt(pieces) / combo)
	for size, pieces in size_wise_pieces.items():
		if pieces > 0:
			missing.append(size)
	if missing:
		frappe.throw(
			_("Order details have quantity for sizes {0} without an order item row.").format(
				", ".join(missing)
			)
		)
	lot.total_quantity = sum(flt(item.qty) for item in lot.items)


def _size_piece_totals(lot, ipd):
	totals = {}
	for row in lot.lot_order_details:
		attrs = get_variant_attr_details(row.item_variant)
		if ipd.is_set_item and attrs.get(ipd.set_item_attribute) != ipd.major_attribute_value:
			continue
		size = attrs.get(ipd.primary_item_attribute)
		totals[size] = totals.get(size, 0) + flt(row.quantity)
	return totals


def _transform_lot(lot, ipd, normalized, create_variants, conflicts):
	before_total = flt(lot.total_order_quantity)
	before_size_totals = _size_piece_totals(lot, ipd)
	row_summary = _transform_lot_rows(lot, ipd, normalized, create_variants, conflicts)
	after_size_totals = row_summary.pop("size_pieces_after", None)
	if after_size_totals is not None and before_size_totals != after_size_totals:
		# Add/Remove changed the per-size piece counts; keep the colour-
		# independent order items and PPO allocation consistent using the
		# app's existing reverse derivation. A split leaves size totals
		# unchanged, so user-entered item quantities are preserved exactly.
		_recompute_items_from_details(lot, ipd, after_size_totals)
	after_total = sum(flt(row.quantity) for row in lot.lot_order_details)

	# Never present a stale cached grid/BOM after a colour change.
	lot.lot_order_details_json = None
	lot.set("bom_summary", [])
	lot.bom_summary_json = None
	lot.last_calculated_time = None

	return {
		"rows": row_summary,
		"before_total_order_quantity": before_total,
		"after_total_order_quantity": after_total,
		"total_quantity": flt(lot.total_quantity),
	}


# ---------------------------------------------------------------------------
# Process Cost transformation
# ---------------------------------------------------------------------------


def _transform_process_costs(lot, ipd, normalized, conflicts):
	"""Compute Process Cost changes WITHOUT mutating cached documents."""
	operation = normalized["operation"]
	source = normalized["source_colour"]
	targets = _targets_for_transform(normalized)
	changes = []
	new_values_by_colour = normalized["process_cost_values"] or {}

	for pc in _relevant_process_costs(lot.name, ipd.packing_attribute):
		before = _process_cost_values(pc.name)
		new_values = None
		if operation == "add":
			colour = normalized["targets"][0]["colour"]
			reference_value = next(
				(row for row in before if row.attribute_value == normalized["reference_colour"]),
				None,
			)
			adjusted = new_values_by_colour.get(pc.name) or new_values_by_colour.get(colour) or {}
			new_values = [
				{
					"attribute_value": colour,
					"price": flt(adjusted.get("price", reference_value.price if reference_value else 0)),
					"min_order_qty": flt(
						adjusted.get("min_order_qty", reference_value.min_order_qty if reference_value else 0)
					),
				}
			]
		new_rows, process_cost_diff = T.transform_process_cost_values(
			[dict(row) for row in before], source, targets, operation, new_values=new_values
		)
		_collect_conflicts(
			{"Process Cost {0}".format(pc.name): process_cost_diff}, conflicts
		)
		changes.append(
			{
				"name": pc.name,
				"docstatus": pc.docstatus,
				"process_name": pc.process_name,
				"before": [
					{
						"attribute_value": row.get("attribute_value"),
						"price": row.get("price"),
						"min_order_qty": row.get("min_order_qty"),
					}
					for row in before
				],
				"after": [
					{
						"attribute_value": row.get("attribute_value"),
						"price": row.get("price"),
						"min_order_qty": row.get("min_order_qty"),
					}
					for row in new_rows
				],
			}
		)
	return changes


def _apply_process_cost_changes(changes):
	links = []
	for change in changes:
		if change["docstatus"] == 0:
			doc = frappe.get_doc("Process Cost", change["name"])
			if not frappe.has_permission("Process Cost", ptype="write", doc=doc):
				frappe.throw(
					_("You need write permission on Process Cost {0}.").format(doc.name),
					frappe.PermissionError,
				)
			doc.set("process_cost_values", change["after"])
			doc.save()
			links.append(doc.name)
		else:
			source = frappe.get_doc("Process Cost", change["name"])
			if not frappe.has_permission("Process Cost", ptype="create"):
				frappe.throw(
					_("You need create permission for Process Cost replacements."),
					frappe.PermissionError,
				)
			# Draft replacement/version; the submitted source stays untouched.
			# amended_from is only for real amendments of cancelled docs.
			new_doc = frappe.copy_doc(source)
			new_doc.docstatus = 0
			# A workflow (e.g. Process Cost approval) must start again from its
			# initial state; copying the submitted state would fail validation.
			new_doc.workflow_state = None
			new_doc.approved_by = None
			new_doc.set("process_cost_values", change["after"])
			new_doc.insert()
			links.append(new_doc.name)
	return links


# ---------------------------------------------------------------------------
# Preview / Apply
# ---------------------------------------------------------------------------


def _prepare(lot_name, payload):
	lot, ipd = _get_lot_and_ipd(lot_name)
	_require_lot_write_permission(lot)
	normalized, errors = T.normalize_payload(_parse_payload(payload))
	_throw_validation_errors(errors)
	return lot, ipd, normalized


def _check_stale(lot, ipd, expected_lot_modified, expected_ipd_modified):
	stale = []
	if expected_lot_modified and str(lot.modified) != str(expected_lot_modified):
		stale.append("Lot")
	if expected_ipd_modified and str(ipd.modified) != str(expected_ipd_modified):
		stale.append("Item Production Detail")
	if stale:
		frappe.throw(
			_("{0} changed while the colour update dialog was open. Reload the form and try again.").format(
				", ".join(stale)
			),
			frappe.ValidationError,
		)


@frappe.whitelist()
def preview_colour_update(lot, payload, expected_lot_modified=None, expected_ipd_modified=None):
	lot_doc, ipd_doc, normalized = _prepare(lot, payload)
	_check_stale(lot_doc, ipd_doc, expected_lot_modified, expected_ipd_modified)

	source = normalized["source_colour"]
	blockers, has_blockers = find_colour_update_blockers(lot, source)
	if has_blockers:
		return {"ok": False, "blockers": blockers, "errors": []}

	grid, _order = _colour_size_grid(lot_doc, ipd_doc)
	errors = _validate_payload_against_ipd(ipd_doc, normalized, grid, lot)
	if errors:
		return {"ok": False, "blockers": blockers, "errors": errors}

	lot_copy = frappe.copy_doc(lot_doc)
	ipd_copy = frappe.copy_doc(ipd_doc)
	conflicts = []
	ipd_diff, _mapping_docs = _transform_ipd(ipd_copy, normalized, conflicts)
	lot_summary = _transform_lot(lot_copy, ipd_copy, normalized, create_variants=False, conflicts=conflicts)
	process_costs = _transform_process_costs(lot_copy, ipd_copy, normalized, conflicts)
	manual_follow_up = [
		_("The IPD will be reset to Not Approved; approve it after reviewing the change."),
		_("The cached BOM summary was cleared; review the IPD and click Calculate BOM."),
	]
	if normalized["operation"] == "add" and _colour_dependent_accessory_structures(ipd_doc):
		manual_follow_up.insert(
			1,
			_(
				"Accessory combinations are copied from the selected Reference Colour; review them before approving the IPD."
			),
		)

	return {
		"ok": not conflicts,
		"errors": [],
		"blockers": blockers,
		"conflicts": conflicts,
		"shared_ipd": {
			"is_shared": _is_shared_ipd(ipd_doc.name, lot),
			"linked_lots": _get_linked_lots(ipd_doc.name, lot),
		},
		"ipd_diff": ipd_diff,
		"lot_summary": lot_summary,
		"process_costs": process_costs,
		"manual_follow_up": manual_follow_up,
	}


def _lock_documents(lot_name, ipd_name, ipd):
	frappe.db.get_value("Lot", lot_name, "name", for_update=True)
	frappe.db.get_value("Item Production Detail", ipd_name, "name", for_update=True)
	lock_names = set()
	mapping_doc = _get_packing_mapping_doc(ipd)
	if mapping_doc:
		lock_names.add(("Item Item Attribute Mapping", mapping_doc.name))
	for row in ipd.item_bom:
		if row.based_on_attribute_mapping and row.attribute_mapping:
			lock_names.add(("Item BOM Attribute Mapping", row.attribute_mapping))
	for doctype, name in sorted(lock_names):
		frappe.db.get_value(doctype, name, "name", for_update=True)
	for pc in _relevant_process_costs(lot_name, ipd.packing_attribute):
		frappe.db.get_value("Process Cost", pc.name, "name", for_update=True)


def _save_mapping_docs(mapping_docs):
	for doc in mapping_docs:
		doc.save()


def _audit_summary(operation, normalized, lot_summary, old_ipd, new_ipd, process_cost_links):
	# Timeline comments render as HTML; escape every user-controlled value.
	targets = ", ".join(html.escape(str(t["colour"])) for t in normalized["targets"]) or "-"
	source = html.escape(str(normalized["source_colour"] or "-"))
	return "\n".join(
		[
			"Update Colour applied",
			"Operation: {0}".format(operation),
			"Source colour: {0}".format(source),
			"Target colour(s): {0}".format(targets),
			"Order quantity: {0} -> {1}".format(
				T.fmt_qty(lot_summary["before_total_order_quantity"]),
				T.fmt_qty(lot_summary["after_total_order_quantity"]),
			),
			"IPD: {0} -> {1}".format(old_ipd, new_ipd),
			"Process Cost documents: {0}".format(", ".join(process_cost_links) or "-"),
			"User: {0}".format(html.escape(str(frappe.session.user))),
		]
	)


@frappe.whitelist()
def apply_colour_update(
	lot,
	payload,
	expected_lot_modified=None,
	expected_ipd_modified=None,
	confirmed_shared_ipd=False,
):
	lot_doc, ipd_doc, normalized = _prepare(lot, payload)

	# Lock in deterministic order, then re-load and re-check staleness under lock.
	_lock_documents(lot, ipd_doc.name, ipd_doc)
	lot_doc, ipd_doc = _get_lot_and_ipd(lot)
	_check_stale(lot_doc, ipd_doc, expected_lot_modified, expected_ipd_modified)

	blockers, has_blockers = find_colour_update_blockers(lot, normalized["source_colour"])
	_throw_blockers(blockers)

	grid, _order = _colour_size_grid(lot_doc, ipd_doc)
	_throw_validation_errors(_validate_payload_against_ipd(ipd_doc, normalized, grid, lot))
	_require_ipd_write_permission(ipd_doc)

	shared = _is_shared_ipd(ipd_doc.name, lot)
	if shared and not _truthy(confirmed_shared_ipd):
		frappe.throw(
			_(
				"This IPD is shared by other Lots ({0}). Confirm the duplication to create a private copy for this Lot."
			).format(", ".join(_get_linked_lots(ipd_doc.name, lot))),
			frappe.ValidationError,
		)

	old_ipd_name = ipd_doc.name
	if shared:
		ipd = build_ipd_duplicate(ipd_doc)
		lot_doc.production_detail = ipd.name
	else:
		_ensure_private_mappings(ipd_doc)
		ipd = ipd_doc

	# Transform on copies first so conflicts can never leave partial writes.
	ipd_probe = frappe.copy_doc(ipd)
	lot_probe = frappe.copy_doc(lot_doc)
	conflicts = []
	_transform_ipd(ipd_probe, normalized, conflicts)
	_transform_lot(lot_probe, ipd_probe, normalized, create_variants=False, conflicts=conflicts)
	_transform_process_costs(lot_probe, ipd_probe, normalized, conflicts)
	if conflicts:
		_throw_validation_errors(
			[_format_conflict(conflict) for conflict in conflicts]
		)

	# Real transformation (creates missing variants inside the transaction).
	ipd_diff, mapping_docs = _transform_ipd(ipd, normalized, [])
	lot_summary = _transform_lot(lot_doc, ipd, normalized, create_variants=True, conflicts=[])
	process_cost_changes = _transform_process_costs(lot_doc, ipd, normalized, [])

	# Mapping docs MUST be saved before the IPD: packing_tab_validations reads
	# the packing attribute mapping from the DB during ipd.save() and requires
	# len(mapping.values) >= packing_attribute_no. The transformed mapping only
	# exists in memory until it is saved, so saving the IPD first failed with
	# "The Packing attribute no is X But there is only Y attributes are
	# available" whenever the mapping did not already contain every target
	# colour. Both saves stay inside the same transaction, so the SD/YRP
	# guarantee is unchanged: the final IPD save still clears
	# skip_sd_yrp_sync (shared path) and SD/YRP only ever sees the complete
	# transformed document.
	_save_mapping_docs(mapping_docs)
	ipd.flags.skip_sd_yrp_sync = False
	ipd.save()

	process_cost_links = _apply_process_cost_changes(process_cost_changes)

	lot_doc.save()

	lot_doc.add_comment(
		"Comment",
		_audit_summary(normalized["operation"], normalized, lot_summary, old_ipd_name, ipd.name, process_cost_links),
	)

	return {
		"ok": True,
		"lot": lot_doc.name,
		"ipd": ipd.name,
		"duplicated_ipd": shared,
		"old_ipd": old_ipd_name,
		"lot_summary": lot_summary,
		"process_costs": process_cost_links,
		"ipd_diff": ipd_diff,
		"message": _(
			"Colour update applied. The IPD is Not Approved and must be reviewed and approved."
		),
	}


def _format_conflict(conflict):
	structure = str(conflict.get("structure") or "?")
	colour = str(conflict.get("colour") or "-")
	key = str(conflict.get("combination_key") or "-")
	details = str(conflict.get("details") or conflict.get("message") or "")
	return _("Conflict in {0} for colour {1} ({2}): {3}").format(structure, colour, key, details)
