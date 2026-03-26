# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname": "stock_update", "fieldtype": "Link", "label": "Stock Update", "options": "Stock Update", "width": 200},
		{"fieldname": "update_type", "fieldtype": "Data", "label": "Update Type", "width": 130},
		{"fieldname": "warehouse", "fieldtype": "Link", "label": "Warehouse", "options": "Supplier", "width": 100},
		{"fieldname": "warehouse_name", "fieldtype": "Data", "label": "Warehouse Name", "width": 200},
		{"fieldname": "lot", "fieldtype": "Link", "label": "Lot", "options": "Lot", "width": 100},
		{"fieldname": "item", "fieldtype": "Link", "label": "Item", "options": "Item", "width": 250},
		{"fieldname": "item_variant", "fieldtype": "Link", "label": "Item Variant", "options": "Item Variant", "width": 250},
		{"fieldname": "available_stock", "fieldtype": "Float", "label": "Available Stock (Before)", "width": 150},
		{"fieldname": "qty", "fieldtype": "Float", "label": "Quantity", "width": 100},
		{"fieldname": "stock_after", "fieldtype": "Float", "label": "Stock After", "width": 120},
		{"fieldname": "uom", "fieldtype": "Link", "label": "UOM", "options": "UOM", "width": 100},
		{"fieldname": "rate", "fieldtype": "Currency", "label": "Rate", "width": 100},
		{"fieldname": "comments", "fieldtype": "Data", "label": "Comments", "width": 200},
	]

def get_data(filters):
	con = {}
	con['from_date'] = filters.get("from_date")
	con['to_date'] = filters.get("to_date")
	conditions = ""

	if filters.get("warehouse"):
		conditions += f" AND warehouse = %(warehouse)s"
		con['warehouse'] = filters.get("warehouse")

	su_list = frappe.db.sql(
		f"""
			SELECT name, update_type, warehouse, comments FROM `tabStock Update`
				WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND docstatus = 1 {conditions}
		""", con, as_dict=True
	)
	data = []
	for su in su_list:
		warehouse_name = None
		if su['warehouse']:
			warehouse_name = frappe.get_cached_value("Supplier", su['warehouse'], "supplier_name")

		con2 = {}
		con2['su'] = su['name']
		conditions2 = ""
		if filters.get("lot"):
			con2['lot'] = filters.get("lot")
			conditions2 += f" AND lot = %(lot)s"

		if filters.get("item_variant"):
			con2['item_variant'] = filters.get("item_variant")
			conditions2 += f" AND item_variant = %(item_variant)s"

		su_detail_items = frappe.db.sql(
			f"""
				SELECT item_variant, update_diff_qty, available_stock, lot, uom, rate FROM `tabStock Update Detail` WHERE parent = %(su)s {conditions2}
			""", con2, as_dict=True
		)
		for detail in su_detail_items:
			item_name = frappe.get_cached_value("Item Variant", detail['item_variant'], "item")
			if filters.get('item') and item_name != filters.get("item"):
				continue

			available_stock = detail['available_stock'] or 0
			update_diff_qty = detail['update_diff_qty'] or 0
			if su['update_type'] == 'Add':
				stock_after = available_stock + update_diff_qty
			else:
				stock_after = available_stock - update_diff_qty

			data.append(
				{
					"stock_update": su['name'],
					"update_type": su['update_type'],
					"warehouse": su['warehouse'],
					"warehouse_name": warehouse_name,
					"lot": detail['lot'],
					"item": item_name,
					"item_variant": detail['item_variant'],
					"available_stock": available_stock,
					"qty": update_diff_qty,
					"stock_after": stock_after,
					"uom": detail['uom'],
					"rate": detail['rate'],
					"comments": su['comments'],
				}
			)
	return data
