// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["FG Stock With Lot"] = {
	"filters": [
		{
			"fieldname": "filter_date",
			"label": __("Filter Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd" : 1
		},
		{
			"fieldname" : "warehouse",
			"label" : __("Warehouse"),
			"fieldtype" :"Link",
			"width" : "100",
			"reqd" : 1,
			"options" : "Supplier",
			"get_query": () => {
                return {
                    filters: {
                        is_company_location: 1
                    }
                };
            }
		}
		// {
		// 	"fieldname": "item",
		// 	"label": __("Item"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Item",
		// },
		// {
		// 	"fieldname": "warehouse",
		// 	"label": __("Warehouse"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Supplier",
		// },
		// {
		// 	"fieldname": "lot",
		// 	"label": __("Lot"),
		// 	"fieldtype": "Link",
		// 	"width": "80",
		// 	"options": "Lot",
		// },
		// {
		// 	"fieldname":"received_type",
		// 	"fieldtype":"Link",
		// 	"label":"Received Type",
		// 	"options":"GRN Item Type",
		// 	"width":80,
		// },
		// {
		// 	"fieldname": 'remove_zero_balance_item',
		// 	"label": __('Remove Zero Balance Item'),
		// 	"fieldtype": 'Check'
		// },
	]
};
