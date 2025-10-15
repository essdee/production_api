frappe.pages['size-wise-stock-repo'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Size Wise Stock Report',
		single_column: true
	});
}

frappe.pages['size-wise-stock-repo'].refresh = function(wrapper){
	new frappe.production.ui.SizeWiseStockReport(wrapper)
}