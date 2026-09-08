// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["FG Inward Temp"] = {
	filters: [
		{
			fieldname: "start_date", label: __("Start Date"), fieldtype: "Date",
			reqd: 1
		},
		{
			fieldname: "end_date", label: __("End Date"), fieldtype: "Date",
			reqd: 1
		},
		{
			fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link",
			options: "Supplier", reqd: 1,
			get_query: () => ({ filters: { is_company_location: 1 } })
		},
		// Historical lots need not exist as Lot documents in the current site.
		{ fieldname: "lot", label: __("Lot Number"), fieldtype: "Data" },
		// Historical item codes also need not have been migrated.
		{ fieldname: "item", label: __("Item"), fieldtype: "Data" }
	]
};
