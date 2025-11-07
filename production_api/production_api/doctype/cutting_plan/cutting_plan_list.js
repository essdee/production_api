frappe.listview_settings["Cutting Plan"] = {
    add_fields: ["status"],
	has_indicator_for_draft: 1,
	get_indicator: function (doc) {
		const status_color = {
			"Draft": "gray",
			"Planned": "blue",
			"Fabric Partially Received": "orange",
			"Ready to Cut": "purple",
            "Cutting In Progress": "yellow",
            "Partially Completed": "orange",
            "Completed": "green",
            "Cut Panel Dispatch Pending": "red"
		};
		const status = doc.status;
		return [__(doc.status), status_color[doc.status]];
	},
};
