// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Work Station Capacity Blocking"] = {
	"filters": [
		{
			"fieldname": "start_date",
			"fieldtype": "Date",
			"label": "Start Date",
			"default": frappe.datetime.nowdate(),
			"reqd": 1
		},
		{
			"fieldname": "end_date",
			"fieldtype": "Date",
			"label": "End Date",
			"default": frappe.datetime.add_days(frappe.datetime.nowdate(), 7),
			"reqd": 1
		},
		{
			"fieldname": "work_station",
			"fieldtype": "Link",
			"options": "Work Station",
			"label": "Work Station",
		},
		{
			"fieldname": "lot",
			"fieldtype": "Link",
			"options": "Lot",
			"label": "Lot",
			get_query(){
				return {
					filters: {
						"version": "V2"
					}
				}
			}
		},
	]
};
