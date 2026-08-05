# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

COMPACTING_KEY_FIELDS = (
	"cloth_item",
	"packing_attribute_value",
	"input_dia",
)


def _as_json(value):
	if isinstance(value, str):
		return json.loads(value) if value else {}
	return value or {}


def compacting_key(row):
	return tuple(row.get(fieldname) for fieldname in COMPACTING_KEY_FIELDS)


def _format_key(key):
	return " / ".join(str(value or _("Not Set")) for value in key)


def _cloth_item_by_label(ipd_doc):
	cloth_items = {}
	for row in ipd_doc.get("cloth_detail") or []:
		label = row.get("name1")
		cloth_item = row.get("cloth")
		if not label or not cloth_item:
			continue
		if label in cloth_items and cloth_items[label] != cloth_item:
			frappe.throw(
				_("Cloth label {0} points to more than one Cloth Item in IPD {1}.").format(
					label, ipd_doc.name
				)
			)
		cloth_items[label] = cloth_item
	return cloth_items


def _attribute_key(row, attributes):
	return tuple(row.get(attribute) for attribute in attributes)


def _append_compacting_detail(combinations, cloth_item, packing_value, input_dia):
	detail = {
		"cloth_item": cloth_item,
		"packing_attribute_value": packing_value,
		"input_dia": input_dia,
	}
	combinations[compacting_key(detail)] = detail


def _append_accessory_compacting_details(ipd_doc, cloth_items, combinations):
	accessory_items = _as_json(ipd_doc.get("cloth_accessory_json")).get("items") or []
	if not accessory_items:
		return

	accessory_mappings = (
		_as_json(ipd_doc.get("stiching_accessory_json")).get("items") or []
	)
	if not accessory_mappings:
		frappe.throw(
			_("Configure and save the Cloth Accessory colour mapping first.")
		)

	set_attribute = ipd_doc.get("set_item_attribute") if ipd_doc.get("is_set_item") else None
	default_cloth_by_accessory = _as_json(
		ipd_doc.get("accessory_clothtype_json")
	)
	mappings_by_accessory = {}
	for mapping in accessory_mappings:
		accessory = mapping.get("accessory") or mapping.get("Accessory")
		if accessory:
			mappings_by_accessory.setdefault(accessory, []).append(mapping)

	for accessory_row in accessory_items:
		accessory = accessory_row.get("Accessory") or accessory_row.get("accessory")
		input_dia = accessory_row.get("Dia") or accessory_row.get("dia")
		if not accessory or not input_dia:
			frappe.throw(_("Accessory and Dia are required for every Cloth Accessory row."))

		matched = False
		for mapping in mappings_by_accessory.get(accessory, []):
			if set_attribute:
				accessory_part = accessory_row.get(set_attribute)
				mapping_part = mapping.get(set_attribute)
				if accessory_part and mapping_part and accessory_part != mapping_part:
					continue

			cloth_label = mapping.get("cloth_type") or mapping.get("Cloth")
			if not cloth_label and not ipd_doc.get("is_set_item"):
				cloth_label = default_cloth_by_accessory.get(accessory)
			packing_value = (
				mapping.get("accessory_colour")
				or mapping.get("Accessory Colour")
				or mapping.get(ipd_doc.get("packing_attribute"))
				or mapping.get("major_colour")
				or mapping.get("Major Colour")
			)
			if not cloth_label or not packing_value:
				frappe.throw(
					_("Complete the Cloth and Accessory Colour mapping for accessory {0}.").format(
						accessory
					)
				)
			cloth_item = cloth_items.get(cloth_label)
			if not cloth_item:
				frappe.throw(
					_("Accessory cloth label {0} has no matching Cloth Detail row in IPD {1}.").format(
						cloth_label, ipd_doc.name
					)
				)
			_append_compacting_detail(
				combinations, cloth_item, packing_value, input_dia
			)
			matched = True

		if not matched:
			frappe.throw(
				_("No Cloth Accessory colour mapping was found for accessory {0}.").format(
					accessory
				)
			)


def get_expected_compacting_details(ipd_doc):
	"""Resolve unique Cloth Item + Packing Value + Input Dia routes from an IPD."""
	if not ipd_doc.get("enable_panel_wise_consumption_matrix"):
		return []

	packing_attribute = ipd_doc.get("packing_attribute")
	if not packing_attribute:
		frappe.throw(_("Select the Packing Attribute before entering Compacting Details."))

	cloth_attributes = [
		row.get("attribute") for row in ipd_doc.get("cloth_attributes") or []
		if row.get("attribute")
	]
	if not cloth_attributes:
		frappe.throw(_("Configure the Cloth Mapping attributes before entering Compacting Details."))

	cutting_items = _as_json(ipd_doc.get("cutting_items_json")).get("items") or []
	cutting_cloths = _as_json(ipd_doc.get("cutting_cloths_json")).get("items") or []
	if not cutting_items:
		frappe.throw(_("Save the Panel-wise Consumption Matrix before entering Compacting Details."))
	if not cutting_cloths:
		frappe.throw(_("Configure and save the Cutting Cloth mapping first."))

	cloth_items = _cloth_item_by_label(ipd_doc)
	cloth_by_attributes = {}
	for row in cutting_cloths:
		key = _attribute_key(row, cloth_attributes)
		cloth_label = row.get("Cloth")
		if not cloth_label:
			frappe.throw(
				_("Select Cloth for Cloth Mapping combination {0}.").format(
					_format_key(key)
				)
			)
		cloth_item = cloth_items.get(cloth_label)
		if not cloth_item:
			frappe.throw(
				_("Cloth label {0} has no matching Cloth Detail row in IPD {1}.").format(
					cloth_label, ipd_doc.name
				)
			)
		if key in cloth_by_attributes and cloth_by_attributes[key] != cloth_item:
			frappe.throw(
				_("Cloth Mapping combination {0} points to more than one Cloth Item.").format(
					_format_key(key)
				)
			)
		cloth_by_attributes[key] = cloth_item

	combinations = {}
	for row in cutting_items:
		cloth_key = _attribute_key(row, cloth_attributes)
		cloth_item = cloth_by_attributes.get(cloth_key)
		if not cloth_item:
			frappe.throw(
				_("No Cutting Cloth mapping matches consumption combination {0}.").format(
					_format_key(cloth_key)
				)
			)
		packing_value = row.get(packing_attribute)
		input_dia = row.get("Dia")
		if not packing_value or not input_dia:
			frappe.throw(
				_("Packing Attribute value and Dia are required for every panel-wise consumption row.")
			)
		_append_compacting_detail(
			combinations, cloth_item, packing_value, input_dia
		)

	_append_accessory_compacting_details(ipd_doc, cloth_items, combinations)

	return [combinations[key] for key in sorted(combinations)]


