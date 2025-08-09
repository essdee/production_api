# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname": "allocated_date","fieldtype": "Date","label": "Allocated Dae","width": 120},
		{"fieldname": "lot","fieldtype": "Link","options": "Lot","label": "Lot","width": 100},
		{"fieldname": "item","fieldtype": "Link","options": "Item","label": "Item","width": 300},
		{"fieldname": "work_station","fieldtype": "Link","options": "Work Station","label": "Work Station", "width": 150},
		{"fieldname": "colour","fieldtype": "Data","label": "Colour","width": 150},
		{"fieldname": "total_qty","fieldtype": "Float","label": "Total Qty","width": 100},
		{"fieldname": "target","fieldtype": "Float","label": "Target","width": 100},
		{"fieldname": "capacity","fieldtype": "Percent","label": "Capacity","width": 100},
	]

def get_data(filters):
	conditions = ""
	con = {}
	if filters.get("start_date"):
		conditions += " AND t2.allocated_date >= %(start_date)s"
		con['start_date'] = filters.get("start_date")
	if filters.get("end_date"):
		conditions += " AND t2.allocated_date <= %(end_date)s"
		con['end_date'] = filters.get("end_date")	
	if filters.get("work_station"):
		conditions += " AND t1.name = %(ws)s"
		con['ws'] = filters.get("work_station")
	if filters.get("lot"):
		conditions += " AND t1.lot = %(lot)s"
		con['lot'] = filters.get("lot")	

	return frappe.db.sql(
		f"""
			SELECT t2.allocated_date, t2.lot, t3.item, t1.name AS work_station, 
			t2.colour, t3.qty AS total_qty, t2.target, t2.capacity
			FROM `tabWork Station` AS t1 JOIN `tabWork Station Action` AS t2
			ON t2.parent = t1.name JOIN `tabTime and Action` AS t3 ON t2.time_and_action = t3.name
			WHERE 1 = 1 {conditions} ORDER BY t2.allocated_date
		""", con, as_dict=True
	)
