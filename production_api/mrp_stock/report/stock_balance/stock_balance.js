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
		// {
		// 	"fieldname": "item_group",
		// 	"label": __("Item Group"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Item Group"
		// },
		{
			"fieldname": "item",
			"label": __("Item Variant"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Variant",
		},
		{
			"fieldname": "parent_item",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Supplier",
		},
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
		{
			"fieldname": 'remove_zero_balance_item',
			"label": __('Remove Zero Balance Item'),
			"fieldtype": 'Check'
		},
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}  else if (column.fieldname == "warehouse_name") {
			value = `<a href="/app/supplier/${data.warehouse}" data-doctype="Supplier" data-name="${data.warehouse}" data-value="${data.warehouse}">${data.warehouse_name}</a>`;
		}

		return value;
	}
};