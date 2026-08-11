# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

"""Knitting-program preview for a Lot.

The calculation deliberately uses only the Lot's garment IPD and order
quantities. It stores the selected Cloth Excess Percentage and manual program
weight additions on the Lot, but does not create cloth IPDs, Item Variants,
process matrices, or Lot child rows. The yarn-to-cloth yield is fixed at 1.0
until a persisted cloth-production workflow is introduced on this bench.
"""

import math
import re

import frappe
from frappe import _
from frappe.utils import flt

from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
	calculate_cloth,
	get_cloth_combination,
	get_stitching_combination,
)
from production_api.essdee_production.doctype.ipd_compacting.ipd_compacting import (
	compacting_key,
	get_compacting_mapping,
)


CLOTH_PER_KG_YARN = 1.0
WEIGHT_PRECISION = 3
CLOTH_PROGRAM_ADDITION_VERSION = 1


def _validate_extra_percentage(extra_percentage):
	extra_percentage = flt(extra_percentage)
	if extra_percentage < 0:
		frappe.throw(_("Extra Percentage cannot be negative."))
	return extra_percentage


def _cloth_item_by_label(ipd_doc):
	"""Return the garment IPD's cloth-label -> cloth-Item mapping."""
	result = {}
	for row in ipd_doc.get("cloth_detail") or []:
		label = row.get("name1")
		cloth_item = row.get("cloth")
		if not label or not cloth_item:
			continue
		if label in result and result[label] != cloth_item:
			frappe.throw(
				_(
					"Cloth label {0} points to more than one Cloth Item in garment IPD {1}."
				).format(label, ipd_doc.name)
			)
		result[label] = cloth_item
	return result


def _variant_attributes(item_variant):
	variant_doc = frappe.get_cached_doc("Item Variant", item_variant)
	return {
		row.attribute: row.attribute_value
		for row in variant_doc.get("attributes") or []
	}


def _apply_compacting_details(ipd_doc, rows):
	if not ipd_doc.get("enable_panel_wise_consumption_matrix"):
		return False

	mapping = get_compacting_mapping(ipd_doc.name)
	uses_compacting_details = False
	for row in rows:
		key = compacting_key(
			{
				"cloth_item": row["cloth_item"],
				"packing_attribute_value": row["colour"],
				"input_dia": row["dia"],
			}
		)
		compacting_dia = mapping.get(key)
		if not compacting_dia:
			continue
		row["input_dia"] = row["dia"]
		row["compacting_dia"] = compacting_dia
		uses_compacting_details = True

	# Compacting is optional for this preview. When a matching value exists it is
	# shown beside the input Dia; otherwise the cutting Dia remains sufficient.
	return uses_compacting_details


