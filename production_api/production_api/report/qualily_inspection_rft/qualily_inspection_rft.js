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
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		console.log(column)
		if (column.fieldname.includes('result')) {
			if (data && data[column.fieldname] === 'Fail') {
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if (data && data[column.fieldname] === 'Hold') {
				value = "<span style='color:orange'>" + value + "</span>";
			}
			else {
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		return value;
	}
};
