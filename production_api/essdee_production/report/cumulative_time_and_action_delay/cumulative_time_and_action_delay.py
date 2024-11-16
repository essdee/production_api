# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data()
	return columns, data

def get_columns():
	columns = [
		{"fieldtype":"Link","fieldname":"lot","options":"Lot","label":"Lot","width":120},
		{"fieldtype":"Link","fieldname":"item","options":"Item","label":"Item","width":150},
		{"fieldtype":"Int","fieldname":"delay","label":"Delay","width":80},
		{"fieldtype":"Data","fieldname":"colour","label":"Colour","width":150},
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":130},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity","width":100},
		{"fieldtype":"Link","fieldname":"action","label":"Next Action","options":"Action","width":120},
		{"fieldtype":"Link","fieldname":"department","options":"Employee Department","label":"Department","width":120},
		{"fieldtype":"Date","fieldname":"date","label":"Planned Date","width":120},
		{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":150},
	]
	return columns

def get_data():
	query_list = frappe.db.sql(
		"""
			SELECT A.lot, A.item, A.delay, A.colour, A.sizes, A.qty , B.action, B.department, B.date, B.rescheduled_date 
			FROM `tabTime and Action` AS A JOIN `tabTime and Action Detail` AS B ON A.name = B.parent 
			WHERE A.status != 'Completed' AND A.action IS NOT NULL AND B.index2 = 1
			ORDER BY A.delay ASC; 
		"""
	)
	return query_list