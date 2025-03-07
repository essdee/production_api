// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Time and Action Dispatch Report"] = {
	"filters": [
		{
			"fieldname":"lot",
			"fieldtype":"Link",
			"options":"Lot",
			"label":"Lot",
		}
	]
};
