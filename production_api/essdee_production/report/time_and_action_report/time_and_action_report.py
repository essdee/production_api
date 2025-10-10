# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"lot","options":"Lot","label":"Lot","width":120},
		{"fieldtype":"Link","fieldname":"item","options":"Item","label":"Item","width":150},
		{"fieldtype":"Link","fieldname":"master","options":"Action Master","label":"Master","width":120},
		{"fieldtype":"Data","fieldname":"colour","label":"Colour","width":100},
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":100},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity","width":100},
		{"fieldtype":"Date","fieldname":"start_date","label":"Start Date","width":120},
		{"fieldtype":"Link","fieldname":"action","options":"Action","label":"Action","width":100},
		{"fieldtype":"Link","fieldname":"department","options":"Department","label":"Department","width":120},
		{"fieldtype":"Int","fieldname":"lead_time","label":"Lead Time","width":100},
		{"fieldtype":"Date","fieldname":"date","label":"Planned date","width":120},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":120},
	]
	return columns

def get_data(filters):
	t_and_a_list = frappe.get_all("Time and Action",pluck="name")
	data_list = []

	for t_and_a in t_and_a_list:
		doc = frappe.get_doc("Time and Action",t_and_a)
		if filters.lot and filters.lot != doc.lot:
			continue
		if doc.status == "Completed":
			continue
		
		query_list = frappe.db.sql(
			"""
				SELECT A.lot, A.item, A.master, A.colour, A.sizes, A.qty, A.start_date, B.action, B.department, B.lead_time,
				B.date, B.rescheduled_date FROM `tabTime and Action` AS A JOIN `tabTime and Action Detail` AS B ON A.name = B.parent
				WHERE A.name = %s AND B.completed = 0 AND A.status != 'Completed' ORDER BY B.idx ASC LIMIT 1
			""",(t_and_a,), as_dict = True
		)
		
		if query_list:
			data_list.append(query_list[0])

	sorted_data = sorted(data_list, key=lambda x: x['lot'])
	return sorted_data
