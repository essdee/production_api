import frappe

from production_api.patches.v1_0.backfill_finishing_plan_dispatch_logs import update_dispatch_logs


def execute():
	fp_names = [
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

	updated = 0
	failed = 0
	for index, fp_name in enumerate(fp_names, start=1):
		try:
			finishing_doc = frappe.get_doc("Finishing Plan", fp_name)
			updated += update_dispatch_logs(finishing_doc)
		except Exception as exc:
			failed += 1
			frappe.db.rollback()
			print(f"[{index}/{len(fp_names)}] Dispatch log reorder failed for {fp_name}: {exc}")
			continue

		if index % 50 == 0:
			frappe.db.commit()
			print(f"Reordered {index}/{len(fp_names)} Finishing Plans")

	frappe.db.commit()
	print(
		"Finishing Plan dispatch log reorder: "
		f"updated={updated}, failed={failed}, total={len(fp_names)}"
	)
