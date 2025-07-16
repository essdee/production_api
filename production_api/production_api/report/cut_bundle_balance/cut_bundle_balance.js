// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Cut Bundle Balance"] = {
	"filters": [
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
		},
		{
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "Supplier",
		}
	]
};
