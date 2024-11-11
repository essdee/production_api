// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.query_reports["Time and Action Report"] = {
	"filters": [
		{
			"fieldtype":"Link",
			"fieldname":"lot",
			"options":"Lot",
			"label":"Lot"
		}
	]
};
