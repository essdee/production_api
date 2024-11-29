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
		},
		{
			"fieldtype":"Link",
			"fieldname":"work_station",
			"options":"Work Station",
			"label":"Work Station",
			get_query:function(){
				return {
					filters: {
						"action" : frappe.query_report.get_filter_value("action")
					}
				}
			}
		}
	]
};
