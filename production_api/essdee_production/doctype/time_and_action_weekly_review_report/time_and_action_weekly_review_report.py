# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TimeandActionWeeklyReviewReport(Document):
	pass

@frappe.whitelist()
def get_report_data(lot, item, report_date):
	conditions = ""
	con = {}
	if lot:
		conditions += f" and lot = %(lot)s"
		con["lot"] = lot
	
	if report_date:
		conditions += f' and end_date < %(end_date)s'
		con['end_date'] = report_date

	if item:
		conditions += f" and item = %(item)s"
		con['item'] = item

	lot_list = frappe.db.sql(
		f"""
			SELECT t1.lot FROM `tabTime and Action` AS t1 JOIN `tabTime and Action Detail` AS t2
			ON t2.parent = t1.name JOIN (
				SELECT parent, MAX(idx) AS max_idx FROM `tabTime and Action Detail` GROUP BY parent
			) AS D ON t2.parent = D.parent AND t2.idx = D.max_idx
			WHERE 1 = 1 {conditions} GROUP BY t1.lot ORDER BY t2.rescheduled_date;
		""", con, as_list=True
	)
	data = {}
	conditions = ""
	con = {}

	if report_date:
		conditions += f' and t3.end_date < %(end_date)s'
		con['end_date'] = report_date

	conditions += " and t3.status != 'Completed'"	

	for lot in lot_list:
		lot = lot[0]
		data.setdefault(lot, {})
		t_and_a_list = frappe.db.sql(
			f"""
				SELECT t1.time_and_action, t1.master FROM `tabLot Time and Action Detail` as t1 JOIN 
				`tabTime and Action Detail` as t2 ON t2.parent = t1.time_and_action JOIN 
				`tabTime and Action` as t3 ON t2.parent = t3.name 
				WHERE t1.parent = '{lot}' {conditions} GROUP BY t1.time_and_action
			""",con, as_dict=True
		)
		masters = []
		for t_and_a in t_and_a_list:
			if t_and_a.master not in masters:
				masters.append(t_and_a.master)
		
		for master in masters:
			data[lot].setdefault(master, {"actions": [], "datas": []})
			for t_and_a in t_and_a_list:
				if t_and_a.master == master:
					doc = frappe.get_doc("Time and Action", t_and_a.time_and_action)
					d = {
						"item":doc.item,
						"master": doc.master,
						"colour": doc.colour,
						"sizes": doc.sizes,
						"qty": doc.qty,
						"start_date": doc.start_date,
						"delay": doc.delay
					}
					if not data[lot][master]['actions']:
						for row in doc.details:
							data[lot][master]['actions'].append(row.action)
					d['actions'] = []
					for row in doc.details:
						d['actions'].append({
							"department":row.department,
							"date":row.date,
							"rescheduled_date":row.rescheduled_date,
							"actual_date":row.actual_date,
							"reason": row.reason,
							"performance": row.performance,
							"delay": row.date_diff

						})
					data[lot][master]['datas'].append(d)
	return data