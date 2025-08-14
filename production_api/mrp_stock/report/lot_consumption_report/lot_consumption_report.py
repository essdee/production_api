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
			"fieldname": "stock_ledger_entry",
		 	"fieldtype": "Link",
		 	"options":"Stock Ledger Entry",
		 	"label": "Stock Ledger Entry",
		 	"width": 170
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"label": "Lot",
			"options": "Lot",
			"width": 100
		},
		{
			"fieldname": "item_variant",
			"fieldtype": "Link",
			"label": "Item Variant",
			"options": "Item Variant",
			"width": 250
		},
		{
			"fieldname": "quantity",
			"fieldtype": "Float",
			"label": "Quantity",
			"width": 100
		},
		{
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"label": "Valuation Rate",
			"width": 100
		},
		{
			"fieldname": "item_group",
			"fieldtype": "Link",
			"label": "Item Group",
			"options": "Item Group",
			"width": 150
		},
		{
			"fieldname": "item_name",
			"fieldtype": "Link",
			 "label": "Item",
			"options": "Item",
		 	"width": 170
		},
		{
			"fieldname": "from_warehouse",
			"fieldtype": "Link",
			"label": "From Warehouse",
			"options": "Supplier",
			"width": 150
		},
		{
			"fieldname": "to_warehouse",
			"fieldtype": "Link",
			"label": "To Warehouse",
			"options": "Supplier",
		 	"width": 150
		},
		{
			"fieldname": "voucher_type",
		 	"fieldtype": "Link",
		 	"options":"DocType",
		 	"label": "Voucher Type",
			"width": 130
		},
		{
			"fieldname": "voucher_no",
		 	"fieldtype": "Dynamic Link",
		 	"options": "voucher_type",
		 	"label": "Voucher No",
			"width": 130
		},
	]

def get_data(filters):
	item_groups = get_item_groups(filters.get("item_group"))
	doctypes = ['Stock Entry', "Lot Transfer", "Delivery Challan", "Goods Received Note"]
	data = frappe.db.sql(
		"""
			SELECT t1.name as stock_ledger_entry, t1.lot, t1.item as item_variant, 
			sum(t1.qty) as quantity, t1.valuation_rate, t3.item_group, 
			t3.name as item_name, t1.warehouse as from_warehouse,
			t1.voucher_type, t1.voucher_no
			FROM `tabStock Ledger Entry` as t1 
			JOIN `tabItem Variant` as t2 ON t1.item = t2.name 
			JOIN `tabItem` as t3 ON t2.item = t3.name 
			JOIN `tabItem Group` as t4 ON t3.item_group = t4.name 
			WHERE t1.posting_date >= %(start_date)s 
			AND t1.posting_date <= %(end_date)s 
			AND t1.lot = %(lot)s
			AND t3.item_group IN %(item_groups)s
			AND t1.qty < 0
			AND t1.is_cancelled = 0
			AND t1.voucher_type IN %(doctypes)s
			GROUP BY t1.item, t1.valuation_rate
		""", {
			"start_date": filters.get("start_date"),
			"end_date": filters.get("end_date"),
			"lot": filters.get("lot"),
			"item_groups": tuple(item_groups),
			"doctypes": tuple(doctypes),
		}, as_dict=True
	)
	to_warehouse_field = {
		"Delivery Challan": "supplier",
		"Goods Received Note": "delivery_location",
		"Stock Entry": "to_warehouse",
	}
	for row in data:
		if to_warehouse_field.get(row['voucher_type']):
			row['to_warehouse'] = frappe.get_value(row['voucher_type'], row["voucher_no"], to_warehouse_field[row['voucher_type']])
			if not row['to_warehouse'] and row['voucher_type'] == "Stock Entry":
				row['to_warehouse'] = frappe.get_value(row['voucher_type'], row["voucher_no"], "transfer_supplier")

		else:
			row['to_warehouse'] = row['from_warehouse']
	return data

def get_item_groups(item_group):
	item_grp_doc = frappe.get_doc("Item Group", item_group)
	if not item_grp_doc.is_group:
		return [item_group]
	
	item_groups = frappe.get_all("Item Group", pluck="name")
	grps = []
	for grp in item_groups:
		if grp != item_group:
			parent = get_parent_group(grp, item_group)
			if parent:
				grps.append(grp)
		else:
			grps.append(grp)
	return grps

def get_parent_group(grp, item_group):
	grp_doc = frappe.get_doc("Item Group", grp)
	if grp_doc.parent_item_group == item_group:
		return grp
	if not grp_doc.parent_item_group and grp_doc.is_group and grp != item_group:
		return None
	
	return get_parent_group(grp_doc.parent_item_group, item_group)
	