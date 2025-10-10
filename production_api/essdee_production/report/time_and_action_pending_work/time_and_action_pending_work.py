# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns() 
	data = get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"lot","options":"Lot","label":"Lot","width":100},
		{"fieldtype":"Link","fieldname":"item","options":"Item","label":"Item","width":150},
		{"fieldtype":"Link","fieldname":"master","options":"Action Master","label":"Master","width":120},
		{"fieldtype":"Data","fieldname":"colour","label":"Colour","width":120},
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":130},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity","width":100},
		{"fieldtype":"Link","fieldname":"action","options":"Action","label":"Action","width":100},
		{"fieldtype":"Link","fieldname":"department","options":"Department","label":"Department","width":120},
		{"fieldtype":"Date","fieldname":"date","label":"Planned Date","width":120},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":120},
		{"fieldtype":"Int","fieldname":"date_diff","label":"Date Diff","width":100}
	]
	return columns	

def get_data(filters):
	date = filters.get("date")
	action_cond = ""
	if action := filters.get("action"):
		action_cond += f"and B.action = '{action}'"

	if work_station := filters.get("work_station"):
		action_cond += f" and B.work_station = '{work_station}'"	

	query_result = frappe.db.sql(
		f"""
			Select A.lot, A.item, A.master, A.colour, A.sizes, A.qty, B.action, B.department, B.date,
			B.rescheduled_date , DATEDIFF(B.rescheduled_date,'{date}') as date_diff
			from `tabTime and Action` AS A JOIN `tabTime and Action Detail` AS B 
			ON A.name = B.parent WHERE B.rescheduled_date <= '{date}' and B.completed = 0 {action_cond}
			ORDER BY date_diff asc;
		""",as_dict=True
	)

	return query_result