// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt
/* eslint-disable */
let x = 0
frappe.query_reports["Lot Profit Comparison"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "lot",
			"label": __("Lot"),
			"fieldtype": "Link",
			"options": "Lot",
		},
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "FG Item Master",
		},
	],
	formatter: function(value, row, column, data, default_formatter) {
		let formatted_value = default_formatter(value, row, column, data);

		if (column.fieldname.includes("_qty") || column.fieldname.includes("_profit")) {
			if (!value) {
				return ""
			} else {
				if (column.fieldname.includes("_qty")) {
					let name = data[column.fieldname.replace("_qty", "_name")];
					formatted_value = '<a href="/app/lotwise-item-profit/' + name + '">' + formatted_value + '</a>';
				}
				if (x < 1) {
					x++;
					console.log(formatted_value, value, row, column, data);
				}
			}
		}

		// if (column.fieldname == "delivery_date") {
		// 	if (data.delivery_date > data.expected_delivery_date) {
		// 		value = "<span style='color:red'>" + value + "</span>";
		// 	} else if (data.delivery_date <= data.expected_delivery_date) {
		// 		value = "<span style='color:green'>" + value + "</span>";
		// 	} else {
		// 		value = "<span style='color:grey'>" + value + "</span>";
		// 	}
		// } else if (column.fieldname == "status") {
		// 	const status_colors = {
		// 		"0": "orange",
		// 		"1": "blue",
		// 		"2": "red",
		// 	};
		// 	const status_type = {
		// 		"0": "Draft",
		// 		"1": "Submitted",
		// 		"2": "Cancelled",
		// 	};
		// 	if (status_colors[data.status]) {
		// 		value = `<span class='indicator-pill ${status_colors[data.status]}'>${__(status_type[data.status])}</span>`;
		// 	}
		// }

		return formatted_value;
	}
};
