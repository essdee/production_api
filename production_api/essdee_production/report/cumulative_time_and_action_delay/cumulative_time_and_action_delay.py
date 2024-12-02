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
		{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":130},
		{"fieldtype":"Float","fieldname":"qty","label":"Quantity","width":100},
		{"fieldtype":"Data","fieldname":"colours","label":"Colours","width":150},
		{"fieldtype":"Link","fieldname":"action","label":"Next Action","options":"Action","width":120},
		# {"fieldtype":"Link","fieldname":"department","options":"Employee Department","label":"Department","width":120},
		# {"fieldtype":"Date","fieldname":"date","label":"Planned Date","width":120},
		# {"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":150},
	]
	return columns

def get_data():
	query_list = frappe.db.sql(
		"""
			SELECT A.lot, A.item, MIN(A.delay) AS delay, A.sizes, SUM(A.qty) AS qty, GROUP_CONCAT(A.colour SEPARATOR ', ') AS colours,
			GROUP_CONCAT(A.action SEPARATOR ', ') AS action FROM `tabTime and Action` AS A 
			JOIN `tabTime and Action Detail` AS B ON A.name = B.parent WHERE 
    		A.status != 'Completed' AND B.index2 = 1 GROUP BY A.lot ORDER BY A.delay ASC;
		"""
	)
	return query_list