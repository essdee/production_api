# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt
import frappe
from frappe.utils import nowdate

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{"fieldtype":"Link","fieldname":"lot","label":"Lot","options":"Lot","width":100},
		{"fieldtype":"Link","fieldname":"item","label":"Item","options":"Item","width":150},
	]
	if not filters.get("show_style_summary"):
		columns = columns + [
			{"fieldtype":"Link","fieldname":"master","label":"Master","options":"Action Master","width":120},
			{"fieldtype":"Data","fieldname":"colour","label":"Colour","width":100},
			{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":130},
			{"fieldtype":"Float","fieldname":"qty","label":"Qty","width":100},
			{"fieldtype":"Link","fieldname":"action","label":"Action","options":"Action","width":150},
			{"fieldtype":"Link","fieldname":"department","label":"Department","options":"Department","width":120},
			{"fieldtype":"Date","fieldname":"date","label":"Planned Date","width":120},
			{"fieldtype":"Date","fieldname":"rescheduled_date","label":"Rescheduled Date","width":120},
			{"fieldtype":"Int","fieldname":"date_diff","label":"Date Diff","width":90},
		]
	else:
		columns = columns + [
			{"fieldtype":"Data","fieldname":"sizes","label":"Sizes","width":130},
			{"fieldtype":"Int","fieldname":"date_diff","label":"Date Diff","width":90},
		]

	return columns

def get_data(filters):
	conditions = ""
	con = {}
	today = nowdate()
	if filters.get("lot"):
		conditions += f" and A.lot = %(lot)s"
		con["lot"] = filters.get("lot")

	conditions += f" and B.rescheduled_date <= %(today)s"
	con["today"] = today
	query_result = None
	if not filters.get("show_style_summary"):
		query_result = frappe.db.sql(
			f"""
				SELECT A.lot, A.item, A.master, A.colour, A.sizes, A.qty, B.action, 
				B.department, B.date ,B.rescheduled_date, DATEDIFF(B.rescheduled_date,'{today}') AS date_diff 
				FROM `tabTime and Action` AS A JOIN `tabTime and Action Detail` AS B ON A.name = B.parent    
				WHERE B.completed = 0 and B.index2 = 1 {conditions}
				ORDER BY date_diff ASC, A.lot;
			""", con, as_dict=True
		)
	else:
		query_result = frappe.db.sql(
			f"""
				SELECT A.lot, A.item, A.sizes, min(DATEDIFF(B.rescheduled_date,'{today}')) AS date_diff 
				FROM `tabTime and Action` AS A JOIN `tabTime and Action Detail` AS B ON A.name = B.parent    
				WHERE B.completed = 0 {conditions} Group By A.lot
				ORDER BY date_diff ASC, A.lot;
			""", con, as_dict=True
		)

	return query_result
