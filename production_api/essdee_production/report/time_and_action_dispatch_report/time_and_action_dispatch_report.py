# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname":"lot",
			"fieldtype":"Link",
			"label":"Lot",
			"options":"Lot",
			"width": 200,
		},
		{
			"fieldname":"item",
			"fieldtype":"Link",
			"label":"Item",
			"options":"Item",
			"width": 200,
		},
		{
			"fieldname":"sizes",
			"fieldtype":"Data",
			"label":"Sizes",
			"width": 300,
		},
		{
			"fieldname":"date",
			"fieldtype":"Date",
			"label":"Dispatch Date",
			"width": 200,
		},
		{
			"fieldname":"total_order_quantity",
			"fieldtype":"Int",
			"label":"Total Quantity"
		},
		{
			"fieldname":"cumulative_delay",
			"fieldtype":"Int",
			"label":"Cumulative Delay"
		}
	]

def get_data(filters):
	conditions = ""
	con = {}
	if filters.get('lot'):
		conditions += f" and t1.lot = %(lot)s"
		con['lot'] = filters.get('lot')
	
	res = frappe.db.sql(
		f"""
			Select t1.lot, t1.item, t1.sizes, max(t2.rescheduled_date) as date, t3.total_order_quantity, min(t1.delay) as cumulative_delay
			from `tabTime and Action` as t1 JOIN `tabTime and Action Detail` as t2
			On t2.parent = t1.name JOIN `tabLot` t3 on t1.lot = t3.name where 1 = 1 {conditions} group by t1.lot, t1.item
		""",con, as_dict=True
	)
	return res