// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Balance"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group"
		},
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Variant",
			// "get_query": function() {
			// 	return {
			// 		query: "erpnext.controllers.queries.item_query",
			// 	};
			// }
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Supplier",
			// get_query: () => {
			// 	let warehouse_type = frappe.query_report.get_filter_value("warehouse_type");
			// 	let company = frappe.query_report.get_filter_value("company");

			// 	return {
			// 		filters: {
			// 			...warehouse_type && {warehouse_type},
			// 			...company && {company}
			// 		}
			// 	}
			// }
		},
		// {
		// 	"fieldname": "warehouse_type",
		// 	"label": __("Warehouse Type"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Warehouse Type"
		// },
		// {
		// 	"fieldname":"include_uom",
		// 	"label": __("Include UOM"),
		// 	"fieldtype": "Link",
		// 	"options": "UOM"
		// },
		{
			"fieldname": "show_variant_attributes",
			"label": __("Show Variant Attributes"),
			"fieldtype": "Check"
		},
		{
			"fieldname": 'show_stock_ageing_data',
			"label": __('Show Stock Ageing Data'),
			"fieldtype": 'Check'
		},
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		}
		else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}

		return value;
	}
};