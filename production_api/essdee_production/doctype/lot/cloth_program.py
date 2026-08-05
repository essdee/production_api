# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

"""Read-only knitting-program preview for a Lot.

The preview deliberately uses only the Lot's garment IPD and order quantities.
It does not create cloth IPDs, Item Variants, process matrices, or Lot child
rows. The yarn-to-cloth yield is fixed at 1.0 until a persisted cloth-production
workflow is introduced on this bench.
"""

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
	missing = []
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
			missing.append(" / ".join(key))
			continue
		row["input_dia"] = row["dia"]
		row["compacting_dia"] = compacting_dia

	if missing:
		frappe.throw(
			_(
				"Enter Compacting Dia for the following Cloth Item / {0} / Input Dia "
				"combination(s) in Item Production Detail {1}: {2}"
			).format(
				ipd_doc.get("packing_attribute") or _("Packing Attribute"),
				ipd_doc.name,
				", ".join(sorted(missing)),
			)
		)
	return True


def _calculate_cloth_program(lot_doc, ipd_doc, extra_percentage=0):
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
			key = (
				cloth_item,
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
	totals = {
		"required_weight": 0.0,
		"extra_weight": 0.0,
		"program_weight": 0.0,
	}
	for (cloth_item, colour, dia), raw_weight in sorted(weights.items()):
		required_weight = flt(raw_weight, WEIGHT_PRECISION)
		extra_weight = flt(raw_weight * extra_percentage / 100.0, WEIGHT_PRECISION)
		program_weight = flt(
			raw_weight * multiplier / CLOTH_PER_KG_YARN,
			WEIGHT_PRECISION,
		)
		rows.append(
			{
				"cloth_item": cloth_item,
				"colour": colour or None,
				"dia": dia or None,
				"required_weight": required_weight,
				"extra_weight": extra_weight,
				"program_weight": program_weight,
			}
		)
		totals["required_weight"] += required_weight
		totals["extra_weight"] += extra_weight
		totals["program_weight"] += program_weight

	for key in totals:
		totals[key] = flt(totals[key], WEIGHT_PRECISION)
	uses_compacting_details = _apply_compacting_details(ipd_doc, rows)

	return {
		"lot": lot_doc.name,
		"extra_percentage": extra_percentage,
		"cloth_per_kg_yarn": CLOTH_PER_KG_YARN,
		"uses_compacting_details": uses_compacting_details,
		"rows": rows,
		"totals": totals,
	}


@frappe.whitelist()
def get_cloth_program_preview(lot, extra_percentage=0):
	"""Return the calculated knitting program; never persist the preview."""
	lot_doc = frappe.get_doc("Lot", lot)
	lot_doc.check_permission("read")
	if not lot_doc.get("production_detail"):
		frappe.throw(_("Select a garment Item Production Detail on the Lot first."))

	ipd_doc = frappe.get_cached_doc(
		"Item Production Detail", lot_doc.production_detail
	)
	return _calculate_cloth_program(lot_doc, ipd_doc, extra_percentage)
