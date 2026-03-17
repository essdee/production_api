frappe.listview_settings["WO Debit"] = {
	get_indicator(doc) {
		if (doc.docstatus === 1) {
			if (doc.status === "Approved") {
				return [__("Approved"), "green", "status,=,Approved"];
			}
			return [__("Debit Requested"), "orange", "status,=,Debit Requested"];
		}
	},
};
