// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

function multi_select_filter(fieldname, label, doctype) {
	return {
		fieldname,
		label: __(label),
		fieldtype: "MultiSelectList",
		options: doctype,
		get_data(txt) {
			return frappe.db.get_link_options(doctype, txt);
		},
	};
}

frappe.query_reports["Work Order Pending Report"] = {
	filters: [
		multi_select_filter("production_order", "Production Order", "Production Order"),
		multi_select_filter("lot", "Lot", "Lot"),
		multi_select_filter("item", "Item", "Item"),
		multi_select_filter("item_variant", "Item Variant", "Item Variant"),
		multi_select_filter("process", "Process", "Process"),
		multi_select_filter("supplier", "Supplier", "Supplier"),
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "status",
			label: __("Open Status"),
			fieldtype: "Select",
			options: "\nOpen\nClose Request\nClose",
		},
	],
};
