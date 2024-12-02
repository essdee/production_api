# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TimeandActionGanttChart(Document):
	pass

@frappe.whitelist()
def get_chart_data(action,work_station):
	cond =""
	if work_station != None and work_station != "":
		cond += f"and A.work_station = '{work_station}'"

	query = f"""
		SELECT CONCAT(B.lot, '-', B.item, '-', B.colour) AS name, A.rescheduled_start_date, 
			A.rescheduled_date, A.actual_start_date, A.actual_date 
		FROM `tabTime and Action Detail` AS A 
		JOIN `tabTime and Action` AS B 
		ON A.parent = B.name WHERE A.completed = 0 and A.action = '{action}' {cond} 
		ORDER BY A.rescheduled_date ASC;
	"""
	datas = frappe.db.sql(query, as_dict=True)
	items = []
	index = 0
	for data in datas:
		if data['actual_date']:
			items.append({
				"id" : index,
				"name" : data['name'],
				"start" : data['actual_start_date'],
				"end":data['actual_date'],
				"progress":100
			})
		else:
			items.append({
				"id" : index,
				"name" : data['name'],
				"start" : data['rescheduled_start_date'],
				"end":data['rescheduled_date'],
				"progress":100
			})	
		index = index + 1	
	return items	
	