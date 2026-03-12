frappe.pages['cutting-detail'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Cutting Detail',
		single_column: true
	});
}

frappe.pages['cutting-detail'].refresh = function(wrapper) {
	new frappe.production.ui.CuttingDetailReport(wrapper);
}