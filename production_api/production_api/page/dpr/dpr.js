frappe.pages['dpr'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'DPR',
		single_column: true,
	})
}

frappe.pages['dpr'].refresh = function(wrapper) {
	if (!wrapper.dpr) {
		wrapper.dpr = new frappe.production.ui.DPR(wrapper)
	}
}
