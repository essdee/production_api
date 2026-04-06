// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Update Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"fieldtype": "Date",
			"label": "From Date",
			"default": frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
			"reqd": true
		},
		{
			"fieldname": "to_date",
			"fieldtype": "Date",
			"label": "To Date",
			"default": frappe.datetime.nowdate(),
			"reqd": true
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"label": "Item",
		},
		{
			"fieldname": "item_variant",
			"fieldtype": "Link",
			"options": "Item Variant",
			"label": "Item Variant",
		},
		{
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "Warehouse",
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
		},
	]
};
