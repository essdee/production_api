// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Non-GRN Received Items"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"fieldtype": "Date",
			"label": __("From Date"),
			"default": frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"fieldtype": "Date",
			"label": __("To Date"),
			"default": frappe.datetime.nowdate(),
			"reqd": 1
		},
		{
			"fieldname": "purpose",
			"fieldtype": "Select",
			"label": __("Purpose"),
			"options": "\nMaterial Receipt\nSend to Warehouse"
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": __("Lot")
		},
		{
			"fieldname": "received_location",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": __("Received Location")
		},
		{
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": __("Supplier")
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"label": __("Item")
		}
	]
};
