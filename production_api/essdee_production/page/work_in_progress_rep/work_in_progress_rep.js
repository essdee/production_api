frappe.pages['work-in-progress-rep'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Work In Progress Report',
		single_column: true
	});
}

frappe.pages['work-in-progress-rep'].refresh = function(wrapper){
	new frappe.production.ui.WorkInProgress(wrapper)
}