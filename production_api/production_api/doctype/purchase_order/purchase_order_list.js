frappe.listview_settings["Purchase Order"] = {
	filters: [
        ['open_status', '=', 'Open']
    ],
	get_indicator(doc) {
		const status_colors = {
			"Draft": "orange",
			"Ordered": "blue",
			"Partially Delivered": "yellow",
			"Delivered": "green",
			"Overdue": "red",
			"Cancelled": "darkgrey",
			"Partially Cancelled": "grey",
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