def _calculate_cloth_program(lot_doc, ipd_doc, extra_percentage=0, additions=None):
	"""Calculate preview rows without mutating either supplied document."""
	extra_percentage = _validate_extra_percentage(extra_percentage)
	if not lot_doc.get("lot_order_details"):
		frappe.throw(
			_("This Lot has no order quantities. Run 'Calculate Order Items' first.")
		)

	cloth_items = _cloth_item_by_label(ipd_doc)
	if not cloth_items:
		frappe.throw(
			_("Garment IPD {0} has no Cloth Detail rows.").format(ipd_doc.name)
		)

	cloth_combination = get_cloth_combination(ipd_doc)
	stitching_combination = get_stitching_combination(ipd_doc)
	weights = {}
	unmapped_labels = set()

	for order_row in lot_doc.get("lot_order_details") or []:
		quantity = flt(order_row.get("quantity"))
		if quantity <= 0:
			continue
		item_variant = order_row.get("item_variant")
		if not item_variant:
			continue

		attributes = _variant_attributes(item_variant)
		dependent_attribute = ipd_doc.get("dependent_attribute")
		if dependent_attribute and attributes.get(dependent_attribute):
			attributes.pop(dependent_attribute)

		for cloth in calculate_cloth(
			ipd_doc,
			attributes,
			quantity,
			cloth_combination,
			stitching_combination,
		):
			cloth_label = cloth.get("cloth_type")
			cloth_item = cloth_items.get(cloth_label)
			if not cloth_item:
				unmapped_labels.add(cloth_label or _("Unnamed Cloth"))
				continue
			weight = flt(cloth.get("quantity"))
			if weight <= 0:
				continue
			requirement_type = (
				"accessory" if cloth.get("type") == "accessory" else "cloth"
			)
			accessory_name = (
				cloth.get("accessory_name") or ""
				if requirement_type == "accessory"
				else ""
			)
			key = (
				cloth_item,
				requirement_type,
				accessory_name,
				cloth.get("colour") or "",
				cloth.get("dia") or "",
			)
			weights[key] = weights.get(key, 0.0) + weight

	if unmapped_labels:
		frappe.throw(
			_(
				"Cloth label(s) {0} have no matching Cloth Detail row in garment IPD {1}."
			).format(", ".join(sorted(unmapped_labels)), ipd_doc.name)
		)
	if not weights:
		frappe.throw(
			_(
				"No cloth requirement could be calculated for this Lot. Check its order "
				"quantities and garment IPD cutting combinations."
			)
		)

	multiplier = 1 + (extra_percentage / 100.0)
	rows = []
	ordered_weights = sorted(
		weights.items(),
		key=lambda item: (
			item[0][0],
			item[0][1] != "cloth",
			item[0][2],
			item[0][3],
			item[0][4],
		),
	)
	for (
		cloth_item,
		requirement_type,
		accessory_name,
		colour,
		dia,
	), raw_weight in ordered_weights:
		required_weight = flt(raw_weight, WEIGHT_PRECISION)
		extra_weight = flt(raw_weight * extra_percentage / 100.0, WEIGHT_PRECISION)
		program_weight = flt(
			raw_weight * multiplier / CLOTH_PER_KG_YARN,
			WEIGHT_PRECISION,
		)
		rows.append(
			{
				"cloth_item": cloth_item,
				"requirement_type": requirement_type,
				"accessory_name": accessory_name or None,
				"colour": colour or None,
				"dia": dia or None,
				"required_weight": required_weight,
				"extra_weight": extra_weight,
				"program_weight": program_weight,
			}
		)

	uses_compacting_details = _apply_compacting_details(ipd_doc, rows)
	normalized_additions, route_additions = _apply_cloth_program_additions(
		rows, additions
	)
	totals = {
		"required_weight": sum(flt(row.get("required_weight")) for row in rows),
		"extra_weight": sum(flt(row.get("extra_weight")) for row in rows),
		"manual_additional_weight": sum(
			flt(row.get("manual_additional_weight")) for row in rows
		),
		"program_weight": sum(flt(row.get("program_weight")) for row in rows),
	}
	for key in totals:
		totals[key] = flt(totals[key], WEIGHT_PRECISION)

	return {
		"lot": lot_doc.name,
		"extra_percentage": extra_percentage,
		"cloth_per_kg_yarn": CLOTH_PER_KG_YARN,
		"uses_compacting_details": uses_compacting_details,
		"rows": rows,
		"totals": totals,
		"additions": normalized_additions,
		"addition_routes": route_additions,
	}


def _round_display_weight(value):
	"""Match the whole-kilogram rounding used by the cloth-program dialog."""
	value = flt(value)
	floor = math.floor(value)
	return math.ceil(value) if value - floor > 0.5 else floor


def _parse_cloth_program_additions(value):
	"""Return the user-entered fabric/colour total additions from stored JSON."""
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except (TypeError, ValueError):
			frappe.throw(_("Saved Cloth Program Additions are not valid JSON."))
	if isinstance(value, dict):
		value = value.get("totals") or []
	if not isinstance(value, list):
		frappe.throw(_("Cloth Program Additions must be a list of rows."))
	return value


def _addition_group_key(row):
	requirement_type = (
		"accessory" if row.get("requirement_type") == "accessory" else "cloth"
	)
	return (
		row.get("cloth_item") or "",
		requirement_type,
		(row.get("accessory_name") or "") if requirement_type == "accessory" else "",
		row.get("colour") or "",
	)


def _allocate_added_weight(total_weight, eligible_rows):
	"""Proportionally allocate whole kg while preserving the exact entered total."""
	total_weight = int(total_weight)
	base_total = sum(base_weight for _index, base_weight in eligible_rows)
	if total_weight <= 0 or base_total <= 0:
		return {}

	shares = []
	allocated = {}
	for position, (row_index, base_weight) in enumerate(eligible_rows):
		exact_share = total_weight * base_weight / base_total
		whole_share = math.floor(exact_share)
		allocated[row_index] = whole_share
		shares.append((exact_share - whole_share, base_weight, -position, row_index))

	remainder = total_weight - sum(allocated.values())
	for _fraction, _base_weight, _position, row_index in sorted(
		shares, reverse=True
	)[:remainder]:
		allocated[row_index] += 1
	return allocated


