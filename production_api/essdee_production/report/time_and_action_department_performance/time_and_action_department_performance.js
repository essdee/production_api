// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Time and Action Department Performance"] = {
	"filters": [
		{
			"fieldtype":"Date",
			"fieldname":"from_date",
			"label":"From Date"
		},
		{
			"fieldtype":"Date",
			"fieldname":"to_date",
			"label":"To Date"
		}
	]
};
