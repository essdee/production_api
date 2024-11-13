# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"lot","options":"Lot","label":"Lot"},
		{"fieldtype":"Link","fieldname":"item","options":"Item","label":"Item"},
		{"fieldtype":"Link","fieldname":"master","options":"Action Master","label":"Master"},
		{"fieldtype":"Data","fieldname":"colour","label":"Colour"},
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes"},
		{"fieldtype":"Data","fieldname":"description","label":"Description"},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity"},
		{"fieldtype":"Date","fieldname":"start_date","label":"Start Date"},
		{"fieldtype":"Link","fieldname":"action","options":"Action","label":"Action"},
		{"fieldtype":"Link","fieldname":"department","options":"Employee Department","label":"Department"},
		{"fieldtype":"Int","fieldname":"lead_time","label":"Lead Time"},
		{"fieldtype":"Date","fieldname":"date","label":"Date"},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date"},
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
		
		list1 = frappe.db.sql(
			""" SELECT * FROM `tabTime and Action` AS t_and_a
				WHERE t_and_a.name = %s """, (t_and_a,), as_dict=1
		)
		list2 = frappe.db.sql(
			""" SELECT * FROM `tabTime and Action Detail` AS t_and_a WHERE t_and_a.parent = %s AND t_and_a.completed = 0 
				ORDER BY t_and_a.idx ASC LIMIT 1 """, (t_and_a,), as_dict=1
		)
		if list1 and list2:
			final_list = list1[0] | list2[0]
			data_list.append(final_list)

	sorted_data = sorted(data_list, key=lambda x: x['lot'])
	return sorted_data