def _apply_cloth_program_additions(rows, additions):
	"""Apply fabric/colour total additions only to their non-zero Dia rows.

	The popup works in whole kilograms. Each entered total is split in proportion
	to the already-calculated visible weights; largest remainders receive the
	leftover kilograms so the distributed route values add back to the exact input.
	"""
	eligible_by_group = {}
	for row_index, row in enumerate(rows):
		row["manual_additional_weight"] = 0
		base_weight = _round_display_weight(row.get("program_weight"))
		if base_weight > 0:
			eligible_by_group.setdefault(_addition_group_key(row), []).append(
				(row_index, base_weight)
			)

	requested = {}
	for index, addition in enumerate(_parse_cloth_program_additions(additions), 1):
		weight = flt(addition.get("additional_weight"))
		if weight < 0:
			frappe.throw(
				_("Cloth Program Additions row {0}: Added Weight cannot be negative.").format(
					index
				)
			)
		key = _addition_group_key(addition)
		if not key[0]:
			continue
		requested[key] = requested.get(key, 0) + weight

	normalized_totals = []
	route_additions = []
	for key in sorted(requested):
		eligible_rows = eligible_by_group.get(key) or []
		added_weight = _round_display_weight(requested[key])
		if added_weight <= 0 or not eligible_rows:
			continue
		allocation = _allocate_added_weight(added_weight, eligible_rows)
		cloth_item, requirement_type, accessory_name, colour = key
		normalized_totals.append(
			{
				"cloth_item": cloth_item,
				"requirement_type": requirement_type,
				"accessory_name": accessory_name or None,
				"colour": colour or None,
				"additional_weight": added_weight,
			}
		)
		for row_index, route_weight in allocation.items():
			if route_weight <= 0:
				continue
			row = rows[row_index]
			row["manual_additional_weight"] += route_weight
			row["extra_weight"] = flt(
				flt(row.get("extra_weight")) + route_weight,
				WEIGHT_PRECISION,
			)
			row["program_weight"] = flt(
				flt(row.get("program_weight")) + route_weight,
				WEIGHT_PRECISION,
			)
			route_additions.append(
				{
					"cloth_item": cloth_item,
					"requirement_type": requirement_type,
					"accessory_name": accessory_name or None,
					"colour": colour or None,
					"dia": row.get("dia") or None,
					"additional_weight": route_weight,
				}
			)
	return normalized_totals, route_additions


def _serialize_cloth_program_additions(totals, routes):
	return frappe.as_json(
		{
			"version": CLOTH_PROGRAM_ADDITION_VERSION,
			"totals": totals,
			"routes": routes,
		}
	)


def _accessory_fabric_label(value):
	label = re.sub(
		r"\b\w",
		lambda match: match.group(0).upper(),
		" ".join(str(value or _("Accessory")).split()),
	)
	return label if re.search(r"\bFabric$", label, re.IGNORECASE) else f"{label} Fabric"


def build_cloth_program_display_data(preview):
	"""Shape calculated rows into the matrix shared by preview and print output."""
	table_groups = {}
	rows = preview.get("rows") or []
	addition_by_group = {}
	for addition in preview.get("additions") or []:
		cloth_item, requirement_type, accessory_name, colour = _addition_group_key(
			addition
		)
		addition_by_group[
			(cloth_item, requirement_type, accessory_name, colour or _("No Colour"))
		] = _round_display_weight(addition.get("additional_weight"))

	for row in rows:
		cloth_item = row.get("cloth_item") or _("Unspecified Cloth")
		requirement_type = (
			"accessory"
			if row.get("requirement_type") == "accessory"
			else "cloth"
		)
		accessory_name = row.get("accessory_name") or _("Accessory")
		colour = row.get("colour") or _("No Colour")
		if row.get("compacting_dia"):
			dia = _("{0} → {1}").format(
				row.get("input_dia") or _("No Dia"),
				row.get("compacting_dia") or _("No Dia"),
			)
		else:
			dia = row.get("dia") or _("No Dia")

		route_key = (requirement_type, accessory_name, dia)
		group = table_groups.setdefault(
			cloth_item,
			{
				"cloth_item": cloth_item,
				"colours": set(),
				"routes": {},
				"weights": {},
			},
		)
		group["colours"].add(colour)
		group["routes"][route_key] = {
			"requirement_type": requirement_type,
			"accessory_name": accessory_name,
			"fabric_type": (
				_accessory_fabric_label(accessory_name)
				if requirement_type == "accessory"
				else _("Main Fabric")
			),
			"dia": dia,
		}
		weight_key = (*route_key, colour)
		group["weights"][weight_key] = group["weights"].get(
			weight_key, 0
		) + _round_display_weight(row.get("program_weight"))

	tables = []
	for group in sorted(table_groups.values(), key=lambda value: value["cloth_item"]):
		colours = sorted(group["colours"])
		colour_totals = {colour: 0 for colour in colours}
		table_total = 0
		routes = []
		fabric_groups = []
		fabric_groups_by_type = {}
		ordered_routes = sorted(
			group["routes"].items(),
			key=lambda item: (
				item[1]["requirement_type"] != "cloth",
				item[1]["fabric_type"],
				item[1]["dia"],
			),
		)
		for route_key, route in ordered_routes:
			fabric_type = route["fabric_type"]
			if fabric_type not in fabric_groups_by_type:
				fabric_group = {
					"fabric_type": fabric_type,
					"requirement_type": route["requirement_type"],
					"accessory_name": route["accessory_name"],
					"routes": [],
					"colour_totals": {colour: 0 for colour in colours},
					"additions": {
						colour: addition_by_group.get(
							(
								group["cloth_item"],
								route["requirement_type"],
								(
									route["accessory_name"]
									if route["requirement_type"] == "accessory"
									else ""
								),
								colour,
							),
							0,
						)
						for colour in colours
					},
					"additional_total": 0,
					"total": 0,
				}
				fabric_group["additional_total"] = sum(
					fabric_group["additions"].values()
				)
				fabric_groups_by_type[fabric_type] = fabric_group
				fabric_groups.append(fabric_group)
			fabric_group = fabric_groups_by_type[fabric_type]
			weights = {}
			route_total = 0
			for colour in colours:
				weight = group["weights"].get((*route_key, colour), 0)
				weights[colour] = weight
				route_total += weight
				fabric_group["colour_totals"][colour] += weight
				colour_totals[colour] += weight
			table_total += route_total
			fabric_group["total"] += route_total
			route_data = {**route, "weights": weights, "total": route_total}
			routes.append(route_data)
			fabric_group["routes"].append(route_data)

		tables.append(
			{
				"cloth_item": group["cloth_item"],
				"colours": colours,
				"routes": routes,
				"fabric_groups": fabric_groups,
				"colour_totals": colour_totals,
				"total": table_total,
			}
		)

	display_totals = {
		"required_weight": 0,
		"extra_weight": 0,
		"manual_additional_weight": 0,
		"program_weight": 0,
	}
	for row in rows:
		required_weight = _round_display_weight(row.get("required_weight"))
		program_weight = _round_display_weight(row.get("program_weight"))
		manual_additional_weight = _round_display_weight(
			row.get("manual_additional_weight")
		)
		display_totals["required_weight"] += required_weight
		display_totals["extra_weight"] += max(
			program_weight - required_weight - manual_additional_weight,
			0,
		)
		display_totals["manual_additional_weight"] += manual_additional_weight
		display_totals["program_weight"] += program_weight

	return {
		**preview,
		"tables": tables,
		"display_totals": display_totals,
	}


