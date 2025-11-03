frappe.listview_settings["Purchase Invoice"] = {
    add_fields: ["status"],
	has_indicator_for_draft: 1,
	get_indicator: function (doc) {
		const status_color = {
			"Approved": "green",
			"Approval Initiated": "red",
			"Approval Pending": "orange",
			"Draft": "yellow",
            "Cancelled": "black",
            "Submitted": "blue",
		};
		const status = doc.status;
		return [__(status), status_color[status]];
	},
};
  