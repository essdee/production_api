// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

function toggle_based_on_filters() {
	const based_on = frappe.query_report.get_filter_value("based_on") || "Date";
	const from_date_filter = frappe.query_report.get_filter("from_date");
	const to_date_filter = frappe.query_report.get_filter("to_date");
	const status_filter = frappe.query_report.get_filter("status");

	const show_date = based_on === "Date";
	const show_status = based_on === "WO Status";

	[from_date_filter, to_date_filter].forEach((f) => {
		if (!f) return;
		f.df.hidden = show_date ? 0 : 1;
		f.df.reqd = show_date ? 1 : 0;
		f.refresh();
	});

	if (status_filter) {
		status_filter.df.hidden = show_status ? 0 : 1;
		status_filter.df.reqd = 0;
		status_filter.refresh();
	}
}

frappe.query_reports["Work Order Report"] = {
	"onload": function () {
		toggle_based_on_filters();
	},
	"filters": [
		{
			"fieldname": "based_on",
			"fieldtype": "Select",
			"label": "Based On",
			"options": "Date\nWO Status",
			"default": "Date",
			"reqd": 1,
			"on_change": function () {
				toggle_based_on_filters();
				frappe.query_report.refresh();
			},
		},
		{
			"fieldname":"from_date",
			"fieldtype":"Date",
			"label":"From Date",
			"default": frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
			"reqd":1,
		},
		{
			"fieldname":"to_date",
			"fieldtype":"Date",
			"label":"To Date",
			"default":frappe.datetime.nowdate(),
			"reqd":1,
		},
		{
			"fieldname":"supplier",
			"fieldtype":"Link",
			"options":"Supplier",
			"label":"Supplier",
		},
		{
			"fieldname":"process_name",
			"fieldtype":"Link",
			"options":"Process",
			"label":"Process",
		},
		{
			"fieldname":"item",
			"fieldtype":"Link",
			"options":"Item",
			"label":"Item",
		},
		{
			"fieldname":"lot",
			"fieldtype":"Link",
			"options":"Lot",
			"label":"Lot",
		},
		{
			"fieldname":"status",
			"fieldtype":"Select",
			"options":"\nOpen\nClose",
			"label":"WO Status",
		}
	]
};
