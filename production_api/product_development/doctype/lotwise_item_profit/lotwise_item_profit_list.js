frappe.listview_settings["Lotwise Item Profit"] = {
	add_fields: ["lot_costing_type"],
	get_indicator(doc) {
		const status_colors = {
			"Costing": "orange",
			"Planned Qty": "blue",
			"Cutting Qty": "darkgrey",
			"Final Qty": "green",
		};

		if (status_colors[doc.lot_costing_type]) {
			return [
				__(doc.lot_costing_type),
				status_colors[doc.lot_costing_type],
				"lot_costing_type,=," + doc.lot_costing_type,
			];
		}
	},
};