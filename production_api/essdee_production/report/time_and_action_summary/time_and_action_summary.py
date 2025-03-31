# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	return columns, data, None, chart

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"action","label":"Action","options":"Action","width":150},
		{"fieldtype":"Int","fieldname":"no_of_completed","label":"No of Completed","width":200},
	]
	return columns

def get_data(filters=None):
	conditions = ""
	con = {}
	if filters.get('lot'):
		conditions += f" and B.lot = %(lot)s"
		con["lot"] = filters.get("lot")
	
	query_result = frappe.db.sql(
		f"""
		Select D.action, sum(D.no_of_completed) as no_of_completed from 
			(Select B.lot,A.action,min(A.completed) as no_of_completed, C.default_order from `tabTime and Action Detail` As A , 
			`tabTime and Action` As B, `tabAction` As C where A.parent = B.name AND A.action = C.name AND C.default = 1 {conditions}
			GROUP BY B.lot, A.action) as D
			GROUP BY D.action Order By D.default_order; 
		""" , con, as_dict=True
	)
	return query_result

def get_chart_data(data):
	labels = []
	for d in data:
		if d.action not in labels:
			labels.append(d.action)

	data_list = {label: 0 for label in labels}

	for d in data:
		data_list[d.action] += d.no_of_completed

	datasets = [{
		"name": "Completed Actions",
		"values": [data_list[label] for label in labels],
	}]

	return {
		"data": {
			"labels": labels,
			"datasets": datasets,
		},
		"type": "bar",
		"height": 500,
		"colors":[['#4dcd32', '#4dcd32', '#dd0453', '#4dcd32','#dd0453']]
	}

