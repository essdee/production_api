import frappe
from frappe.utils import getdate

def execute():
	"""Backfill cutting_start_date and cutting_end_date on existing Cutting Plans."""
	cutting_plans = frappe.get_all("Cutting Plan", pluck="name")

	for cp in cutting_plans:
		# Start date = creation date of earliest non-cancelled LaySheet (by lay_no)
		lay1_creation = frappe.db.sql("""
			SELECT creation FROM `tabCutting LaySheet`
			WHERE cutting_plan = %s AND status != 'Cancelled'
			ORDER BY lay_no ASC LIMIT 1
		""", cp)
		start_date = getdate(lay1_creation[0][0]) if lay1_creation else None

		# End date = max bundle_generated_date across all non-cancelled LaySheets
		end_date = frappe.db.sql("""
			SELECT MAX(bundle_generated_date)
			FROM `tabCutting LaySheet`
			WHERE cutting_plan = %s AND status != 'Cancelled' AND bundle_generated_date IS NOT NULL
		""", cp)[0][0]

		if start_date or end_date:
			frappe.db.set_value("Cutting Plan", cp, {
				"cutting_start_date": start_date,
				"cutting_end_date": end_date,
			}, update_modified=False)
