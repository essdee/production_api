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
		{"fieldtype":"Link","fieldname":"department","options":"Employee Department","label":"Department","width":200},
		{"fieldtype":"Percent","fieldname":"performance","label":"Performance","width":200}
	]
	return columns

def get_data(filters=None):
	conditions = ""
	con = {}
	if filters.get('from_date'):
		conditions += f" and date >= %(from_date)s"
		con["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions += f" and date <= %(to_date)s"
		con["to_date"] = filters.get("to_date")

	query_result = frappe.db.sql(
		f""" Select department, avg(performance) as performance from `tabTime and Action Detail` 
			where completed = 1 {conditions} GROUP BY department ORDER BY performance DESC
		""", con , as_dict=True
	)
	return query_result

def get_chart_data(data):
	labels = []
	for d in data:
		if d.department not in labels:
			labels.append(d.department)

	data_list = {label: 0 for label in labels}

	for d in data:
		data_list[d.department] += d.performance

	datasets = [{
		"name": "",
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