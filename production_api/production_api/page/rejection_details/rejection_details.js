frappe.pages['rejection-details'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rejection Details',
		single_column: true
	});
}

frappe.pages['rejection-details'].refresh = function(wrapper){
	new frappe.production.ui.RejectionPage(wrapper)
}
