// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt
frappe.query_reports["Stock Item Balance Difference"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"read_only" : 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"read_only" : 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Variant",
		},
		{
			"fieldname": "parent_item",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Supplier",
		},
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Lot",
		},
		{
			"fieldname": "remove_zero_diff",
			"label": __("Remove Zero Differences"),
			"fieldtype": "Check",
		},
		
	],

};