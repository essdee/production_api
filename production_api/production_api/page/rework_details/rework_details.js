frappe.pages['rework-details'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rework Details',
		single_column: true
	});
}

frappe.pages['rework-details'].refresh = function(wrapper){
	new frappe.production.ui.ReworkPage(wrapper)
}