def merge_compacting_details(expected, saved):
	saved_by_key = {compacting_key(row): row for row in saved or []}
	return [
		{
			**detail,
			"compacting_dia": (
				saved_by_key.get(compacting_key(detail), {}).get("compacting_dia") or None
			),
		}
		for detail in expected
	]


def _validate_dia_values(rows):
	dias = {
		value
		for row in rows
		for value in (row.get("input_dia"), row.get("compacting_dia"))
		if value
	}
	if not dias:
		return
	valid_dias = set(
		frappe.get_all(
			"Item Attribute Value",
			filters={"attribute_name": "Dia", "name": ["in", sorted(dias)]},
			pluck="name",
		)
	)
	invalid = sorted(dias - valid_dias)
	if invalid:
		frappe.throw(_("Invalid Dia value(s): {0}.").format(", ".join(invalid)))


def validate_submitted_details(expected, submitted):
	expected_by_key = {compacting_key(row): row for row in expected}
	normalized = []
	seen = set()
	for row in submitted or []:
		row = frappe._dict(row)
		key = compacting_key(row)
		if any(not value for value in key):
			frappe.throw(_("Cloth Item, Packing Attribute Value and Input Dia are required."))
		if key in seen:
			frappe.throw(_("Duplicate Compacting Details combination: {0}.").format(_format_key(key)))
		if key not in expected_by_key:
			frappe.throw(
				_("Compacting Details combination no longer belongs to this IPD: {0}.").format(
					_format_key(key)
				)
			)
		seen.add(key)
		normalized.append(
			{
				**expected_by_key[key],
				"compacting_dia": row.get("compacting_dia") or None,
			}
		)

	for key, detail in expected_by_key.items():
		if key not in seen:
			normalized.append({**detail, "compacting_dia": None})

	normalized.sort(key=compacting_key)
	_validate_dia_values(normalized)
	return normalized


def get_ipd_compacting(item_production_detail):
	name = frappe.db.exists(
		"IPD Compacting", {"item_production_detail": item_production_detail}
	)
	return frappe.get_doc("IPD Compacting", name) if name else None


def get_compacting_mapping(item_production_detail):
	doc = get_ipd_compacting(item_production_detail)
	if not doc:
		return {}
	return {
		compacting_key(row): row.get("compacting_dia")
		for row in doc.get("compacting_details") or []
	}


def _context(ipd_doc):
	expected = get_expected_compacting_details(ipd_doc)
	compacting = get_ipd_compacting(ipd_doc.name)
	rows = merge_compacting_details(
		expected, compacting.get("compacting_details") if compacting else []
	)
	return {
		"item_production_detail": ipd_doc.name,
		"packing_attribute": ipd_doc.get("packing_attribute"),
		"rows": rows,
		"modified": str(compacting.modified) if compacting else None,
		"can_write": bool(ipd_doc.has_permission("write")),
	}


@frappe.whitelist()
def get_compacting_details(item_production_detail):
	ipd_doc = frappe.get_doc("Item Production Detail", item_production_detail)
	ipd_doc.check_permission("read")
	return _context(ipd_doc)


@frappe.whitelist()
def save_compacting_details(item_production_detail, rows, expected_modified=None):
	ipd_doc = frappe.get_doc("Item Production Detail", item_production_detail)
	ipd_doc.check_permission("write")
	if not ipd_doc.get("enable_panel_wise_consumption_matrix"):
		frappe.throw(_("Enable Panel-wise Consumption Matrix before saving Compacting Details."))

	expected = get_expected_compacting_details(ipd_doc)
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	normalized = validate_submitted_details(expected, rows or [])
	compacting = get_ipd_compacting(ipd_doc.name)
	if compacting and expected_modified and str(compacting.modified) != str(expected_modified):
		frappe.throw(
			_("Compacting Details changed after you opened this tab. Reload and try again."),
			frappe.TimestampMismatchError,
		)
	if not compacting:
		compacting = frappe.new_doc("IPD Compacting")
		compacting.item_production_detail = ipd_doc.name

	compacting.packing_attribute = ipd_doc.packing_attribute
	compacting.set("compacting_details", normalized)
	compacting.flags.ignore_permissions = True
	compacting.save()
	return _context(ipd_doc)


class IPDCompacting(Document):
	def validate(self):
		ipd_doc = frappe.get_cached_doc(
			"Item Production Detail", self.item_production_detail
		)
		self.packing_attribute = ipd_doc.packing_attribute
		seen = set()
		for row in self.get("compacting_details") or []:
			key = compacting_key(row)
			if key in seen:
				frappe.throw(
					_("Duplicate Compacting Details combination: {0}.").format(
						_format_key(key)
					)
				)
			seen.add(key)
