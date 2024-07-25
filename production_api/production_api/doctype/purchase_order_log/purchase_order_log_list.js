frappe.listview_settings["Purchase Order Log"] = {
	refresh: function(listview) {
		listview.page.clear_primary_action()
        $('.btn-new-doc').hide()
	},
};