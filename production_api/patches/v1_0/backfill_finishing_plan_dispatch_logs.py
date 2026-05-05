import frappe
from frappe.utils import flt, get_datetime

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

	events = get_dispatch_events()
	fp_names = set(events)
	created = 0
	for fp_name, fp_events in events.items():
		for event in fp_events:
			if flt(event.dispatch_boxes) <= 0:
				continue
			if dispatch_log_exists(fp_name, event):
				continue
			create_dispatch_log(fp_name, event)
			created += 1

	for fp_name in frappe.get_all("Finishing Plan", pluck="name"):
		if ensure_historical_summary_log(fp_name):
			created += 1
			fp_names.add(fp_name)

	fp_names.update(get_existing_log_parents())

	logs_updated = 0
	statuses_updated = 0
	failed = 0
	for index, fp_name in enumerate(sorted(fp_names), start=1):
		try:
			finishing_doc = frappe.get_doc("Finishing Plan", fp_name)
			logs_updated += update_dispatch_logs(finishing_doc)
			statuses_updated += update_fp_status(finishing_doc)
		except Exception as exc:
			failed += 1
			frappe.db.rollback()
			print(f"[{index}/{len(fp_names)}] Dispatch log backfill failed for {fp_name}: {exc}")
			continue

		if index % 50 == 0:
			frappe.db.commit()
			print(f"Backfilled {index}/{len(fp_names)} Finishing Plans")

	frappe.db.commit()
	print(
		"Finishing Plan dispatch log backfill: "
		f"created={created}, logs_updated={logs_updated}, "
		f"statuses_updated={statuses_updated}, failed={failed}, total={len(fp_names)}"
	)


def get_dispatch_events():
	events = {}
	for event in get_direct_dispatch_events():
		events.setdefault(event.fp_name, []).append(event)
	for event in get_finishing_plan_dispatch_events():
		events.setdefault(event.fp_name, []).append(event)

	for fp_events in events.values():
		fp_events.sort(key=lambda row: (
			row.posting_date or "",
			row.posting_time or "",
			row.creation or "",
			row.stock_entry or "",
		))
	return events


def get_existing_log_parents():
	return [
		row.parent
		for row in frappe.db.sql(
			"""
			SELECT DISTINCT parent
			FROM `tabFinishing Plan Dispatch Log`
			WHERE
				parenttype = 'Finishing Plan'
				AND parentfield = 'finishing_plan_dispatch_logs'
			""",
			as_dict=True,
		)
	]


def get_direct_dispatch_events():
	return frappe.db.sql(
		"""
		SELECT
			se.name AS stock_entry,
			se.against_id AS fp_name,
			'Finishing Plan' AS source_doctype,
			se.against_id AS source_name,
			se.posting_date,
			se.posting_time,
			se.creation,
			SUM(sed.qty) AS dispatch_boxes
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE
			se.docstatus = 1
			AND se.purpose = 'Material Issue'
			AND se.against = 'Finishing Plan'
			AND se.against_id IS NOT NULL
		GROUP BY
			se.name, se.against_id, se.posting_date, se.posting_time, se.creation
		""",
		as_dict=True,
	)


def get_finishing_plan_dispatch_events():
	return frappe.db.sql(
		"""
		SELECT
			se.name AS stock_entry,
			fdi.against_id AS fp_name,
			'Finishing Plan Dispatch' AS source_doctype,
			se.against_id AS source_name,
			se.posting_date,
			se.posting_time,
			se.creation,
			SUM(fdi.quantity) AS dispatch_boxes
		FROM `tabStock Entry` se
		INNER JOIN `tabFinishing Plan Dispatch Item` fdi ON fdi.parent = se.against_id
		WHERE
			se.docstatus = 1
			AND se.against = 'Finishing Plan Dispatch'
			AND fdi.against_id IS NOT NULL
		GROUP BY
			se.name, fdi.against_id, se.against_id,
			se.posting_date, se.posting_time, se.creation
		""",
		as_dict=True,
	)


def dispatch_log_exists(fp_name, event):
	return frappe.db.exists(
		"Finishing Plan Dispatch Log",
		{
			"parent": fp_name,
			"parenttype": "Finishing Plan",
			"parentfield": "finishing_plan_dispatch_logs",
			"stock_entry": event.stock_entry,
			"source_doctype": event.source_doctype,
			"source_name": event.source_name,
		},
	)


def create_dispatch_log(fp_name, event):
	idx = get_next_log_idx(fp_name)
	frappe.get_doc({
		"doctype": "Finishing Plan Dispatch Log",
		"parent": fp_name,
		"parenttype": "Finishing Plan",
		"parentfield": "finishing_plan_dispatch_logs",
		"idx": idx,
		"stock_entry": event.stock_entry,
		"source_doctype": event.source_doctype,
		"source_name": event.source_name,
		"posting_date": event.posting_date,
		"posting_time": event.posting_time,
		"dispatch_boxes": flt(event.dispatch_boxes),
		"cancelled": 0,
	}).insert(ignore_permissions=True)


def ensure_historical_summary_log(fp_name):
	if frappe.db.exists(
		"Finishing Plan Dispatch Log",
		{
			"parent": fp_name,
			"parenttype": "Finishing Plan",
			"parentfield": "finishing_plan_dispatch_logs",
		},
	):
		return False

	dispatched_boxes = frappe.db.sql(
		"""
		SELECT SUM(dispatched)
		FROM `tabFinishing Plan GRN Detail`
		WHERE parent = %s
		""",
		fp_name,
	)[0][0] or 0
	if flt(dispatched_boxes) <= 0:
		return False

	fp_doc = frappe.get_cached_doc("Finishing Plan", fp_name)
	modified = get_datetime(fp_doc.modified) if fp_doc.modified else None
	frappe.get_doc({
		"doctype": "Finishing Plan Dispatch Log",
		"parent": fp_name,
		"parenttype": "Finishing Plan",
		"parentfield": "finishing_plan_dispatch_logs",
		"idx": 1,
		"source_doctype": "Finishing Plan",
		"source_name": fp_name,
		"posting_date": modified.date() if modified else None,
		"posting_time": modified.time() if modified else None,
		"dispatch_boxes": flt(dispatched_boxes),
		"cancelled": 0,
	}).insert(ignore_permissions=True)
	return True


def get_next_log_idx(fp_name):
	current = frappe.db.sql(
		"""
		SELECT MAX(idx)
		FROM `tabFinishing Plan Dispatch Log`
		WHERE parent = %s
		""",
		fp_name,
	)[0][0] or 0
	return current + 1


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
	log_idx = {log.name: idx for idx, log in enumerate(logs, start=1)}

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
				"idx": log_idx[log.name],
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
