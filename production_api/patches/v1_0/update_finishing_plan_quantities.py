import frappe
from production_api.production_api.doctype.finishing_plan.finishing_plan import fetch_quantity, fetch_rejected_quantity


def execute():
	fp_list = frappe.get_all("Finishing Plan", pluck="name")
	total = len(fp_list)
	for i, fp_name in enumerate(fp_list):
		try:
			fetch_quantity(fp_name)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			print(f"[{i+1}/{total}] fetch_quantity FAILED for {fp_name}: {e}")

		try:
			fetch_rejected_quantity(fp_name)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			print(f"[{i+1}/{total}] fetch_rejected_quantity FAILED for {fp_name}: {e}")

		if (i + 1) % 10 == 0:
			print(f"Processed {i+1}/{total} Finishing Plans")

	print(f"Done. Processed {total} Finishing Plans")
