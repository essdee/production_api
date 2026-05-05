frappe.pages['rework-group-details'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rework Group Details',
		single_column: true
	});
}

frappe.pages['rework-group-details'].refresh = function(wrapper){
	new frappe.production.ui.ReworkGroupPage(wrapper)
}
