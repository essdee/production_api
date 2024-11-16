// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["TIme and Action Pending Work"] = {
	"filters": [
		{
			"fieldtype":"Date",
			"fieldname":"date",
			"label":"Date",
			"reqd":true,
			"default":frappe.datetime.get_today()
		}, 
		{
			"fieldtype":"Link",
			"fieldname":"action",
			"options":"Action",
			"label":"Action",
			"reqd":1,
		}
	]
};
