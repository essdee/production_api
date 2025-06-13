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
	]
};
