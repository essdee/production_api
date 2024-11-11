# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"lot","options":"Lot","label":"Lot",},
		{"fieldtype":"Link","fieldname":"item","options":"Item","label":"Item",},
		{"fieldtype":"Link","fieldname":"master","options":"Action Master","label":"Master",},
		{"fieldtype":"Data","fieldname":"colour","label":"Colour",},
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes",},
		{"fieldtype":"Data","fieldname":"description","label":"Description",},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity",},
		{"fieldtype":"Date","fieldname":"start_date","label":"Start Date",},
		{"fieldtype":"Link","fieldname":"action","options":"Action","label":"Action",},
		{"fieldtype":"Link","fieldname":"department","options":"Employee Department","label":"Department",},
		{"fieldtype":"Int","fieldname":"lead_time","label":"Lead Time",},
		{"fieldtype":"Date","fieldname":"date","label":"Date",},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date",},
		{"fieldtype":"Date","fieldname":"actual_date","label":"Actual Date",},
		{"fieldtype":"Int","fieldname":"date_diff","label":"Date Diff",},
		{"fieldtype":"data","fieldname":"reason","label":"Reason",},
		{"fieldtype":"Percent","fieldname":"performance","label":"Performance",},
	]
	return columns

def get_data(filters):
	t_and_a_list = frappe.get_all("Time and Action",pluck="name")
	data_list = []

	for t_and_a in t_and_a_list:
		doc = frappe.get_doc("Time and Action",t_and_a)
		if filters.lot and filters.lot != doc.lot:
			continue

		data = {}
		data['lot'] = doc.lot
		data['item'] = doc.item
		data['master'] = doc.master
		data['colour'] = doc.colour
		data['sizes'] = doc.sizes
		data['description'] = doc.description
		data['qty'] = doc.qty
		data['start_date'] = doc.start_date
		for item in doc.details:
			if not item.completed:
				data['action'] = item.action
				data['department'] = item.department
				data['lead_time'] = item.lead_time
				data['date'] = item.date
				data['rescheduled_date'] = item.rescheduled_date
				data['actual_date'] = item.actual_date
				data['date_diff'] = item.date_diff
				data['reason'] = item.reason
				data['performance'] = item.performance
				data_list.append(data)
				break  
			
	return data_list
