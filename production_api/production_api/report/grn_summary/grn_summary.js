// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["GRN Summary"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"options": "Lot",
		},
		{
			"fieldname": "delivery_location",
			"label": __("Delivery Location"),
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": [
				{"value": "", "label": "All"},
				{ "value": "0", "label": __("Draft") },
				{ "value": "1", "label": __("Submitted") },
				{ "value": "2", "label": __("Cancelled") },
			],
		},

	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "delivery_date") {
			if (data.delivery_date > data.expected_delivery_date) {
				value = "<span style='color:red'>" + value + "</span>";
			} else if (data.delivery_date <= data.expected_delivery_date) {
				value = "<span style='color:green'>" + value + "</span>";
			} else {
				value = "<span style='color:grey'>" + value + "</span>";
			}
		} else if (column.fieldname == "status") {
			const status_colors = {
				"0": "orange",
				"1": "blue",
				"2": "red",
			};
			const status_type = {
				"0": "Draft",
				"1": "Submitted",
				"2": "Cancelled",
			};
			if (status_colors[data.status]) {
				value = `<span class='indicator-pill ${status_colors[data.status]}'>${__(status_type[data.status])}</span>`;
			}
		}

		return value;
	}
};
