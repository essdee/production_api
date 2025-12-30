// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Qualily Inspection RFT"] = {
	"filters": [
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot"
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"label": "Item"
		},
		{
			"fieldname": "from_date",
			"fieldtype": "Date",
			"label": "From Date"
		},
		{
			"fieldname": "to_date",
			"fieldtype": "Date",
			"label": "To Date"
		},
		{
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "Supplier"
		},
		{
			"fieldname": "result",
			"fieldtype": "Select",
			"options": "\nPass\nFail\nHold",
			"label": "Result",
		}
	]
};
