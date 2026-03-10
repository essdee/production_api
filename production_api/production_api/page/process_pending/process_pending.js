frappe.pages['process-pending'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Process Pending',
		single_column: true
	});
}

frappe.pages['process-pending'].refresh = function(wrapper) {
	new frappe.production.ui.ProcessPending(wrapper);
}
