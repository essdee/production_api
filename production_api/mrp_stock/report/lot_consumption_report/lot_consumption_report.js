// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Lot Consumption Report"] = {
	"filters": [
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
			"reqd": true,
		},
		{
			"fieldname": "start_date",
			"fieldtype": "Date",
			"label": "Start Date",
			"reqd": true,
			"default": frappe.datetime.add_months(frappe.datetime.month_start(), -1)
		},
		{
			"fieldname": "end_date",
			"fieldtype": "Date",
			"label": "End Date",
			"reqd": true,
			"default": frappe.datetime.add_days(frappe.datetime.month_start(), -1),
		},
		{
			"fieldname": "item_group",
			"fieldtype": "Link",
			"label": "Item Group",
			"options": "Item Group",
			"reqd": true,
		}
	]
};
