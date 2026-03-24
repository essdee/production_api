frappe.listview_settings["Item Production Detail"] = {
	add_fields: ["approval_status"],
	get_indicator: function (doc) {
		const status_map = {
			"Approved": ["Approved", "green"],
			"Cutting Approved": ["Cutting Approved", "blue"],
			"Not Approved": ["Not Approved", "orange"],
		};
		let [label, color] = status_map[doc.approval_status] || status_map["Not Approved"];
		return [__(label), color, "approval_status,=," + doc.approval_status];
	},
};
