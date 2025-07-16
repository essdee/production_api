# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname": "stock_entry","fieldtype": "Link","label": "Stock Entry","options": "Stock Reconciliation", "width": 200},
		{"fieldname": "purpose","fieldtype": "Data","label": "Purpose", "width": 130},
		{"fieldname": "from_warehouse","fieldtype": "Link","label": "From Warehouse","options": "Supplier", "width": 100},
		{"fieldname": "from_warehouse_name","fieldtype": "Data","label": "From Warehouse Name", "width": 200},
		{"fieldname": "to_warehouse","fieldtype": "Link","label": "To Location","options": "Supplier", "width": 100},
		{"fieldname": "to_warehouse_name","fieldtype": "Data","label": "To Location Name", "width": 200},
		{"fieldname": "lot","fieldtype": "Link","label": "Lot","options": "Lot", "width": 100},
		{"fieldname": "item","fieldtype": "Link","label": "Item","options": "Item", "width": 250},
		{"fieldname": "item_variant","fieldtype": "Link","label": "Item Variant","options": "Item Variant", "width": 250},
		{"fieldname": "qty","fieldtype": "Float","label": "Quantity", "width": 100},
		{"fieldname": "uom","fieldtype": "Link","label": "UOM","options": "UOM", "width": 100},
		{"fieldname": "remarks","fieldtype": "Data","label": "Remarks", "width": 200},
	]

def get_data(filters):
	con = {}
	con['from_date'] = filters.get("from_date")
	con['to_date'] = filters.get("to_date")
	conditions = ""

	if filters.get("from_warehouse"):
		conditions += f" AND from_warehouse = %(from_warehouse)s"
		con['from_warehouse'] = filters.get("from_warehouse")	

	if filters.get("to_warehouse"):
		conditions += f" AND to_warehouse = %(to_warehouse)s"
		con['to_warehouse'] = filters.get("to_warehouse")	

	se_list = frappe.db.sql(
		f"""
			SELECT name, purpose, from_warehouse, to_warehouse FROM `tabStock Entry` 
				WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND docstatus = 1 {conditions}
		""", con, as_dict=True
	)
	data = []
	for se in se_list:
		purpose = se['purpose']
		from_warehouse_name = None
		to_warehouse_name = None
		if se['from_warehouse']:
			from_warehouse_name = frappe.get_cached_value("Supplier", se['from_warehouse'], "supplier_name")
		if se['to_warehouse']:
			to_warehouse_name = frappe.get_cached_value("Supplier", se['to_warehouse'], "supplier_name")

		con = {}
		con['se'] = se['name']
		conditions = ""
		if filters.get("lot"):
			con['lot'] = filters.get("lot")
			conditions += f" AND lot = %(lot)s"

		if filters.get("item_variant"):
			con['item_variant'] = filters.get("item_variant")
			conditions += f" AND item = %(item_variant)s"	

		se_table_items = frappe.db.sql(
			f"""
				SELECT item, qty, lot, uom, remarks FROM `tabStock Entry Detail` WHERE parent = %(se)s {conditions}
			""", con, as_dict=True
		)
		for table_item in se_table_items:
			item_name = frappe.get_cached_value("Item Variant", table_item['item'], "item")
			if filters.get('item') and item_name != filters.get("item"):
				continue

			data.append(
				{
					"stock_entry": se['name'],
					"purpose": purpose,
					"from_warehouse": se['from_warehouse'],
					"from_warehouse_name": from_warehouse_name,
					"to_warehouse": se['to_warehouse'],
					"to_warehouse_name": to_warehouse_name,
					"lot": table_item['lot'],
					"item": item_name,
					"item_variant": table_item['item'],
					"qty": table_item['qty'],
					"uom": table_item['uom'],
					"remarks": table_item['remarks'],
				}
			)
	return data
