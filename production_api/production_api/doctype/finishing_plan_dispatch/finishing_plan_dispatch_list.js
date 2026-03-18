frappe.listview_settings["Finishing Plan Dispatch"] = {
	onload: function(listview) {
		add_child_link_filter(listview, "lot", "Lot");
		add_child_link_filter(listview, "item", "Item");
	}
};

function add_child_link_filter(listview, fieldname, options) {
	listview.page.add_field({
		label: __(options),
		fieldtype: "Link",
		fieldname: fieldname,
		options: options,
		doctype: "Finishing Plan Dispatch Item",
		change() {
			listview.refresh();
		}
	}, listview.filter_area.standard_filters_wrapper);
}
