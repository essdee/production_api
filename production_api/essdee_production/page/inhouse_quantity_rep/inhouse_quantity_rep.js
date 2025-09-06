frappe.pages['inhouse-quantity-rep'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Inhouse Quantity Report',
		single_column: true
	});
}