frappe.listview_settings["Cutting Order"] = {
	add_fields: ["co_status"],
	get_indicator: function (doc) {
		const status_color = {
			"Draft": "gray",
			"Submitted": "blue",
			"Cutting In Progress": "yellow",
			"Partially Completed": "orange",
			"Completed": "green",
		};
		return [__(doc.co_status), status_color[doc.co_status], "co_status,=," + doc.co_status];
	},
	refresh() {
		$(".layout-side-section").css("display", "none");
	}
};
