frappe.pages['inward-quantity-repo'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Inward Quantity Report',
		single_column: true
	});
}

frappe.pages['inward-quantity-repo'].refresh = function (wrapper){
	new frappe.production.ui.InwardQuantityReport(wrapper)
}