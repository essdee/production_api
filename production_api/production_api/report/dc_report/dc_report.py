# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_data(filters):
	d = {}
	conditions = ""
	if filters.from_date:
		conditions += f" AND t2.posting_date >= %(from_date)s"
		d['from_date'] = filters.from_date

	if filters.to_date:
		conditions += f" AND t2.posting_date <= %(to_date)s"
		d['to_date'] = filters.to_date

	if filters.lot:
		conditions += f" AND t2.lot = %(lot)s"
		d['lot'] = filters.lot	

	if filters.from_location:
		conditions += f" AND t2.from_location = %(from_location)s"
		d['from_location'] = filters.from_location		

	if filters.supplier:
		conditions += f" AND t2.supplier = %(supplier)s"
		d['supplier'] = filters.supplier		 

	data = frappe.db.sql(
		f"""
			SELECT t2.name as delivery_challan, t2.from_location, t2.from_location_name, t2.supplier, 
			t2.supplier_name, t2.lot, t2.process_name, t1.item_variant, t1.qty, t1.uom, t1.item_type as received_type 
			FROM `tabDelivery Challan Item` as t1 JOIN `tabDelivery Challan` as t2 ON t2.name = t1.parent 
			WHERE t1.docstatus = 1 AND t1.qty > 0 {conditions}
		""", d, as_dict=True
	)
	return data

def get_columns():
	return [
		{
			"fieldname": "delivery_challan",
			"fieldtype": "Link",
			"options": "Delivery Challan",
			"label": "Delivery Challan",
		},
		{
			"fieldname": "from_location",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "From Location",
		},
		{
			"fieldname": "from_location_name",
			"fieldtype": "Data",
			"label": "From Location Name",
		},
		{
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "Supplier",
		},
		{
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"label": "Supplier Name",
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
		},
		{
			"fieldname": "process_name",
			"fieldtype": "Link",
			"options": "Process",
			"label": "Process",
		},
		{
			"fieldname": "item_variant",
			"fieldtype": "Link",
			"options": "Item Variant",
			"label": "Item",
		},
		{
			"fieldname": "qty",
			"fieldtype": "Float",
			"label": "Qty",
		},
		{
			"fieldname": "received_type",
			"fieldtype": "Link",
			"options": "GRN Item Type",
			"label": "Received Type",
		},
		{
			"fieldname": "uom",
			"fieldtype": "Link",
			"options": "UOM",
			"label": "UOM",
		},
	]
