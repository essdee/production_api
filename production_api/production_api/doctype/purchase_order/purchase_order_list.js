frappe.listview_settings["Purchase Order"] = {
	get_indicator(doc) {
		const status_colors = {
			"Draft": "orange",
			"Submitted": "blue",
			"Cancelled": "gray",
			"Overdue": "red",
			"Partly Fulfilled": "yellow",
			"Completed": "green",
		};

		if (status_colors[doc.status]) {
			return [
				__(doc.status),
				status_colors[doc.status],
				"status,=," + doc.status,
			];
		}
	},
};