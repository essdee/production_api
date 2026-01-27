frappe.pages['multi-ccr'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Multi CCR',
		single_column: true
	});
}

frappe.pages['multi-ccr'].refresh = function(wrapper){
	new frappe.production.ui.MultiCCR(wrapper)
}