frappe.listview_settings["Production Order"] = {
	add_fields: ["price_approval_status", "status"],
	get_indicator: function (doc) {
		if (doc.price_approval_status === "Pending Approval") {
			return [__("Pending Approval"), "orange", "price_approval_status,=,Pending Approval"];
		}
		if (doc.docstatus === 1 && doc.status) {
			const status_colors = {
				"Open": "blue",
				"Pending Request": "orange",
				"Item Changed": "yellow",
				"Not Processed": "red",
				"Closed": "green",
			};
			return [__(doc.status), status_colors[doc.status] || "blue", "status,=," + doc.status];
		}
		const status_map = {
			0: [__("Draft"), "red", "docstatus,=,0"],
			1: [__("Submitted"), "blue", "docstatus,=,1"],
			2: [__("Cancelled"), "gray", "docstatus,=,2"],
		};
		return status_map[doc.docstatus];
	},
};
