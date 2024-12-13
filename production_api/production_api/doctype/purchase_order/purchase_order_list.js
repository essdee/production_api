frappe.listview_settings["Purchase Order"] = {
	add_fields: ["status", "open_status"],
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
			"Closed": "light-blue",
		};

		if (status_colors[doc.status]) {
			return [
				__(doc.status),
				status_colors[doc.status],
				"status,=," + doc.status,
			];
		}
	},
	onload: function(listview) {
		let method = "production_api.production_api.doctype.purchase_order.purchase_order.close_or_open_purchase_orders";
		listview.page.add_action_item(__("Close"), function() {
			listview.call_for_selected_items(method, {"close": true});
		});
		listview.page.add_action_item(__("Open"), function() {
			listview.call_for_selected_items(method, {"close": false});
		});
		if (!frappe.route_options) {
			console.log("frappe.route_options is empty");
			frappe.route_options = {
				owner: frappe.session.user,
				open_status: "Open",
			};
		}
	},
};