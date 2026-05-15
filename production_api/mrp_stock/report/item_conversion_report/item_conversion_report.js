// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Item Conversion Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"fieldtype": "Date",
			"label": "From Date",
			"default": frappe.datetime.add_months(frappe.datetime.month_start(), -1),
			"reqd": true
		},
		{
			"fieldname": "to_date",
			"fieldtype": "Date",
			"label": "To Date",
			"default": frappe.datetime.add_months(frappe.datetime.month_end(), -1),
			"reqd": true
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
		},
		{
			"fieldname": "from_item",
			"fieldtype": "Link",
			"options": "Item",
			"label": "From Item",
			"get_query": function() {
				return { filters: { is_stock_item: 1 } };
			},
		},
		{
			"fieldname": "to_item",
			"fieldtype": "Link",
			"options": "Item",
			"label": "To Item",
			"get_query": function() {
				return { filters: { is_stock_item: 1 } };
			},
		},
	]
};
