# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data,group = get_data(filters)
	chart = get_chart_data(data,group)
	return columns, data, None, chart

def get_columns(filters=None):
	group_by = filters.get("select")
	group_by_map = {
        "Department": {
			"options":"Employee Department",
			"label":"Department",
			"fieldname":"department"
		},
		"Action": {
			"options":"Action",
			"label":"Action",
			"fieldname":"action"
		},
		"Work Station": {
			"options":"Work Station",
			"label":"Work Station",
			"fieldname":"work_station"
		}
    }
	options = group_by_map[group_by]['options']
	fieldname = group_by_map[group_by]['fieldname']
	label = group_by_map[group_by]['label']
	columns = [
		{"fieldtype":"Link","fieldname":fieldname,"options":options,"label":label,"width":200},
		{"fieldtype":"Percent","fieldname":"performance","label":"Performance","width":200}
	]
	return columns

def get_data(filters=None):
    conditions, con = "", {}

    if filters.get('from_date'):
        conditions += " and date >= %(from_date)s"
        con["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions += " and date <= %(to_date)s"
        con["to_date"] = filters["to_date"]

    group_by_map = {
        "Department": "department",
        "Action": "action",
        "Work Station": "work_station"
    }
    group_by = filters.get("select")
    data = group_by_map.get(group_by, None)
    cond = f"GROUP BY {data}" 

    query_result = frappe.db.sql(
        f"""SELECT {data} as {data}, AVG(performance) as performance
            FROM `tabTime and Action Detail`
            WHERE completed = 1 AND {data} IS NOT NULL {conditions} {cond}
            ORDER BY performance DESC
        """, con, as_dict=True
    )
    return query_result, data


def get_chart_data(data,group):
	labels = []
	for d in data:
		if d[group] not in labels:
			labels.append(d[group])

	data_list = {label: 0 for label in labels}

	for d in data:
		data_list[d[group]] += d.performance

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