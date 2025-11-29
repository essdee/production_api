// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Finishing Plan Report"] = {
	"filters": [
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"label": "Item",
		},
		{
			"fieldname": "season",
			"fieldtype": "Link",
			"options": "Product Season",
			"label": "Season",
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if(column.fieldname == 'cut_to_finishing_diff'){
			if(data && data.cut_to_finishing_diff < 0){
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if(data && data.cut_to_finishing_diff > 0){
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		if(column.fieldname == 'sewing_diff'){
			if(data && data.sewing_diff < 0){
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if(data && data.sewing_diff > 0){
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		if(column.fieldname == 'unaccountable'){
			if(data && data.unaccountable < 0){
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if(data && data.unaccountable > 0){
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		if(column.fieldname == 'cut_to_dispatch_diff'){
			if(data && data.cut_to_dispatch_diff < 0){
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if(data && data.cut_to_dispatch_diff > 0){
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		if(column.fieldname == 'finishing_inward_to_dispatch_diff'){
			if(data && data.finishing_inward_to_dispatch_diff < 0){
				value = "<span style='color:red'>" + value + "</span>";
			}
			else if(data && data.finishing_inward_to_dispatch_diff > 0){
				value = "<span style='color:green'>" + value + "</span>";
			}
		}

		return value;
	}
};
