import frappe
from frappe.utils import flt

from production_api.production_api.doctype.finishing_plan.finishing_plan import (
	AUTO_FP_STATUSES,
	compute_received_status,
	get_finishing_dispatch_totals,
	get_set_item_parts_count,
)


def execute():
	if not frappe.db.exists("DocType", "Finishing Plan Dispatch Log"):
		return
	if not frappe.get_meta("Finishing Plan").has_field("finishing_plan_dispatch_logs"):
		return

	fp_names = frappe.get_all("Finishing Plan", pluck="name")
	logs_updated = 0
	statuses_updated = 0
	failed = 0

	for index, fp_name in enumerate(fp_names, start=1):
		try:
			finishing_doc = frappe.get_doc("Finishing Plan", fp_name)
			logs_updated += update_dispatch_logs(finishing_doc)
			statuses_updated += update_fp_status(finishing_doc)
		except Exception as exc:
			failed += 1
			frappe.db.rollback()
			print(f"[{index}/{len(fp_names)}] Dispatch percentage update failed for {fp_name}: {exc}")
			continue

		if index % 50 == 0:
			frappe.db.commit()
			print(f"Processed {index}/{len(fp_names)} Finishing Plans")

	frappe.db.commit()
	print(
		"Finishing Plan dispatch percentage patch: "
		f"logs_updated={logs_updated}, statuses_updated={statuses_updated}, "
		f"failed={failed}, total={len(fp_names)}"
	)


def update_dispatch_logs(finishing_doc):
	logs = frappe.get_all(
		"Finishing Plan Dispatch Log",
		filters={
			"parent": finishing_doc.name,
			"parenttype": "Finishing Plan",
			"parentfield": "finishing_plan_dispatch_logs",
			"cancelled": 0,
		},
		fields=["name", "dispatch_boxes"],
		order_by="posting_date asc, posting_time asc, creation asc, idx asc",
	)
	if not logs:
		return 0

	totals = get_finishing_dispatch_totals(finishing_doc)
	total_cutting = flt(totals.total_cutting)
	running_after = flt(totals.total_dispatched_pieces)
	dispatch_multiplier = flt(finishing_doc.pieces_per_box) * get_set_item_parts_count(finishing_doc)
	updated = 0

	for log in reversed(logs):
		dispatch_pieces = flt(log.dispatch_boxes) * dispatch_multiplier
		running_before = max(running_after - dispatch_pieces, 0)
		frappe.db.set_value(
			"Finishing Plan Dispatch Log",
			log.name,
			{
				"dispatch_pieces": dispatch_pieces,
				"total_dispatched_pieces_after": running_after,
				"cutting_qty": total_cutting,
				"dispatch_percentage_before": get_percentage(running_before, total_cutting),
				"dispatch_percentage_after": get_percentage(running_after, total_cutting),
			},
			update_modified=False,
		)
		running_after = running_before
		updated += 1

	return updated


def update_fp_status(finishing_doc):
	current_status = finishing_doc.fp_status or ""
	if current_status not in AUTO_FP_STATUSES:
		return 0

	new_status = compute_received_status(finishing_doc) or "Planned"
	if new_status == current_status:
		return 0

	frappe.db.set_value(
		"Finishing Plan",
		finishing_doc.name,
		"fp_status",
		new_status,
		update_modified=False,
	)
	return 1


def get_percentage(value, total):
	if not total:
		return 0
	return flt(value) / flt(total) * 100
