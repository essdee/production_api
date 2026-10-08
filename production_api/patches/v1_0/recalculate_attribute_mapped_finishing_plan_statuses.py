import frappe

from production_api.production_api.doctype.finishing_plan.finishing_plan import (
	AUTO_FP_STATUSES,
	compute_received_status,
)


def execute():
	candidates = get_candidate_plans()
	result = {
		"total": len(candidates),
		"updated": 0,
		"unchanged": 0,
		"skipped": 0,
	}

	for candidate in candidates:
		current_status = candidate.fp_status or ""
		if current_status not in AUTO_FP_STATUSES:
			result["skipped"] += 1
			continue

		finishing_plan = frappe.get_doc("Finishing Plan", candidate.name)
		new_status = compute_received_status(finishing_plan) or "Planned"
		if new_status == current_status:
			result["unchanged"] += 1
			continue

		frappe.db.set_value(
			"Finishing Plan",
			candidate.name,
			"fp_status",
			new_status,
			update_modified=False,
		)
		result["updated"] += 1

	print(
		"Attribute-mapped Finishing Plan status recalculation: "
		f"updated={result['updated']}, unchanged={result['unchanged']}, "
		f"skipped={result['skipped']}, total={result['total']}"
	)
	return result


def get_candidate_plans():
	return frappe.db.sql(
		"""
			SELECT fp.name, fp.fp_status
			FROM `tabFinishing Plan` fp
			INNER JOIN `tabItem Production Detail` ipd
				ON ipd.name = fp.production_detail
			WHERE
				fp.docstatus < 2
				AND (
					COALESCE(ipd.based_on_other_attribute_mapping, 0) = 1
					OR ipd.packing_mode = 'Size Wise Packing'
				)
			ORDER BY fp.name
		""",
		as_dict=True,
	)
