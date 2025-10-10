frappe.pages['t_and_a_update'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Time and Action Update',
		single_column: true
	});
}

frappe.pages['t_and_a_update'].refresh = function(wrapper) {
	new frappe.production.ui.TandAUpdate(wrapper);
}