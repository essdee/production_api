frappe.listview_settings["FG Item Master"] = {
	onload: function(listview) {
		let method = "production_api.product_development.doctype.fg_item_master.fg_item_master.sync_fg_items";
		listview.page.add_action_item(__("Sync FG Items"), function() {
			listview.call_for_selected_items(method, { rename: false });
		});
		listview.page.add_action_item(__("Rename FG Items"), function() {
			listview.call_for_selected_items(method, { rename: true });
		});
	},
};