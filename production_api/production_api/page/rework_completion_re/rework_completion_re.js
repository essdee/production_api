frappe.pages['rework-completion-re'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Rework Completion Report',
		single_column: true
	});
}

frappe.pages['rework-completion-re'].refresh = function(wrapper){
	new frappe.production.ui.ReworkCompletion(wrapper)
}