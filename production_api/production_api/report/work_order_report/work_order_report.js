// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Work Order Report"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"fieldtype":"Date",
			"label":"From Date",
			"default": frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
			"reqd":1,
		},
		{
			"fieldname":"to_date",
			"fieldtype":"Date",
			"label":"To Date",
			"default":frappe.datetime.nowdate(),
			"reqd":1,
		},
		{
			"fieldname":"supplier",
			"fieldtype":"Link",
			"options":"Supplier",
			"label":"Supplier",
		},
		{
			"fieldname":"process_name",
			"fieldtype":"Link",
			"options":"Process",
			"label":"Process",
		},
		{
			"fieldname":"item",
			"fieldtype":"Link",
			"options":"Item",
			"label":"Item",
		},
		{
			"fieldname":"lot",
			"fieldtype":"Link",
			"options":"Lot",
			"label":"Lot",
		},
		{
			"fieldname":"status",
			"fieldtype":"Select",
			"options":"\nOpen\nClose",
			"label":"Status",
			"default": "Open",
		}
	]
};