def get_cloth_program_print_data(lot):
	"""Calculate print-ready data using the saved percentage and additions."""
	lot_doc = frappe.get_doc("Lot", lot)
	lot_doc.check_permission("read")
	if not lot_doc.get("production_detail"):
		frappe.throw(_("Select a garment Item Production Detail on the Lot first."))

	ipd_doc = frappe.get_cached_doc(
		"Item Production Detail", lot_doc.production_detail
	)
	preview = _calculate_cloth_program(
		lot_doc,
		ipd_doc,
		lot_doc.get("cloth_excess_percentage") or 0,
		lot_doc.get("cloth_program_additions"),
	)
	return {
		**build_cloth_program_display_data(preview),
		"item": lot_doc.get("item"),
		"production_detail": lot_doc.get("production_detail"),
	}


@frappe.whitelist()
def get_cloth_program_preview(lot, extra_percentage=0, additions=None):
	"""Return the preview and store its percentage/manual weight additions."""
	lot_doc = frappe.get_doc("Lot", lot)
	lot_doc.check_permission("write")
	if not lot_doc.get("production_detail"):
		frappe.throw(_("Select a garment Item Production Detail on the Lot first."))

	ipd_doc = frappe.get_cached_doc(
		"Item Production Detail", lot_doc.production_detail
	)
	selected_additions = (
		lot_doc.get("cloth_program_additions") if additions is None else additions
	)
	preview = _calculate_cloth_program(
		lot_doc, ipd_doc, extra_percentage, selected_additions
	)
	stored_additions = _serialize_cloth_program_additions(
		preview["additions"], preview["addition_routes"]
	)
	stored_payload = frappe.parse_json(stored_additions)
	current_value = lot_doc.get("cloth_program_additions")
	current_payload = (
		frappe.parse_json(current_value)
		if isinstance(current_value, str) and current_value
		else (current_value or {})
	)
	updates = {}
	if flt(lot_doc.get("cloth_excess_percentage")) != preview["extra_percentage"]:
		updates["cloth_excess_percentage"] = preview["extra_percentage"]
	if current_payload != stored_payload:
		updates["cloth_program_additions"] = stored_additions
	if updates:
		lot_doc.db_set(updates)
		# db_set deliberately avoids a full Lot save, so publish this authoritative
		# calculation update explicitly for the SD -> YRP replica.
		from production_api.sd_yrp_sync import enqueue_sd_yrp_publish

		enqueue_sd_yrp_publish(lot_doc, "on_update")
	preview["cloth_program_additions"] = stored_additions
	preview["lot_modified"] = lot_doc.modified
	return preview
