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
		{"fieldtype":"Link","fieldname":"department","label":"Department","options":"Employee Department","width":120},
		{"fieldtype":"Date","fieldname":"date","label":"Planned Date","width":120},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":120},
		{"fieldtype":"Date","fieldname":"actual_date","label":"Actual Date","width":120},
		{"fieldtype":"Int","fieldname":"date_diff","label":"Date Difference","width":140},
		{"fieldtype":"Int","fieldname":"cumulative_diff","label":"Cumulative Difference","width":200},
	]
	return columns

def get_data(filters):
	lot = filters.get("lot")
	time_and_action = filters.get("time_and_action")

	query_result = frappe.db.sql(
		f""" SELECT A.action, A.department, A.date, A.rescheduled_date, A.actual_date, DATEDIFF(A.rescheduled_date, A.actual_date) AS date_diff, 
			DATEDIFF(A.date, A.actual_date) AS cumulative_diff FROM `tabTime and Action Detail` AS A JOIN `tabTime and Action` AS B 
			ON A.parent = B.name WHERE B.lot = '{lot}' AND B.name = '{time_and_action}' AND A.completed = 1;""", as_dict=True
	)
	return query_result

def get_chart_data(data):
	labels = []
	max = 0
	date_diff_values = []
	cumulative_values = []
	for d in data:
		if d.action not in labels:
			labels.append(d.action)

		max = d.date_diff if d.date_diff > max else (d.cumulative_diff if d.cumulative_diff > max else max)
		date_diff_values.append(d.date_diff)
		cumulative_values.append(d.cumulative_diff)

	if max < 0:
		max = 0

	datasets = [
		{"name": "Date Difference","values": date_diff_values,"color": "#4dcd32"},
        {"name": "Cumulative Difference","values": cumulative_values,"color": "#dd0453"}
	]
	
	return {
        "data": {
            "labels": labels,
            "datasets": datasets,
            "yRegions": [{
				"label": "Max", "start": 0, 'end': max + 1,
				"options": { "labelPos": 'right' }
			}]
        },
        "type": "line",
        "height": 1000
    }
