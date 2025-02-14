// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Work Order Report"] = {
	"filters": [
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
			"options":"Link",
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
			"options":"Submitted\nClosed",
			"default":"Submitted",
			"label":"Status",
		}
	]
};
