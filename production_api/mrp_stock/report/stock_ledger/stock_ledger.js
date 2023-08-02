// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Ledger"] = {
	"filters": [
		// {
		// 	"fieldname":"company",
		// 	"label": __("Company"),
		// 	"fieldtype": "Link",
		// 	"options": "Company",
		// 	"default": frappe.defaults.get_user_default("Company"),
		// 	"reqd": 1
		// },
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Supplier",
			// "get_query": function() {
			// 	const company = frappe.query_report.get_filter_value('company');
			// 	return {
			// 		filters: { 'company': company }
			// 	}
			// }
		},
		{
			"fieldname":"item",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"options": "Item Variant",
		},
		{
			"fieldname":"parent_item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
		// {
		// 	"fieldname":"item_group",
		// 	"label": __("Item Group"),
		// 	"fieldtype": "Link",
		// 	"options": "Item Group"
		// },
		{
			"fieldname":"lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"options": "Lot"
		},
		{
			"fieldname":"brand",
			"label": __("Brand"),
			"fieldtype": "Link",
			"options": "Brand"
		},
		{
			"fieldname":"voucher_no",
			"label": __("Voucher #"),
			"fieldtype": "Data"
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname == "out_qty" && data && data.out_qty < 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		} else if (column.fieldname == "warehouse_name") {
			value = `<a href="/app/supplier/${data.warehouse}" data-doctype="Supplier" data-name="${data.warehouse}" data-value="${data.warehouse}">${data.warehouse_name}</a>`;
		}
		return value;
	},
};
